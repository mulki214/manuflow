from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.document_services import purchase_order_pdf_bytes, signed_document_payload, verify_document_payload
from app.inventory_services import apply_stock_delta
from app.models import (
    Corporation,
    Department,
    FulfillmentStatus,
    InventoryMovement,
    InventoryMovementType,
    Plant,
    Product,
    ProductLot,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderKind,
    PurchaseOrderStatus,
    SalesOrder,
    SalesOrderItem,
    SalesOrderMaterialAllocation,
    SalesOrderStatus,
    SubcontractDispatch,
    SubcontractDispatchStatus,
    User,
    WipLotJob,
    WipLotStatus,
    WipProcess,
    WipProcessType,
)
from app.module_permissions import ensure_department_access, resolve_department_membership
from app.operational_services import inventory_unit, require_whole_quantity, to_inventory_quantity
from app.purchasing_permissions import (
    PurchasingAccess,
    ensure_purchasing_access,
    ensure_purchasing_head,
    resolve_purchasing_access,
)
from app.purchasing_services import (
    calculate_line_amount,
    calculate_purchase_totals,
    ensure_waiting_review,
    generate_purchase_order_number,
    payment_due_date,
    sales_order_po_demand_rows,
)
from app.schemas import (
    PaginatedPurchaseOrders,
    PurchaseOrderCreate,
    PurchaseOrderItemResponse,
    PurchaseOrderRejection,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
    SubcontractDispatchCreate,
    SubcontractDispatchResponse,
)

router = APIRouter(prefix="/purchasing", tags=["Purchasing"])


async def current_access(db: AsyncSession, user: User) -> PurchasingAccess:
    department = await db.get(Department, settings.purchasing_department_code)
    access = resolve_purchasing_access(user, department)
    ensure_purchasing_access(access)
    return access


async def warehouse_access(db: AsyncSession, user: User) -> None:
    department = await db.get(Department, settings.warehouse_department_code)
    access = resolve_department_membership(user, department)
    ensure_department_access(access, "Warehouse")


async def get_order(db: AsyncSession, po_number: str) -> PurchaseOrder:
    order = (
        await db.execute(
            select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(PurchaseOrder.po_number == po_number)
        )
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    return order


async def order_response(db: AsyncSession, order: PurchaseOrder, access: PurchasingAccess) -> PurchaseOrderResponse:
    creator = await db.get(User, order.created_by)
    reviewer = await db.get(User, order.reviewed_by) if order.reviewed_by else None
    waiting = order.status == PurchaseOrderStatus.waiting_review
    creator_name = f"{creator.first_name} {creator.last_name}".strip() if creator else order.created_by
    reviewer_name = f"{reviewer.first_name} {reviewer.last_name}".strip() if reviewer else None
    item_responses = [
        PurchaseOrderItemResponse(
            id=item.id,
            line_number=item.line_number,
            product_code=item.product_code,
            sales_order_item_id=item.sales_order_item_id,
            process_from_code=item.process_from_code,
            process_to_code=item.process_to_code,
            part_name=item.part_name,
            part_no=item.part_no,
            description=item.description,
            quantity_grams=item.quantity_grams,
            unit=item.unit,
            received_quantity=item.received_quantity,
            outstanding_quantity=max(item.quantity_grams - item.received_quantity, Decimal("0")),
            excess_quantity=max(item.received_quantity - item.quantity_grams, Decimal("0")),
            unit_price=item.unit_price,
            amount=item.amount,
            remark=item.remark,
        )
        for item in order.items
    ]
    return PurchaseOrderResponse(
        po_number=order.po_number,
        sales_order_number=order.sales_order_number,
        order_kind=order.order_kind,
        po_date=order.po_date,
        supplier_code=order.supplier_code,
        supplier_name=order.supplier_name,
        supplier_address=order.supplier_address,
        supplier_phone=order.supplier_phone,
        supplier_contact_person=order.supplier_contact_person,
        quotation_reference=order.quotation_reference,
        quotation_date=order.quotation_date,
        requested_delivery_date=order.requested_delivery_date,
        delivery_plant_code=order.delivery_plant_code,
        delivery_plant_name=order.delivery_plant_name,
        delivery_address=order.delivery_address,
        notes=order.notes,
        payment_terms_days=order.payment_terms_days,
        payment_due_date=order.payment_due_date,
        currency=order.currency,
        subtotal=order.subtotal,
        discount_amount=order.discount_amount,
        ppn_rate=order.ppn_rate,
        ppn_amount=order.ppn_amount,
        pph23_rate=order.pph23_rate,
        pph23_amount=order.pph23_amount,
        grand_total=order.grand_total,
        status=order.status,
        fulfillment_status=order.fulfillment_status,
        department_code=order.department_code,
        created_by=order.created_by,
        created_by_name=creator_name,
        reviewed_by=order.reviewed_by,
        reviewed_by_name=reviewer_name,
        reviewed_at=order.reviewed_at,
        rejection_reason=order.rejection_reason,
        can_edit=order.status != PurchaseOrderStatus.rejected,
        can_delete=waiting,
        can_review=waiting and access.can_review,
        creator_qr_payload=signed_document_payload(
            "purchase_order", order.po_number, "created", order.created_by, creator_name, order.created_at
        ),
        approval_qr_payload=(
            signed_document_payload(
                "purchase_order",
                order.po_number,
                "approved",
                order.reviewed_by,
                reviewer_name or order.reviewed_by,
                order.reviewed_at,
            )
            if order.status == PurchaseOrderStatus.approved and order.reviewed_by and order.reviewed_at
            else None
        ),
        items=item_responses,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


async def apply_order_data(
    db: AsyncSession,
    order: PurchaseOrder,
    data: PurchaseOrderCreate | PurchaseOrderUpdate,
) -> None:
    sales_order = None
    if data.sales_order_number:
        sales_order = (
            await db.execute(
                select(SalesOrder)
                .options(selectinload(SalesOrder.items))
                .where(SalesOrder.sales_order_number == data.sales_order_number)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not sales_order or sales_order.status != SalesOrderStatus.approved:
            raise HTTPException(status_code=422, detail="PO must reference an approved Sales Order")
    elif order.sales_order_number is None and order.po_number:
        # Preserve the ability to edit historical POs without inventing an SO.
        sales_order = None
    else:
        raise HTTPException(status_code=422, detail="A Sales Order is required for every new Purchase Order")

    supplier = await db.get(Corporation, data.supplier_code)
    if not supplier or not supplier.is_supplier:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected corporation is not a supplier",
        )
    plant = await db.get(Plant, data.delivery_plant_code)
    if not plant:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected plant does not exist",
        )

    existing_by_id = {item.id: item for item in order.items}
    new_items: list[PurchaseOrderItem] = []
    amounts: list[Decimal] = []
    so_items_by_id = {item.id: item for item in sales_order.items} if sales_order else {}
    for line_number, item_data in enumerate(data.items, start=1):
        product = await db.get(Product, item_data.product_code)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Product {item_data.product_code} does not exist",
            )
        if data.order_kind != PurchaseOrderKind.subcontract and product.supplier_code != supplier.code:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Product {product.code} is not registered for supplier {supplier.code}",
            )
        so_item = so_items_by_id.get(item_data.sales_order_item_id) if item_data.sales_order_item_id else None
        if sales_order and not so_item:
            raise HTTPException(status_code=422, detail="Every PO line must be linked to an item on its Sales Order")
        if so_item:
            if data.order_kind == PurchaseOrderKind.subcontract and product.code != so_item.product_code:
                raise HTTPException(
                    status_code=422, detail="Subcontract service lines must use the Sales Order product"
                )
            allocation = (
                await db.execute(
                    select(SalesOrderMaterialAllocation).where(
                        SalesOrderMaterialAllocation.sales_order_item_id == so_item.id,
                        SalesOrderMaterialAllocation.material_product_code == product.code,
                    )
                )
            ).scalar_one_or_none()
            if product.code != so_item.product_code and (
                not allocation or data.order_kind == PurchaseOrderKind.subcontract
            ):
                raise HTTPException(
                    status_code=422,
                    detail="PO product must be the Sales Order product or an allocated BOM material",
                )
            expected_unit = so_item.unit if product.code == so_item.product_code else allocation.unit
            if item_data.unit.value != expected_unit:
                raise HTTPException(
                    status_code=422, detail=f"Unit for {product.code} must match Sales Order/BOM unit {expected_unit}"
                )
            if data.order_kind == PurchaseOrderKind.subcontract:
                active_processes = set(
                    (
                        await db.execute(
                            select(WipProcess.code).where(
                                WipProcess.process_type == WipProcessType.production,
                                WipProcess.is_active.is_(True),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                if item_data.process_to_code not in active_processes or (
                    item_data.process_from_code and item_data.process_from_code not in active_processes
                ):
                    raise HTTPException(
                        status_code=422, detail="Subcontract stages must be active Production processes"
                    )

            if sales_order and product.code == so_item.product_code:
                demand = so_item.quantity_grams
            elif allocation:
                demand = allocation.required_quantity
            else:
                demand = None
            if demand is not None:
                allocated_elsewhere = await db.scalar(
                    select(func.coalesce(func.sum(PurchaseOrderItem.quantity_grams), 0))
                    .join(PurchaseOrder, PurchaseOrder.po_number == PurchaseOrderItem.purchase_order_number)
                    .where(
                        PurchaseOrderItem.sales_order_item_id == so_item.id,
                        PurchaseOrderItem.product_code == product.code,
                        PurchaseOrder.status != PurchaseOrderStatus.rejected,
                        PurchaseOrder.po_number != (order.po_number or ""),
                    )
                ) or Decimal("0")
                if allocated_elsewhere + item_data.quantity_grams > demand:
                    raise HTTPException(
                        status_code=409,
                        detail=f"PO quantity exceeds the remaining Sales Order demand for {product.code}",
                    )
        amount = calculate_line_amount(item_data.quantity_grams, item_data.unit_price)
        amounts.append(amount)
        existing = existing_by_id.pop(item_data.id, None) if item_data.id else None
        if item_data.id and not existing:
            raise HTTPException(status_code=422, detail="Purchase Order item does not belong to this order")
        if existing:
            if existing.product_code != product.code or existing.unit != item_data.unit.value:
                raise HTTPException(status_code=422, detail="Product and unit cannot change on an existing PO line")
            existing.line_number = line_number
            existing.quantity_grams = item_data.quantity_grams
            existing.unit_price = item_data.unit_price
            existing.amount = amount
            existing.remark = item_data.remark
            existing.sales_order_item_id = item_data.sales_order_item_id
            existing.process_from_code = item_data.process_from_code
            existing.process_to_code = item_data.process_to_code
            new_items.append(existing)
        else:
            new_items.append(
                PurchaseOrderItem(
                    line_number=line_number,
                    product_code=product.code,
                    sales_order_item_id=item_data.sales_order_item_id,
                    process_from_code=item_data.process_from_code,
                    process_to_code=item_data.process_to_code,
                    part_name=product.part_name,
                    part_no=product.part_no,
                    description=product.description,
                    quantity_grams=item_data.quantity_grams,
                    unit=item_data.unit.value,
                    received_quantity=Decimal("0"),
                    unit_price=item_data.unit_price,
                    amount=amount,
                    remark=item_data.remark,
                )
            )

    for removed in existing_by_id.values():
        if removed.received_quantity > 0:
            raise HTTPException(status_code=422, detail="A PO line with Receiving history cannot be removed")
        await db.delete(removed)

    try:
        totals = calculate_purchase_totals(amounts, data.discount_amount, data.ppn_rate, data.pph23_rate)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    order.sales_order_number = sales_order.sales_order_number if sales_order else None
    order.order_kind = data.order_kind
    order.po_date = data.po_date
    order.supplier_code = supplier.code
    order.supplier_name = supplier.name
    order.supplier_address = supplier.address
    order.supplier_phone = supplier.phone_number
    order.supplier_contact_person = supplier.contact_person_name
    order.quotation_reference = data.quotation_reference
    order.quotation_date = data.quotation_date
    order.requested_delivery_date = data.requested_delivery_date
    order.delivery_plant_code = plant.code
    order.delivery_plant_name = plant.name
    order.delivery_address = plant.full_address
    order.notes = data.notes
    order.payment_terms_days = data.payment_terms_days
    order.payment_due_date = payment_due_date(data.po_date, data.payment_terms_days)
    order.currency = "IDR"
    order.subtotal = totals.subtotal
    order.discount_amount = totals.discount_amount
    order.ppn_rate = data.ppn_rate
    order.ppn_amount = totals.ppn_amount
    order.pph23_rate = data.pph23_rate
    order.pph23_amount = totals.pph23_amount
    order.grand_total = totals.grand_total
    order.items = new_items
    order.fulfillment_status = (
        FulfillmentStatus.closed
        if new_items and all(item.received_quantity >= item.quantity_grams for item in new_items)
        else FulfillmentStatus.open
    )


async def commit_order(db: AsyncSession, order: PurchaseOrder) -> None:
    try:
        await db.commit()
        await db.refresh(order)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Purchase order data conflicts with an existing record",
        ) from exc


@router.get("", response_model=PaginatedPurchaseOrders)
async def list_purchase_orders(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    order_status: PurchaseOrderStatus | None = Query(default=None, alias="status"),
    fulfillment_status: FulfillmentStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedPurchaseOrders:
    access = await current_access(db, current_user)
    filters = [PurchaseOrder.department_code == settings.purchasing_department_code]
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                PurchaseOrder.po_number.ilike(term),
                PurchaseOrder.supplier_code.ilike(term),
                PurchaseOrder.supplier_name.ilike(term),
            )
        )
    if order_status:
        filters.append(PurchaseOrder.status == order_status)
    if fulfillment_status:
        filters.append(PurchaseOrder.fulfillment_status == fulfillment_status)
    if date_from:
        filters.append(PurchaseOrder.po_date >= date_from)
    if date_to:
        filters.append(PurchaseOrder.po_date <= date_to)
    query = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(*filters)
        .order_by(PurchaseOrder.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    orders = list((await db.execute(query)).scalars().all())
    total = (await db.execute(select(func.count()).select_from(PurchaseOrder).where(*filters))).scalar_one()
    return PaginatedPurchaseOrders(
        items=[await order_response(db, order, access) for order in orders],
        total=total,
        page=page,
        size=size,
    )


@router.post("", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PurchaseOrderResponse:
    access = await current_access(db, current_user)
    if not data.sales_order_number:
        raise HTTPException(status_code=422, detail="A Sales Order is required for every Purchase Order")
    order = PurchaseOrder(
        po_number=await generate_purchase_order_number(db, data.po_date),
        status=PurchaseOrderStatus.waiting_review,
        fulfillment_status=FulfillmentStatus.open,
        department_code=settings.purchasing_department_code,
        created_by=current_user.id,
    )
    await apply_order_data(db, order, data)
    db.add(order)
    await commit_order(db, order)
    order = await get_order(db, order.po_number)
    return await order_response(db, order, access)


@router.get("/sales-orders-for-po")
async def sales_orders_for_purchase_order(
    size: int = Query(default=100, ge=1, le=100),
    exclude_po_number: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    """Approved SO candidates with output/BOM quantities still available for PO allocation."""
    await current_access(db, current_user)
    orders = (
        (
            await db.execute(
                select(SalesOrder)
                .options(selectinload(SalesOrder.items))
                .where(
                    SalesOrder.status == SalesOrderStatus.approved,
                    SalesOrder.fulfillment_status == FulfillmentStatus.open,
                )
                .order_by(SalesOrder.created_at.desc())
                .limit(size)
            )
        )
        .scalars()
        .all()
    )
    result: list[dict[str, object]] = []
    active_processes = (
        await db.execute(
            select(WipProcess.code, WipProcess.name)
            .where(
                WipProcess.process_type == WipProcessType.production,
                WipProcess.is_active.is_(True),
            )
            .order_by(WipProcess.code)
        )
    ).all()
    process_stages = [{"code": code, "name": name} for code, name in active_processes]
    for order in orders:
        candidates: list[dict[str, object]] = []
        for so_item in order.items:
            materials = (
                (
                    await db.execute(
                        select(SalesOrderMaterialAllocation)
                        .where(SalesOrderMaterialAllocation.sales_order_item_id == so_item.id)
                        .order_by(SalesOrderMaterialAllocation.id)
                    )
                )
                .scalars()
                .all()
            )
            demand_rows = sales_order_po_demand_rows(
                so_item.product_code,
                so_item.quantity_grams,
                so_item.delivered_quantity,
                so_item.unit,
                materials,
            )
            for product_code, demand, unit, is_output in demand_rows:
                if demand <= 0:
                    continue
                already = await db.scalar(
                    select(func.coalesce(func.sum(PurchaseOrderItem.quantity_grams), 0))
                    .join(PurchaseOrder, PurchaseOrder.po_number == PurchaseOrderItem.purchase_order_number)
                    .where(
                        PurchaseOrderItem.sales_order_item_id == so_item.id,
                        PurchaseOrderItem.product_code == product_code,
                        PurchaseOrder.status != PurchaseOrderStatus.rejected,
                        *([PurchaseOrder.po_number != exclude_po_number] if exclude_po_number else []),
                    )
                ) or Decimal("0")
                available = demand - already
                if available <= 0:
                    continue
                product = await db.get(Product, product_code)
                if not product:
                    continue
                candidates.append(
                    {
                        "sales_order_item_id": so_item.id,
                        "product_code": product.code,
                        "product_name": product.part_name,
                        "description": product.description,
                        "quantity": available,
                        "unit": unit,
                        "is_output": is_output,
                        "process_stages": process_stages,
                    }
                )
        if candidates:
            result.append(
                {
                    "sales_order_number": order.sales_order_number,
                    "customer_po_number": order.customer_po_number,
                    "customer_name": order.customer_name,
                    "items": candidates,
                }
            )
    return {"items": result}


@router.post("/{po_number}/subcontract-dispatches", response_model=SubcontractDispatchResponse, status_code=201)
async def create_subcontract_dispatch(
    po_number: str,
    data: SubcontractDispatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubcontractDispatchResponse:
    """Send SO-owned material/WIP from our stock to the approved subcontractor."""
    await warehouse_access(db, current_user)
    row = (
        await db.execute(
            select(PurchaseOrderItem, PurchaseOrder, SalesOrderItem)
            .join(PurchaseOrder, PurchaseOrder.po_number == PurchaseOrderItem.purchase_order_number)
            .join(SalesOrderItem, SalesOrderItem.id == PurchaseOrderItem.sales_order_item_id)
            .where(PurchaseOrder.po_number == po_number, PurchaseOrderItem.id == data.purchase_order_item_id)
            .with_for_update()
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Linked Purchase Order item not found")
    item, order, so_item = row
    if order.status != PurchaseOrderStatus.approved or order.order_kind != PurchaseOrderKind.subcontract:
        raise HTTPException(status_code=409, detail="Only an approved subcontract PO can be dispatched")
    if not item.process_to_code or data.process_to_code != item.process_to_code:
        raise HTTPException(status_code=422, detail="Dispatch next process must match the subcontract PO")
    if item.process_from_code and data.source_process_code != item.process_from_code:
        raise HTTPException(status_code=422, detail="Dispatch source process must match the subcontract PO")

    lot = None
    wip_job = None
    if data.source_lot_id is not None:
        lot = (
            await db.execute(select(ProductLot).where(ProductLot.id == data.source_lot_id).with_for_update())
        ).scalar_one_or_none()
        if not lot:
            raise HTTPException(status_code=404, detail="Source stock lot not found")
        source_product_code = lot.product_code
        source_unit = lot.unit
        source_lot_number = lot.lot_number
        source_quantity = lot.current_quantity_grams
    else:
        wip_job = (
            await db.execute(select(WipLotJob).where(WipLotJob.id == data.source_wip_job_id).with_for_update())
        ).scalar_one_or_none()
        if not wip_job or wip_job.status in {WipLotStatus.completed, WipLotStatus.reversed, WipLotStatus.subcontracted}:
            raise HTTPException(status_code=404, detail="Available WIP job not found")
        if not data.source_process_code or data.source_process_code != wip_job.process_code:
            raise HTTPException(status_code=422, detail="WIP source process must match the selected WIP job")
        source_product_code = wip_job.product_code
        source_unit = wip_job.unit
        source_lot_number = wip_job.lot_number
        source_quantity = wip_job.current_quantity
    source_product = await db.get(Product, source_product_code)
    if not source_product:
        raise HTTPException(status_code=404, detail="Source product not found")
    material_linked = source_product_code == so_item.product_code or (
        await db.scalar(
            select(func.count())
            .select_from(SalesOrderMaterialAllocation)
            .where(
                SalesOrderMaterialAllocation.sales_order_item_id == so_item.id,
                SalesOrderMaterialAllocation.material_product_code == source_product_code,
            )
        )
    )
    if not material_linked:
        raise HTTPException(status_code=422, detail="Source product is not part of the linked SO/BOM")
    try:
        require_whole_quantity(data.quantity, source_unit)
        require_whole_quantity(data.expected_output_quantity, item.unit, "Expected output")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    moved = to_inventory_quantity(data.quantity, source_unit)
    dispatch_quantity = moved if lot else data.quantity
    dispatch_unit = inventory_unit(source_unit) if lot else source_unit
    if dispatch_quantity > source_quantity:
        raise HTTPException(status_code=409, detail="Dispatch quantity exceeds available source quantity")
    if wip_job and wip_job.sales_order_item_id != so_item.id:
        raise HTTPException(status_code=422, detail="WIP source does not belong to this Sales Order item")
    outstanding_dispatches = await db.scalar(
        select(
            func.coalesce(
                func.sum(SubcontractDispatch.expected_output_quantity - SubcontractDispatch.returned_quantity), 0
            )
        ).where(
            SubcontractDispatch.purchase_order_item_id == item.id,
            SubcontractDispatch.status != SubcontractDispatchStatus.reversed,
        )
    ) or Decimal("0")
    if outstanding_dispatches + item.received_quantity + data.expected_output_quantity > item.quantity_grams:
        raise HTTPException(status_code=409, detail="Dispatch output exceeds the subcontract PO quantity")

    if lot:
        product = (
            await db.execute(select(Product).where(Product.code == lot.product_code).with_for_update())
        ).scalar_one()
        product_after, lot_after = apply_stock_delta(product.current_stock_grams, lot.current_quantity_grams, -moved)
        product.current_stock_grams = product_after
        lot.current_quantity_grams = lot_after
    else:
        # WIP already left warehouse stock when its production transfer posted;
        # dispatch only decrements the WIP job ledger, avoiding a second stock deduction.
        wip_job.current_quantity -= data.quantity
        if wip_job.current_quantity <= 0:
            wip_job.current_quantity = Decimal("0")
            wip_job.status = WipLotStatus.subcontracted
    dispatch = SubcontractDispatch(
        dispatch_number=f"SCD-{datetime.now(timezone.utc):%y%m%d}-{uuid4().hex[:8].upper()}",
        purchase_order_item_id=item.id,
        source_lot_id=lot.id if lot else None,
        source_wip_job_id=wip_job.id if wip_job else None,
        product_code=source_product_code,
        lot_number=source_lot_number,
        quantity=dispatch_quantity,
        unit=dispatch_unit,
        expected_output_quantity=data.expected_output_quantity,
        source_process_code=data.source_process_code,
        process_to_code=data.process_to_code,
        subcontractor_code=order.supplier_code,
        status=SubcontractDispatchStatus.dispatched,
        returned_quantity=Decimal("0"),
        notes=data.notes,
        dispatched_by=current_user.id,
    )
    db.add(dispatch)
    await db.flush()
    if lot:
        db.add(
            InventoryMovement(
                movement_type=InventoryMovementType.warehouse_out,
                product_code=product.code,
                lot_id=lot.id,
                unit=inventory_unit(lot.unit),
                quantity_grams=-moved,
                product_stock_after_grams=product_after,
                lot_stock_after_grams=lot_after,
                reference_type="subcontract_dispatch",
                reference_number=dispatch.dispatch_number,
                performed_by=current_user.id,
                notes=data.notes,
            )
        )
    await db.commit()
    await db.refresh(dispatch)
    return SubcontractDispatchResponse.model_validate(dispatch)


@router.get("/{po_number}/subcontract-dispatches", response_model=list[SubcontractDispatchResponse])
async def list_subcontract_dispatches(
    po_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SubcontractDispatchResponse]:
    await current_access(db, current_user)
    order = await get_order(db, po_number)
    if order.order_kind != PurchaseOrderKind.subcontract:
        raise HTTPException(status_code=409, detail="Purchase Order is not a subcontract order")
    rows = await db.execute(
        select(SubcontractDispatch)
        .join(PurchaseOrderItem, PurchaseOrderItem.id == SubcontractDispatch.purchase_order_item_id)
        .where(PurchaseOrderItem.purchase_order_number == po_number)
        .order_by(SubcontractDispatch.dispatched_at, SubcontractDispatch.id)
    )
    return [SubcontractDispatchResponse.model_validate(row) for row in rows.scalars().all()]


@router.get("/subcontract-source-lots")
async def subcontract_source_lots(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    await warehouse_access(db, current_user)
    lots = (
        await db.execute(
            select(ProductLot, Product)
            .join(Product, Product.code == ProductLot.product_code)
            .where(ProductLot.current_quantity_grams > 0)
            .order_by(Product.part_name, ProductLot.lot_number)
            .limit(500)
        )
    ).all()
    jobs = (
        await db.execute(
            select(WipLotJob, Product)
            .join(Product, Product.code == WipLotJob.product_code)
            .where(
                WipLotJob.current_quantity > 0,
                WipLotJob.status.not_in([WipLotStatus.completed, WipLotStatus.reversed, WipLotStatus.subcontracted]),
            )
            .order_by(Product.part_name, WipLotJob.created_at)
            .limit(500)
        )
    ).all()
    return {
        "items": [
            {
                "source_type": "stock_lot",
                "source_id": lot.id,
                "product_code": lot.product_code,
                "product_name": product.part_name,
                "lot_number": lot.lot_number,
                "quantity": lot.current_quantity_grams,
                "unit": lot.unit,
                "process_code": None,
            }
            for lot, product in lots
        ]
        + [
            {
                "source_type": "wip_job",
                "source_id": job.id,
                "product_code": job.product_code,
                "product_name": product.part_name,
                "lot_number": job.lot_segment_code,
                "quantity": job.current_quantity,
                "unit": job.unit,
                "process_code": job.process_code,
            }
            for job, product in jobs
        ]
    }


@router.get("/subcontract-orders-for-dispatch", response_model=PaginatedPurchaseOrders)
async def subcontract_orders_for_dispatch(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedPurchaseOrders:
    """Approved subcontract POs with quantity still available to dispatch to Warehouse users."""
    await warehouse_access(db, current_user)
    filters = [
        PurchaseOrder.order_kind == PurchaseOrderKind.subcontract,
        PurchaseOrder.status == PurchaseOrderStatus.approved,
    ]
    orders = list(
        (
            await db.execute(
                select(PurchaseOrder)
                .options(selectinload(PurchaseOrder.items))
                .where(*filters)
                .order_by(PurchaseOrder.reviewed_at, PurchaseOrder.po_number)
            )
        )
        .scalars()
        .all()
    )
    if not orders:
        return PaginatedPurchaseOrders(items=[], total=0, page=page, size=size)

    item_ids = [item.id for order in orders for item in order.items]
    dispatched_rows = await db.execute(
        select(
            SubcontractDispatch.purchase_order_item_id,
            func.coalesce(
                func.sum(SubcontractDispatch.expected_output_quantity - SubcontractDispatch.returned_quantity), 0
            ),
        )
        .where(
            SubcontractDispatch.purchase_order_item_id.in_(item_ids),
            SubcontractDispatch.status != SubcontractDispatchStatus.reversed,
        )
        .group_by(SubcontractDispatch.purchase_order_item_id)
    )
    dispatched_by_item = {item_id: Decimal(str(quantity)) for item_id, quantity in dispatched_rows.all()}
    available_responses: list[PurchaseOrderResponse] = []
    for order in orders:
        eligible_items = []
        for item in order.items:
            available = max(
                item.quantity_grams - item.received_quantity - dispatched_by_item.get(item.id, Decimal("0")),
                Decimal("0"),
            )
            if available > 0:
                eligible_items.append((item, available))
        if eligible_items:
            response = await order_response(db, order, resolve_purchasing_access(current_user, None))
            response.can_edit = False
            response.can_delete = False
            response.can_review = False
            eligible_ids = {item.id for item, _ in eligible_items}
            response.items = [item for item in response.items if item.id in eligible_ids]
            for response_item in response.items:
                response_item.outstanding_quantity = next(
                    available for item, available in eligible_items if item.id == response_item.id
                )
            available_responses.append(response)

    return PaginatedPurchaseOrders(
        items=available_responses[(page - 1) * size : page * size],
        total=len(available_responses),
        page=page,
        size=size,
    )


@router.get("/{po_number}", response_model=PurchaseOrderResponse)
async def get_purchase_order(
    po_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PurchaseOrderResponse:
    access = await current_access(db, current_user)
    return await order_response(db, await get_order(db, po_number), access)


@router.get("/{po_number}/pdf")
async def download_purchase_order_pdf(
    po_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    access = await current_access(db, current_user)
    response = await order_response(db, await get_order(db, po_number), access)
    content = purchase_order_pdf_bytes(response)
    safe_number = po_number.replace("/", "-")
    return StreamingResponse(
        iter([content]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="purchase-order-{safe_number}.pdf"'},
    )


@router.patch("/{po_number}", response_model=PurchaseOrderResponse)
async def update_purchase_order(
    po_number: str,
    data: PurchaseOrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PurchaseOrderResponse:
    access = await current_access(db, current_user)
    order = await get_order(db, po_number)
    if order.status == PurchaseOrderStatus.rejected:
        raise HTTPException(status_code=409, detail="Rejected Purchase Order cannot be edited")
    await apply_order_data(db, order, data)
    await commit_order(db, order)
    return await order_response(db, await get_order(db, po_number), access)


@router.delete("/{po_number}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase_order(
    po_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    await current_access(db, current_user)
    order = await get_order(db, po_number)
    ensure_waiting_review(order.status)
    await db.delete(order)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{po_number}/approve", response_model=PurchaseOrderResponse)
async def approve_purchase_order(
    po_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PurchaseOrderResponse:
    access = await current_access(db, current_user)
    ensure_purchasing_head(access)
    order = await get_order(db, po_number)
    ensure_waiting_review(order.status)
    order.status = PurchaseOrderStatus.approved
    order.reviewed_by = current_user.id
    order.reviewed_at = datetime.now(timezone.utc)
    order.rejection_reason = None
    await commit_order(db, order)
    return await order_response(db, order, access)


@router.post("/{po_number}/reject", response_model=PurchaseOrderResponse)
async def reject_purchase_order(
    po_number: str,
    data: PurchaseOrderRejection,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PurchaseOrderResponse:
    access = await current_access(db, current_user)
    ensure_purchasing_head(access)
    order = await get_order(db, po_number)
    ensure_waiting_review(order.status)
    order.status = PurchaseOrderStatus.rejected
    order.fulfillment_status = FulfillmentStatus.closed
    order.reviewed_by = current_user.id
    order.reviewed_at = datetime.now(timezone.utc)
    order.rejection_reason = data.reason
    await commit_order(db, order)
    return await order_response(db, order, access)


@router.get("/verification/qr/{token}")
async def verify_purchase_order_qr(token: str, current_user: User = Depends(get_current_user)) -> dict[str, object]:
    del current_user
    try:
        return {"valid": True, **verify_document_payload(token)}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR payload") from exc
