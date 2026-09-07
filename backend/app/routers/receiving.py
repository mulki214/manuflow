from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.inventory_services import (
    apply_stock_delta,
    ensure_receiving_posted,
    generate_receipt_number,
    grams,
)
from app.models import (
    AccessLevel,
    Corporation,
    Department,
    FulfillmentStatus,
    InventoryMovement,
    InventoryMovementType,
    Plant,
    Product,
    ProductLot,
    ProductSupplySource,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    Receiving,
    ReceivingSourceType,
    ReceivingStatus,
    ReceivingTransportSource,
    SalesOrder,
    SalesOrderItem,
    SalesOrderMaterialAllocation,
    SalesOrderStatus,
    StorageLocation,
    Transportation,
    User,
)
from app.module_permissions import DepartmentModuleAccess, resolve_department_membership
from app.operational_services import (
    from_inventory_quantity,
    inventory_unit,
    require_whole_quantity,
    to_inventory_quantity,
)
from app.schemas import (
    InventoryMovementResponse,
    PaginatedInventoryMovements,
    PaginatedReceivings,
    ProductLotResponse,
    ProductStockResponse,
    ReceivingCreate,
    ReceivingResponse,
    ReceivingReversal,
    ReceivingSourceItemResponse,
    ReceivingSourceItemsResponse,
)

router = APIRouter(prefix="/receiving", tags=["Receiving"])


async def current_access(db: AsyncSession, user: User) -> DepartmentModuleAccess:
    department = await db.get(Department, settings.warehouse_department_code)
    access = resolve_department_membership(user, department)
    if not access.can_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active Warehouse department members can access this module",
        )
    return access


def ensure_can_reverse(access: DepartmentModuleAccess, user: User) -> None:
    if not access.is_pic and not access.is_head and user.access_level != AccessLevel.administrator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Warehouse PIC or Head can reverse Receiving",
        )


async def get_receiving(db: AsyncSession, receipt_number: str) -> Receiving:
    record = await db.get(Receiving, receipt_number)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiving not found")
    return record


async def receiving_response(db: AsyncSession, record: Receiving, access: DepartmentModuleAccess) -> ReceivingResponse:
    movement = (
        await db.execute(
            select(InventoryMovement)
            .where(InventoryMovement.reference_number == record.receipt_number)
            .order_by(InventoryMovement.id.desc())
            .limit(1)
        )
    ).scalar_one()
    reverser = await db.get(User, record.reversed_by) if record.reversed_by else None
    return ReceivingResponse(
        receipt_number=record.receipt_number,
        receipt_date=record.receipt_date,
        product_code=record.product_code,
        product_name=record.product_name,
        description=record.description,
        lot_number=record.lot_number,
        quantity_grams=from_inventory_quantity(record.quantity_grams, record.unit),
        unit=record.unit,
        plant_code=record.plant_code,
        plant_name=record.plant_name,
        storage_location_code=record.storage_location_code,
        storage_location_name=record.storage_location_name,
        source=record.source,
        source_type=record.source_type,
        source_code=record.source_code,
        source_document_item_id=record.purchase_order_item_id or record.sales_order_item_id,
        document_number=record.document_number,
        po_number=record.po_number,
        vehicle_number=record.vehicle_number,
        transport_source=record.transport_source,
        driver_name=record.driver_name,
        transportation_code=record.transportation_code,
        notes=record.notes,
        receiver_id=record.receiver_id,
        receiver_name=record.receiver_name,
        status=record.status,
        reversed_by=record.reversed_by,
        reversed_by_name=(f"{reverser.first_name} {reverser.last_name}".strip() if reverser else None),
        reversed_at=record.reversed_at,
        reversal_reason=record.reversal_reason,
        product_stock_after_grams=from_inventory_quantity(movement.product_stock_after_grams, record.unit),
        lot_stock_after_grams=from_inventory_quantity(movement.lot_stock_after_grams, record.unit),
        can_reverse=record.status == ReceivingStatus.posted and (access.is_pic or access.is_head),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("", response_model=PaginatedReceivings)
async def list_receivings(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    product_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    plant_code: str | None = None,
    storage_location_code: str | None = None,
    receiving_status: ReceivingStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedReceivings:
    access = await current_access(db, current_user)
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Receiving.receipt_number.ilike(term),
                Receiving.lot_number.ilike(term),
                Receiving.document_number.ilike(term),
                Receiving.po_number.ilike(term),
            )
        )
    if product_code:
        filters.append(Receiving.product_code == product_code)
    if date_from:
        filters.append(Receiving.receipt_date >= date_from)
    if date_to:
        filters.append(Receiving.receipt_date <= date_to)
    if plant_code:
        filters.append(Receiving.plant_code == plant_code)
    if storage_location_code:
        filters.append(Receiving.storage_location_code == storage_location_code)
    if receiving_status:
        filters.append(Receiving.status == receiving_status)
    query = (
        select(Receiving).where(*filters).order_by(Receiving.created_at.desc()).offset((page - 1) * size).limit(size)
    )
    records = list((await db.execute(query)).scalars().all())
    total = (await db.execute(select(func.count()).select_from(Receiving).where(*filters))).scalar_one()
    return PaginatedReceivings(
        items=[await receiving_response(db, record, access) for record in records],
        total=total,
        page=page,
        size=size,
    )


@router.get("/source-items", response_model=ReceivingSourceItemsResponse)
async def list_receiving_source_items(
    source_type: ReceivingSourceType | None = None,
    source_code: str | None = None,
    document_type: str | None = Query(default=None, pattern="^(purchase_order|sales_order)$"),
    customer_code: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReceivingSourceItemsResponse:
    await current_access(db, current_user)
    if document_type:
        expected_type = (
            ReceivingSourceType.supplier if document_type == "sales_order" else ReceivingSourceType.customer
        )
        if source_type and source_type != expected_type:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Receiving source does not match document type",
            )
        source_type = expected_type
    if not source_type or not source_code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Supplier is required")
    corporation = await db.get(Corporation, source_code)
    incorrect_role = (
        document_type == "purchase_order" and corporation is not None and not corporation.is_supplier
    ) or (
        document_type != "purchase_order"
        and corporation is not None
        and source_type == ReceivingSourceType.supplier
        and not corporation.is_supplier
    ) or (
        document_type != "purchase_order"
        and corporation is not None
        and source_type == ReceivingSourceType.customer
        and not corporation.is_customer
    )
    if not corporation or incorrect_role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corporation not found")
    responses: list[ReceivingSourceItemResponse] = []
    # A supplier receipt supplies material against customer demand (SO), while
    # a customer receipt is reconciled against supplier demand (PO).
    if source_type == ReceivingSourceType.supplier:
        rows = await db.execute(
            select(SalesOrderMaterialAllocation, SalesOrderItem, SalesOrder, Product)
            .join(SalesOrderItem, SalesOrderItem.id == SalesOrderMaterialAllocation.sales_order_item_id)
            .join(SalesOrder, SalesOrder.sales_order_number == SalesOrderItem.sales_order_number)
            .join(Product, Product.code == SalesOrderMaterialAllocation.material_product_code)
            .where(
                SalesOrder.status == SalesOrderStatus.approved,
                Product.supplier_code == source_code,
                Product.supply_source == ProductSupplySource.external_supplier,
                SalesOrderMaterialAllocation.received_quantity < SalesOrderMaterialAllocation.required_quantity,
            )
        )
        if customer_code:
            rows = await db.execute(
                select(SalesOrderMaterialAllocation, SalesOrderItem, SalesOrder, Product)
                .join(SalesOrderItem, SalesOrderItem.id == SalesOrderMaterialAllocation.sales_order_item_id)
                .join(SalesOrder, SalesOrder.sales_order_number == SalesOrderItem.sales_order_number)
                .join(Product, Product.code == SalesOrderMaterialAllocation.material_product_code)
                .where(
                    SalesOrder.status == SalesOrderStatus.approved,
                    SalesOrder.customer_code == customer_code,
                    Product.supplier_code == source_code,
                    Product.supply_source == ProductSupplySource.external_supplier,
                    SalesOrderMaterialAllocation.received_quantity < SalesOrderMaterialAllocation.required_quantity,
                )
            )
        for allocation, _item, order, product in rows.all():
            responses.append(
                ReceivingSourceItemResponse(
                    source_type=source_type,
                    source_code=source_code,
                    source_name=corporation.name,
                    document_number=order.customer_po_number,
                    item_id=allocation.id,
                    product_code=product.code,
                    product_description=product.description,
                    ordered_quantity=allocation.required_quantity,
                    received_quantity=allocation.received_quantity,
                    outstanding_quantity=allocation.required_quantity - allocation.received_quantity,
                    unit=allocation.unit,
                )
            )
    else:
        po_source_filter = (
            PurchaseOrder.supplier_code == source_code
            if document_type == "purchase_order"
            else Product.customer_code == source_code
        )
        rows = await db.execute(
            select(PurchaseOrderItem, PurchaseOrder)
            .join(PurchaseOrder, PurchaseOrder.po_number == PurchaseOrderItem.purchase_order_number)
            .join(Product, Product.code == PurchaseOrderItem.product_code)
            .where(
                PurchaseOrder.status == PurchaseOrderStatus.approved,
                PurchaseOrder.fulfillment_status == FulfillmentStatus.open,
                po_source_filter,
                Product.supplier_code == PurchaseOrder.supplier_code,
                Product.supply_source == ProductSupplySource.external_supplier,
                PurchaseOrderItem.received_quantity < PurchaseOrderItem.quantity_grams,
            )
        )
        for item, order in rows.all():
            responses.append(
                ReceivingSourceItemResponse(
                    source_type=source_type,
                    source_code=source_code,
                    source_name=corporation.name,
                    document_number=order.po_number,
                    item_id=item.id,
                    product_code=item.product_code,
                    product_description=item.description,
                    ordered_quantity=item.quantity_grams,
                    received_quantity=item.received_quantity,
                    outstanding_quantity=item.quantity_grams - item.received_quantity,
                    unit=item.unit,
                )
            )
    return ReceivingSourceItemsResponse(items=responses)


@router.post("", response_model=ReceivingResponse, status_code=status.HTTP_201_CREATED)
async def create_receiving(
    data: ReceivingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReceivingResponse:
    access = await current_access(db, current_user)
    expected_type = (
        ReceivingSourceType.supplier if data.document_type == "sales_order" else ReceivingSourceType.customer
    ) if data.document_type else data.source_type
    if data.source_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Receiving source does not match document type",
        )
    corporation = await db.get(Corporation, data.source_code)
    incorrect_role = (
        data.document_type == "purchase_order" and corporation and not corporation.is_supplier
    ) or (
        data.document_type != "purchase_order"
        and data.source_type == ReceivingSourceType.supplier
        and corporation
        and not corporation.is_supplier
    ) or (
        data.document_type != "purchase_order"
        and data.source_type == ReceivingSourceType.customer
        and corporation
        and not corporation.is_customer
    )
    if (
        not corporation
        or incorrect_role
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected corporation does not match Receiving source type",
        )

    purchase_item: PurchaseOrderItem | None = None
    sales_item: SalesOrderItem | None = None
    material_allocation: SalesOrderMaterialAllocation | None = None
    document_number: str
    if data.source_type == ReceivingSourceType.supplier:
        row = (
            await db.execute(
                select(SalesOrderMaterialAllocation, SalesOrderItem, SalesOrder, Product)
                .join(SalesOrderItem, SalesOrderItem.id == SalesOrderMaterialAllocation.sales_order_item_id)
                .join(SalesOrder, SalesOrder.sales_order_number == SalesOrderItem.sales_order_number)
                .join(Product, Product.code == SalesOrderMaterialAllocation.material_product_code)
                .where(SalesOrderMaterialAllocation.id == data.source_document_item_id)
                .with_for_update()
            )
        ).one_or_none()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Sales Order material allocation not found"
            )
        material_allocation, sales_item, sales_order, document_product = row
        if (
            sales_order.status != SalesOrderStatus.approved
            or document_product.supply_source != ProductSupplySource.external_supplier
            or document_product.supplier_code != corporation.code
            or (data.customer_code and sales_order.customer_code != data.customer_code)
        ):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Sales Order is not available")
        outstanding = material_allocation.required_quantity - material_allocation.received_quantity
        document_number = sales_order.customer_po_number
        product_code = document_product.code
        unit = material_allocation.unit
    else:
        row = (
            await db.execute(
                select(PurchaseOrderItem, PurchaseOrder, Product)
                .join(PurchaseOrder, PurchaseOrder.po_number == PurchaseOrderItem.purchase_order_number)
                .join(Product, Product.code == PurchaseOrderItem.product_code)
                .where(PurchaseOrderItem.id == data.source_document_item_id)
                .with_for_update()
            )
        ).one_or_none()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Purchase Order item not found"
            )
        purchase_item, purchase_order, document_product = row
        if (
            purchase_order.status != PurchaseOrderStatus.approved
            or (data.document_type == "purchase_order" and purchase_order.supplier_code != corporation.code)
            or (data.document_type != "purchase_order" and document_product.customer_code != corporation.code)
            or document_product.supplier_code != purchase_order.supplier_code
            or document_product.supply_source != ProductSupplySource.external_supplier
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Purchase Order is not available"
            )
        outstanding = purchase_item.quantity_grams - purchase_item.received_quantity
        document_number = purchase_order.po_number
        product_code = purchase_item.product_code
        unit = purchase_item.unit

    document_quantity = grams(data.quantity_grams)
    try:
        require_whole_quantity(document_quantity, unit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if document_quantity > outstanding:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Receiving quantity exceeds outstanding quantity ({outstanding} {unit})",
        )
    quantity = to_inventory_quantity(document_quantity, unit)
    stock_unit = inventory_unit(unit)
    product = (await db.execute(select(Product).where(Product.code == product_code).with_for_update())).scalar_one()
    plant = await db.get(Plant, data.plant_code)
    location = await db.get(StorageLocation, data.storage_location_code)
    if not plant or not location or location.plant_code != plant.code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Storage Location must belong to the selected Plant",
        )
    transportation = None
    if data.transport_source == ReceivingTransportSource.internal:
        transportation = await db.get(Transportation, data.transportation_code)
        if not transportation or not transportation.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Selected Transportation must be active",
            )

    lot = (
        await db.execute(
            select(ProductLot)
            .where(
                ProductLot.product_code == product.code,
                ProductLot.lot_number == data.lot_number,
                ProductLot.storage_location_code == location.code,
                ProductLot.unit == stock_unit,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    existing_lot_quantity = lot.current_quantity_grams if lot else Decimal("0")
    product_after, lot_after = apply_stock_delta(
        product.current_stock_grams or Decimal("0"), existing_lot_quantity, quantity
    )
    if lot:
        lot.initial_quantity_grams += quantity
        lot.current_quantity_grams = lot_after
    else:
        lot = ProductLot(
            product_code=product.code,
            lot_number=data.lot_number,
            plant_code=plant.code,
            storage_location_code=location.code,
            unit=stock_unit,
            initial_quantity_grams=quantity,
            current_quantity_grams=lot_after,
        )
        db.add(lot)
        await db.flush()

    if purchase_item:
        purchase_item.received_quantity += document_quantity
        await db.flush()
        open_items = await db.scalar(
            select(func.count())
            .select_from(PurchaseOrderItem)
            .where(
                PurchaseOrderItem.purchase_order_number == purchase_order.po_number,
                PurchaseOrderItem.received_quantity < PurchaseOrderItem.quantity_grams,
            )
        )
        purchase_order.fulfillment_status = FulfillmentStatus.closed if open_items == 0 else FulfillmentStatus.open
    if material_allocation:
        material_allocation.received_quantity += document_quantity

    receipt_number = await generate_receipt_number(db, data.receipt_date)
    record = Receiving(
        receipt_number=receipt_number,
        receipt_date=data.receipt_date,
        product_code=product.code,
        product_name=product.part_name,
        description=product.description,
        lot_id=lot.id,
        lot_number=lot.lot_number,
        quantity_grams=quantity,
        unit=unit,
        plant_code=plant.code,
        plant_name=plant.name,
        storage_location_code=location.code,
        storage_location_name=location.name,
        source=corporation.name,
        source_type=data.source_type,
        source_code=corporation.code,
        purchase_order_item_id=purchase_item.id if purchase_item else None,
        sales_order_item_id=sales_item.id if sales_item else None,
        material_allocation_id=material_allocation.id if material_allocation else None,
        document_number=data.document_number,
        po_number=document_number,
        transport_source=data.transport_source.value,
        transportation_code=transportation.code if transportation else None,
        vehicle_number=(transportation.vehicle_number if transportation else data.vehicle_number),
        driver_name=(None if transportation else data.driver_name),
        notes=data.notes,
        receiver_id=current_user.id,
        receiver_name=f"{current_user.first_name} {current_user.last_name}".strip(),
        status=ReceivingStatus.posted,
    )
    product.current_stock_grams = product_after
    db.add(record)
    db.add(
        InventoryMovement(
            movement_type=InventoryMovementType.receiving_in,
            product_code=product.code,
            lot_id=lot.id,
            unit=stock_unit,
            quantity_grams=quantity,
            product_stock_after_grams=product_after,
            lot_stock_after_grams=lot_after,
            reference_type="receiving",
            reference_number=receipt_number,
            performed_by=current_user.id,
            notes=data.notes,
        )
    )
    try:
        await db.commit()
        await db.refresh(record)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Receiving Number or inventory balance conflicts with existing data",
        ) from exc
    return await receiving_response(db, record, access)


@router.get("/stock/{product_code}", response_model=ProductStockResponse)
async def get_product_stock(
    product_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductStockResponse:
    await current_access(db, current_user)
    product = await db.get(Product, product_code)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    lots = list(
        (
            await db.execute(
                select(ProductLot).where(ProductLot.product_code == product_code).order_by(ProductLot.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    lot_total = sum((lot.current_quantity_grams for lot in lots), Decimal("0"))
    stock_by_unit: dict[str, Decimal] = {}
    for lot in lots:
        stock_by_unit[lot.unit] = stock_by_unit.get(lot.unit, Decimal("0")) + lot.current_quantity_grams
    return ProductStockResponse(
        product_code=product.code,
        product_name=product.part_name,
        current_stock_grams=product.current_stock_grams,
        lot_total_grams=lot_total,
        lots=[ProductLotResponse.model_validate(lot) for lot in lots],
        stock_by_unit=stock_by_unit,
    )


@router.get("/movements/history", response_model=PaginatedInventoryMovements)
async def list_inventory_movements(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    product_code: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedInventoryMovements:
    await current_access(db, current_user)
    filters = [InventoryMovement.product_code == product_code] if product_code else []
    query = (
        select(InventoryMovement)
        .where(*filters)
        .order_by(InventoryMovement.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = list((await db.execute(query)).scalars().all())
    total = (await db.execute(select(func.count()).select_from(InventoryMovement).where(*filters))).scalar_one()
    return PaginatedInventoryMovements(
        items=[InventoryMovementResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{receipt_number}", response_model=ReceivingResponse)
async def get_receiving_detail(
    receipt_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReceivingResponse:
    access = await current_access(db, current_user)
    return await receiving_response(db, await get_receiving(db, receipt_number), access)


@router.post("/{receipt_number}/reverse", response_model=ReceivingResponse)
async def reverse_receiving(
    receipt_number: str,
    data: ReceivingReversal,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReceivingResponse:
    access = await current_access(db, current_user)
    ensure_can_reverse(access, current_user)
    record = await get_receiving(db, receipt_number)
    ensure_receiving_posted(record.status)
    product = (
        await db.execute(select(Product).where(Product.code == record.product_code).with_for_update())
    ).scalar_one()
    lot = (await db.execute(select(ProductLot).where(ProductLot.id == record.lot_id).with_for_update())).scalar_one()
    try:
        product_after, lot_after = apply_stock_delta(
            product.current_stock_grams, lot.current_quantity_grams, -record.quantity_grams
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Receiving cannot be reversed because stock from this Lot has already been used",
        ) from exc
    product.current_stock_grams = product_after
    lot.current_quantity_grams = lot_after
    if record.purchase_order_item_id:
        purchase_item = (
            await db.execute(
                select(PurchaseOrderItem).where(PurchaseOrderItem.id == record.purchase_order_item_id).with_for_update()
            )
        ).scalar_one()
        purchase_item.received_quantity -= from_inventory_quantity(record.quantity_grams, record.unit)
        purchase_order = await db.get(PurchaseOrder, purchase_item.purchase_order_number)
        if purchase_order:
            purchase_order.fulfillment_status = FulfillmentStatus.open
    if record.material_allocation_id:
        allocation = (
            await db.execute(
                select(SalesOrderMaterialAllocation)
                .where(SalesOrderMaterialAllocation.id == record.material_allocation_id)
                .with_for_update()
            )
        ).scalar_one()
        allocation.received_quantity -= from_inventory_quantity(record.quantity_grams, record.unit)
    elif record.sales_order_item_id:
        sales_item = (
            await db.execute(
                select(SalesOrderItem).where(SalesOrderItem.id == record.sales_order_item_id).with_for_update()
            )
        ).scalar_one()
        sales_item.material_received_quantity -= from_inventory_quantity(record.quantity_grams, record.unit)
    record.status = ReceivingStatus.reversed
    record.reversed_by = current_user.id
    record.reversed_at = datetime.now(timezone.utc)
    record.reversal_reason = data.reason
    db.add(
        InventoryMovement(
            movement_type=InventoryMovementType.receiving_reversal,
            product_code=product.code,
            lot_id=lot.id,
            unit=inventory_unit(record.unit),
            quantity_grams=-record.quantity_grams,
            product_stock_after_grams=product_after,
            lot_stock_after_grams=lot_after,
            reference_type="receiving_reversal",
            reference_number=record.receipt_number,
            performed_by=current_user.id,
            notes=data.reason,
        )
    )
    await db.commit()
    await db.refresh(record)
    return await receiving_response(db, record, access)
