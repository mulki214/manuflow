from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.inventory_services import apply_stock_delta, grams
from app.logistics_services import delivery_number, finish_good_number
from app.models import (
    Delivery,
    DeliveryLine,
    DeliveryStatus,
    Department,
    FinishGoodReceipt,
    FinishGoodStatus,
    FulfillmentStatus,
    Plant,
    Product,
    ProductLot,
    SalesOrder,
    SalesOrderItem,
    StorageLocation,
    Transportation,
    User,
    WarehouseStorage,
    WipLotJob,
    WipLotStatus,
)
from app.module_permissions import resolve_department_membership
from app.operational_services import (
    WEIGHT_UNITS,
    display_quantity,
    inventory_unit,
    require_whole_quantity,
    shipment_weight_kg,
    to_inventory_quantity,
)
from app.schemas import (
    DeliveryBatchCreate,
    DeliveryConfirm,
    DeliveryCreate,
    DeliveryLineResponse,
    DeliveryResponse,
    DeliveryReverse,
    FinishGoodPostCreate,
    FinishGoodResponse,
    FinishGoodReverse,
    PaginatedDeliveries,
    PaginatedFinishGoods,
)

finish_router = APIRouter(prefix="/finish-goods", tags=["Finish Goods"])
delivery_router = APIRouter(prefix="/delivery", tags=["Delivery"])


async def warehouse_access(db: AsyncSession, user: User) -> None:
    access = resolve_department_membership(user, await db.get(Department, settings.warehouse_department_code))
    if not access.can_access:
        raise HTTPException(status_code=403, detail="Only active Warehouse department members can access Finish Goods")


def finish_response(r: FinishGoodReceipt) -> FinishGoodResponse:
    return FinishGoodResponse(
        receipt_number=r.receipt_number,
        receipt_date=r.receipt_date,
        product_code=r.product_code,
        lot_number=r.lot_number,
        quantity=r.quantity,
        unit=r.unit,
        plant_code=r.plant_code,
        storage_location_code=r.storage_location_code,
        status=r.status.value,
        can_reverse=r.status == FinishGoodStatus.posted,
        created_at=r.created_at,
    )


def delivery_response(r: Delivery, lines: list[DeliveryLine] | None = None) -> DeliveryResponse:
    lines = lines or [
        DeliveryLine(
            delivery_number=r.delivery_number,
            sales_order_item_id=r.sales_order_item_id,
            lot_id=r.lot_id,
            product_code=r.product_code,
            lot_number=r.lot_number,
            quantity=r.quantity,
            unit=r.unit,
        )
    ]
    return DeliveryResponse(
        delivery_number=r.delivery_number,
        delivery_date=r.delivery_date,
        sales_order_number=r.sales_order_number,
        customer_name=r.customer_name,
        product_code=r.product_code,
        lot_number=r.lot_number,
        quantity=r.quantity,
        unit=r.unit,
        vehicle_number=r.vehicle_number,
        transportation_code=r.transportation_code,
        driver_name=r.driver_name,
        notes=r.notes,
        status="delivered" if r.status == DeliveryStatus.posted else r.status.value,
        can_reverse=r.status in {DeliveryStatus.dispatched, DeliveryStatus.delivered, DeliveryStatus.posted},
        can_confirm_delivery=r.status == DeliveryStatus.dispatched,
        delivered_at=r.delivered_at,
        created_at=r.created_at,
        lines=[
            DeliveryLineResponse(
                sales_order_item_id=line.sales_order_item_id,
                product_code=line.product_code,
                lot_id=line.lot_id,
                lot_number=line.lot_number,
                quantity=line.quantity,
                unit=line.unit,
            )
            for line in lines
        ],
    )


async def delivery_lines(db: AsyncSession, record: Delivery) -> list[DeliveryLine]:
    """Return detail rows, with a one-line fallback for documents posted before batch support."""
    return list(
        (
            await db.execute(
                select(DeliveryLine)
                .where(DeliveryLine.delivery_number == record.delivery_number)
                .order_by(DeliveryLine.id)
            )
        )
        .scalars()
        .all()
    )


@finish_router.get("/queue")
async def finish_queue(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[dict]:
    await warehouse_access(db, current_user)
    jobs = list(
        (await db.execute(select(WipLotJob).where(WipLotJob.status == WipLotStatus.awaiting_finish_goods)))
        .scalars()
        .all()
    )
    return [
        {
            "job_id": j.id,
            "product_code": j.product_code,
            "lot_number": j.lot_number,
            "lot_segment_code": j.lot_segment_code,
            "quantity": j.current_quantity,
            "unit": j.unit,
            "plant_code": j.plant_code,
        }
        for j in jobs
    ]


@finish_router.get("/stock-lots")
async def finish_good_stock_lots(
    product_code: str | None = Query(default=None),
    plant_code: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return every positive lot physically held in Finished Goods storage.

    This includes lots posted after QC as well as lots transferred directly
    from Warehouse, so the Finish Good module remains the single stock view.
    """
    await warehouse_access(db, current_user)
    filters = [
        ProductLot.current_quantity_grams > 0,
        WarehouseStorage.storage_type == "finished_goods",
    ]
    if product_code:
        filters.append(ProductLot.product_code == product_code)
    if plant_code:
        filters.append(ProductLot.plant_code == plant_code)
    rows = list(
        (
            await db.execute(
                select(ProductLot, Product, Plant, StorageLocation, WarehouseStorage)
                .join(Product, Product.code == ProductLot.product_code)
                .join(Plant, Plant.code == ProductLot.plant_code)
                .join(StorageLocation, StorageLocation.code == ProductLot.storage_location_code)
                .join(WarehouseStorage, WarehouseStorage.code == StorageLocation.storage_code)
                .where(*filters)
                .order_by(Product.part_name, ProductLot.lot_number, ProductLot.id)
            )
        ).all()
    )
    return [
        {
            "lot_id": lot.id,
            "product_code": product.code,
            "product_name": product.part_name,
            "description": product.description,
            "lot_number": lot.lot_number,
            "quantity": display_quantity(lot.current_quantity_grams, lot.unit),
            "unit": lot.unit,
            "plant_code": plant.code,
            "plant_name": plant.name,
            "storage_location_code": location.code,
            "storage_location_name": location.name,
            "storage_name": storage.name,
        }
        for lot, product, plant, location, storage in rows
    ]


@finish_router.post("/queue/{job_id}/post", response_model=FinishGoodResponse, status_code=status.HTTP_201_CREATED)
async def post_finish_good(
    job_id: int,
    data: FinishGoodPostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FinishGoodResponse:
    await warehouse_access(db, current_user)
    job = (await db.execute(select(WipLotJob).where(WipLotJob.id == job_id).with_for_update())).scalar_one_or_none()
    if not job or job.status != WipLotStatus.awaiting_finish_goods:
        raise HTTPException(status_code=409, detail="WIP Job is not available for Finish Good posting")
    location = await db.get(StorageLocation, data.storage_location_code)
    storage = await db.get(WarehouseStorage, location.storage_code) if location else None
    if (
        not location
        or not storage
        or location.plant_code != job.plant_code
        or storage.storage_type.value != "finished_goods"
    ):
        raise HTTPException(
            status_code=422, detail="Storage Location must be a Finished Goods location in the same Plant"
        )
    product = await db.get(Product, job.product_code)
    lot = (
        await db.execute(
            select(ProductLot)
            .where(
                ProductLot.product_code == job.product_code,
                ProductLot.lot_number == job.lot_number,
                ProductLot.storage_location_code == location.code,
                ProductLot.unit == job.unit,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    lot_current = lot.current_quantity_grams if lot else Decimal("0")
    product_after, lot_after = apply_stock_delta(product.current_stock_grams, lot_current, job.current_quantity)
    if not lot:
        lot = ProductLot(
            product_code=job.product_code,
            lot_number=job.lot_number,
            plant_code=job.plant_code,
            storage_location_code=location.code,
            unit=job.unit,
            initial_quantity_grams=job.current_quantity,
            current_quantity_grams=lot_after,
        )
        db.add(lot)
        await db.flush()
    else:
        lot.initial_quantity_grams += job.current_quantity
        lot.current_quantity_grams = lot_after
    record = FinishGoodReceipt(
        receipt_number=await finish_good_number(db, data.receipt_date),
        receipt_date=data.receipt_date,
        source_wip_job_id=job.id,
        product_code=job.product_code,
        lot_number=job.lot_number,
        lot_segment_code=job.lot_segment_code,
        quantity=job.current_quantity,
        unit=job.unit,
        plant_code=job.plant_code,
        storage_location_code=location.code,
        lot_id=lot.id,
        status=FinishGoodStatus.posted,
        notes=data.notes,
        performed_by=current_user.id,
    )
    product.current_stock_grams = product_after
    job.status = WipLotStatus.completed
    job.current_quantity = Decimal("0")
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return finish_response(record)


@finish_router.get("", response_model=PaginatedFinishGoods)
async def list_finish_goods(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    receipt_status: FinishGoodStatus | None = Query(default=None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedFinishGoods:
    await warehouse_access(db, current_user)
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                FinishGoodReceipt.receipt_number.ilike(term),
                FinishGoodReceipt.product_code.ilike(term),
                FinishGoodReceipt.lot_number.ilike(term),
            )
        )
    if receipt_status:
        filters.append(FinishGoodReceipt.status == receipt_status)
    if date_from:
        filters.append(FinishGoodReceipt.receipt_date >= date_from)
    if date_to:
        filters.append(FinishGoodReceipt.receipt_date <= date_to)
    records = list(
        (
            await db.execute(
                select(FinishGoodReceipt)
                .where(*filters)
                .order_by(FinishGoodReceipt.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .scalars()
        .all()
    )
    total = await db.scalar(select(func.count()).select_from(FinishGoodReceipt).where(*filters))
    return PaginatedFinishGoods(items=[finish_response(r) for r in records], total=total or 0, page=page, size=size)


@finish_router.post("/{receipt_number}/reverse", response_model=FinishGoodResponse)
async def reverse_finish_good(
    receipt_number: str,
    data: FinishGoodReverse,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FinishGoodResponse:
    """Reverse a Finish Good posting only while its exact lot quantity is still available."""
    await warehouse_access(db, current_user)
    receipt = (
        await db.execute(
            select(FinishGoodReceipt).where(FinishGoodReceipt.receipt_number == receipt_number).with_for_update()
        )
    ).scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Finish Good receipt not found")
    if receipt.status != FinishGoodStatus.posted:
        raise HTTPException(status_code=409, detail="Finish Good receipt has already been reversed")
    lot = (await db.execute(select(ProductLot).where(ProductLot.id == receipt.lot_id).with_for_update())).scalar_one()
    product = await db.get(Product, receipt.product_code)
    job = (
        await db.execute(select(WipLotJob).where(WipLotJob.id == receipt.source_wip_job_id).with_for_update())
    ).scalar_one()
    if lot.current_quantity_grams < receipt.quantity:
        raise HTTPException(
            status_code=409,
            detail="Finish Good stock has already been consumed and cannot be reversed",
        )
    product_after, lot_after = apply_stock_delta(
        product.current_stock_grams, lot.current_quantity_grams, -receipt.quantity
    )
    product.current_stock_grams = product_after
    lot.current_quantity_grams = lot_after
    job.status = WipLotStatus.awaiting_finish_goods
    job.current_quantity = receipt.quantity
    receipt.status = FinishGoodStatus.reversed
    receipt.reversed_by = current_user.id
    receipt.reversal_reason = data.reason.strip()
    receipt.reversed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(receipt)
    return finish_response(receipt)


async def create_delivery_batch_record(
    data: DeliveryBatchCreate, db: AsyncSession, current_user: User
) -> tuple[Delivery, list[DeliveryLine]]:
    """Validate first, then post the whole delivery in one database commit."""
    item_ids = sorted({line.sales_order_item_id for line in data.lines})
    lot_ids = sorted({line.lot_id for line in data.lines})
    items = list(
        (
            await db.execute(
                select(SalesOrderItem)
                .where(SalesOrderItem.id.in_(item_ids))
                .order_by(SalesOrderItem.id)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    lots = list(
        (
            await db.execute(
                select(ProductLot).where(ProductLot.id.in_(lot_ids)).order_by(ProductLot.id).with_for_update()
            )
        )
        .scalars()
        .all()
    )
    if len(items) != len(item_ids) or len(lots) != len(lot_ids):
        raise HTTPException(status_code=404, detail="Sales Order Item or Finish Good Lot not found")
    items_by_id = {item.id: item for item in items}
    lots_by_id = {lot.id: lot for lot in lots}
    order_numbers = {item.sales_order_number for item in items}
    if len(order_numbers) != 1:
        raise HTTPException(status_code=422, detail="All delivery lines must belong to one Sales Order")
    order = (
        await db.execute(
            select(SalesOrder).where(SalesOrder.sales_order_number == order_numbers.pop()).with_for_update()
        )
    ).scalar_one_or_none()
    if not order or order.status.value != "approved":
        raise HTTPException(status_code=422, detail="Delivery must use an approved Sales Order")

    quantity_by_item: dict[int, Decimal] = {}
    inventory_by_lot: dict[int, Decimal] = {}
    inventory_by_product: dict[str, Decimal] = {}
    for line in data.lines:
        item, lot = items_by_id[line.sales_order_item_id], lots_by_id[line.lot_id]
        location = await db.get(StorageLocation, lot.storage_location_code)
        storage = await db.get(WarehouseStorage, location.storage_code) if location else None
        if (
            item.product_code != lot.product_code
            or not (item.unit == lot.unit or (item.unit in WEIGHT_UNITS and lot.unit == "gram"))
            or not storage
            or storage.storage_type.value != "finished_goods"
        ):
            raise HTTPException(status_code=422, detail="Each line must use matching Finished Goods stock")
        try:
            require_whole_quantity(line.quantity, item.unit)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        quantity_by_item[item.id] = quantity_by_item.get(item.id, Decimal("0")) + line.quantity
        inventory_quantity = to_inventory_quantity(line.quantity, item.unit)
        inventory_by_lot[lot.id] = inventory_by_lot.get(lot.id, Decimal("0")) + inventory_quantity
        inventory_by_product[item.product_code] = (
            inventory_by_product.get(item.product_code, Decimal("0")) + inventory_quantity
        )
    pending_rows = list(
        (
            await db.execute(
                select(DeliveryLine.sales_order_item_id, func.coalesce(func.sum(DeliveryLine.quantity), 0))
                .join(Delivery, Delivery.delivery_number == DeliveryLine.delivery_number)
                .where(
                    DeliveryLine.sales_order_item_id.in_(item_ids),
                    Delivery.status == DeliveryStatus.dispatched,
                )
                .group_by(DeliveryLine.sales_order_item_id)
            )
        ).all()
    )
    pending_by_item = {item_id: Decimal(str(quantity)) for item_id, quantity in pending_rows}
    if any(
        quantity_by_item[item.id]
        > grams(item.quantity_grams - item.delivered_quantity - pending_by_item.get(item.id, Decimal("0")))
        for item in items
    ):
        raise HTTPException(status_code=422, detail="Delivery quantity exceeds Sales Order outstanding")
    if any(inventory_by_lot[lot.id] > lot.current_quantity_grams for lot in lots):
        raise HTTPException(status_code=422, detail="Delivery quantity exceeds Finish Good stock")

    products = list(
        (
            await db.execute(
                select(Product).where(Product.code.in_(inventory_by_product)).order_by(Product.code).with_for_update()
            )
        )
        .scalars()
        .all()
    )
    products_by_code = {product.code: product for product in products}
    transportation = await db.get(Transportation, data.transportation_code) if data.transportation_code else None
    if data.transportation_code and (not transportation or not transportation.is_active):
        raise HTTPException(status_code=422, detail="Selected Transportation must be active")
    shipment_kg = sum(
        (
            shipment_weight_kg(
                line.quantity,
                items_by_id[line.sales_order_item_id].unit,
                products_by_code[items_by_id[line.sales_order_item_id].product_code].gross_weight,
            )
            for line in data.lines
        ),
        Decimal("0"),
    )
    if transportation and transportation.capacity is not None and shipment_kg > transportation.capacity:
        raise HTTPException(status_code=422, detail="Shipment weight exceeds vehicle capacity")

    for lot in lots:
        product = products_by_code[lot.product_code]
        product_after, lot_after = apply_stock_delta(
            product.current_stock_grams, lot.current_quantity_grams, -inventory_by_lot[lot.id]
        )
        product.current_stock_grams, lot.current_quantity_grams = product_after, lot_after
    first_line = data.lines[0]
    first_item, first_lot = items_by_id[first_line.sales_order_item_id], lots_by_id[first_line.lot_id]
    record = Delivery(
        delivery_number=await delivery_number(db, data.delivery_date),
        delivery_date=data.delivery_date,
        sales_order_item_id=first_item.id,
        sales_order_number=order.sales_order_number,
        customer_name=order.customer_name,
        product_code=first_item.product_code,
        lot_id=first_lot.id,
        lot_number=first_lot.lot_number,
        quantity=first_line.quantity,
        unit=first_item.unit,
        vehicle_number=transportation.vehicle_number if transportation else None,
        transportation_code=transportation.code if transportation else None,
        driver_name=data.driver_name,
        notes=data.notes,
        status=DeliveryStatus.dispatched,
        performed_by=current_user.id,
    )
    lines = [
        DeliveryLine(
            delivery_number=record.delivery_number,
            sales_order_item_id=line.sales_order_item_id,
            lot_id=line.lot_id,
            product_code=items_by_id[line.sales_order_item_id].product_code,
            lot_number=lots_by_id[line.lot_id].lot_number,
            quantity=line.quantity,
            unit=items_by_id[line.sales_order_item_id].unit,
        )
        for line in data.lines
    ]
    db.add(record)
    db.add_all(lines)
    await db.commit()
    await db.refresh(record)
    return record, lines


@delivery_router.post("/batch", response_model=DeliveryResponse, status_code=status.HTTP_201_CREATED)
async def create_delivery_batch(
    data: DeliveryBatchCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> DeliveryResponse:
    record, lines = await create_delivery_batch_record(data, db, current_user)
    return delivery_response(record, lines)


@delivery_router.post("", response_model=DeliveryResponse, status_code=status.HTTP_201_CREATED)
async def create_delivery(
    data: DeliveryCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> DeliveryResponse:
    batch = DeliveryBatchCreate(
        delivery_date=data.delivery_date,
        transportation_code=data.transportation_code,
        driver_name=data.driver_name,
        notes=data.notes,
        lines=[{"sales_order_item_id": data.sales_order_item_id, "lot_id": data.lot_id, "quantity": data.quantity}],
    )
    record, lines = await create_delivery_batch_record(batch, db, current_user)
    return delivery_response(record, lines)


@delivery_router.get("", response_model=PaginatedDeliveries)
async def list_deliveries(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    delivery_status: DeliveryStatus | None = Query(default=None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedDeliveries:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Delivery.delivery_number.ilike(term),
                Delivery.sales_order_number.ilike(term),
                Delivery.customer_name.ilike(term),
                Delivery.product_code.ilike(term),
                Delivery.lot_number.ilike(term),
            )
        )
    if delivery_status:
        filters.append(Delivery.status == delivery_status)
    if date_from:
        filters.append(Delivery.delivery_date >= date_from)
    if date_to:
        filters.append(Delivery.delivery_date <= date_to)
    records = list(
        (
            await db.execute(
                select(Delivery)
                .where(*filters)
                .order_by(Delivery.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .scalars()
        .all()
    )
    total = await db.scalar(select(func.count()).select_from(Delivery).where(*filters))
    return PaginatedDeliveries(
        items=[delivery_response(record, await delivery_lines(db, record)) for record in records],
        total=total or 0,
        page=page,
        size=size,
    )


@delivery_router.get("/lookup/sales-order-items")
async def delivery_sales_order_items(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[dict]:
    """Approved customer order lines that still require fulfillment."""
    rows = list(
        (
            await db.execute(
                select(SalesOrderItem, SalesOrder)
                .join(SalesOrder, SalesOrder.sales_order_number == SalesOrderItem.sales_order_number)
                .where(
                    SalesOrder.status == "approved",
                    SalesOrderItem.delivered_quantity < SalesOrderItem.quantity_grams,
                )
                .order_by(SalesOrder.po_receipt_date.desc(), SalesOrderItem.id)
            )
        ).all()
    )
    return [
        {
            "id": item.id,
            "sales_order_number": order.sales_order_number,
            "customer_name": order.customer_name,
            "product_code": item.product_code,
            "description": item.description,
            "unit": item.unit,
            "outstanding_quantity": display_quantity(item.quantity_grams - item.delivered_quantity, item.unit),
        }
        for item, order in rows
    ]


@delivery_router.get("/lookup/finish-good-lots")
async def delivery_finish_good_lots(
    product_code: str = Query(min_length=1),
    unit: str = Query(min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Available positive lots in Finished Goods storage for a selected SO line."""
    rows = list(
        (
            await db.execute(
                select(ProductLot, StorageLocation)
                .join(StorageLocation, StorageLocation.code == ProductLot.storage_location_code)
                .join(WarehouseStorage, WarehouseStorage.code == StorageLocation.storage_code)
                .where(
                    ProductLot.product_code == product_code,
                    ProductLot.unit == inventory_unit(unit),
                    ProductLot.current_quantity_grams > 0,
                    WarehouseStorage.storage_type == "finished_goods",
                )
                .order_by(ProductLot.created_at, ProductLot.id)
            )
        ).all()
    )
    return [
        {
            "id": lot.id,
            "lot_number": lot.lot_number,
            "quantity": display_quantity(lot.current_quantity_grams, unit),
            "unit": unit,
            "plant_code": lot.plant_code,
            "storage_location_code": lot.storage_location_code,
            "storage_location_name": location.name,
        }
        for lot, location in rows
    ]


@delivery_router.get("/{delivery_number_value}", response_model=DeliveryResponse)
async def get_delivery(
    delivery_number_value: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeliveryResponse:
    record = await db.get(Delivery, delivery_number_value)
    if not record:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return delivery_response(record, await delivery_lines(db, record))


@delivery_router.post("/{delivery_number_value}/deliver", response_model=DeliveryResponse)
async def confirm_delivery(
    delivery_number_value: str,
    data: DeliveryConfirm,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeliveryResponse:
    record = (
        await db.execute(select(Delivery).where(Delivery.delivery_number == delivery_number_value).with_for_update())
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if record.status != DeliveryStatus.dispatched:
        raise HTTPException(status_code=409, detail="Only dispatched Delivery can be confirmed as delivered")
    lines = await delivery_lines(db, record)
    item_ids = sorted({line.sales_order_item_id for line in lines})
    items = list(
        (
            await db.execute(
                select(SalesOrderItem)
                .where(SalesOrderItem.id.in_(item_ids))
                .order_by(SalesOrderItem.id)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    items_by_id = {item.id: item for item in items}
    order = (
        await db.execute(
            select(SalesOrder).where(SalesOrder.sales_order_number == record.sales_order_number).with_for_update()
        )
    ).scalar_one()
    for line in lines:
        item = items_by_id[line.sales_order_item_id]
        item.delivered_quantity = grams(item.delivered_quantity + line.quantity)
    open_items = await db.scalar(
        select(func.count())
        .select_from(SalesOrderItem)
        .where(
            SalesOrderItem.sales_order_number == order.sales_order_number,
            SalesOrderItem.delivered_quantity < SalesOrderItem.quantity_grams,
        )
    )
    order.fulfillment_status = FulfillmentStatus.closed if open_items == 0 else FulfillmentStatus.open
    record.status = DeliveryStatus.delivered
    record.delivered_by = current_user.id
    record.delivered_at = datetime.now(timezone.utc)
    if data.notes.strip():
        record.notes = f"{record.notes}\n{data.notes.strip()}".strip()
    await db.commit()
    await db.refresh(record)
    return delivery_response(record, lines)


@delivery_router.post("/{delivery_number_value}/reverse", response_model=DeliveryResponse)
async def reverse_delivery(
    delivery_number_value: str,
    data: DeliveryReverse,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeliveryResponse:
    record = (
        await db.execute(select(Delivery).where(Delivery.delivery_number == delivery_number_value).with_for_update())
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if record.status not in {DeliveryStatus.dispatched, DeliveryStatus.delivered, DeliveryStatus.posted}:
        raise HTTPException(status_code=409, detail="Delivery has already been reversed")
    if current_user.role.strip().lower() != "courier" and current_user.access_level.value != "administrator":
        raise HTTPException(status_code=403, detail="Only Courier users can reverse Delivery")
    lines = await delivery_lines(db, record)
    if not lines:
        lines = [
            DeliveryLine(
                delivery_number=record.delivery_number,
                sales_order_item_id=record.sales_order_item_id,
                lot_id=record.lot_id,
                product_code=record.product_code,
                lot_number=record.lot_number,
                quantity=record.quantity,
                unit=record.unit,
            )
        ]
    item_ids = sorted({line.sales_order_item_id for line in lines})
    lot_ids = sorted({line.lot_id for line in lines})
    items = list(
        (
            await db.execute(
                select(SalesOrderItem)
                .where(SalesOrderItem.id.in_(item_ids))
                .order_by(SalesOrderItem.id)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    lots = list(
        (
            await db.execute(
                select(ProductLot).where(ProductLot.id.in_(lot_ids)).order_by(ProductLot.id).with_for_update()
            )
        )
        .scalars()
        .all()
    )
    items_by_id = {item.id: item for item in items}
    lots_by_id = {lot.id: lot for lot in lots}
    order = (
        await db.execute(
            select(SalesOrder).where(SalesOrder.sales_order_number == record.sales_order_number).with_for_update()
        )
    ).scalar_one()
    product_codes = {line.product_code for line in lines}
    products = list(
        (
            await db.execute(
                select(Product).where(Product.code.in_(product_codes)).order_by(Product.code).with_for_update()
            )
        )
        .scalars()
        .all()
    )
    products_by_code = {product.code: product for product in products}
    for line in lines:
        item, lot, product = (
            items_by_id[line.sales_order_item_id],
            lots_by_id[line.lot_id],
            products_by_code[line.product_code],
        )
        inventory_quantity = to_inventory_quantity(line.quantity, item.unit)
        product_after, lot_after = apply_stock_delta(
            product.current_stock_grams, lot.current_quantity_grams, inventory_quantity
        )
        product.current_stock_grams, lot.current_quantity_grams = product_after, lot_after
        if record.status in {DeliveryStatus.delivered, DeliveryStatus.posted}:
            item.delivered_quantity = grams(item.delivered_quantity - line.quantity)
    if record.status in {DeliveryStatus.delivered, DeliveryStatus.posted}:
        order.fulfillment_status = FulfillmentStatus.open
    record.status = DeliveryStatus.reversed
    record.reversed_by = current_user.id
    record.reversal_reason = data.reason.strip()
    await db.commit()
    await db.refresh(record)
    return delivery_response(record, lines)
