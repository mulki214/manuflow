from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    Department,
    InventoryMovement,
    InventoryMovementType,
    Plant,
    Product,
    ProductLot,
    Receiving,
    StorageLocation,
    StorageType,
    User,
    WarehouseDestinationType,
    WarehouseMaterialTransfer,
    WarehouseStorage,
    WarehouseTransferStatus,
    WipLotJob,
    WipLotStatus,
    WipProcess,
    WipProcessType,
)
from app.module_permissions import DepartmentModuleAccess, resolve_department_membership
from app.operational_services import require_whole_quantity
from app.schemas import (
    PaginatedWarehouseMaterialTransfers,
    PaginatedWarehouseStockLots,
    PaginatedWipProcesses,
    WarehouseMaterialTransferCreate,
    WarehouseMaterialTransferResponse,
    WarehouseStockLotResponse,
    WarehouseTransferReversal,
    WipProcessResponse,
)
from app.warehouse_services import (
    ensure_transfer_posted,
    ensure_wip_job_reversible,
    generate_transfer_number,
    move_quantity,
    quantity,
)

router = APIRouter(prefix="/warehouse", tags=["Warehouse"])


async def current_access(db: AsyncSession, user: User) -> DepartmentModuleAccess:
    department = await db.get(Department, settings.warehouse_department_code)
    access = resolve_department_membership(user, department)
    if not access.can_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active Warehouse department members can access this module",
        )
    return access


def ensure_can_reverse(access: DepartmentModuleAccess) -> None:
    if not access.is_pic and not access.is_head:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Warehouse PIC or Head can reverse a material transfer",
        )


async def destination_response(db: AsyncSession, record: WipProcess) -> WipProcessResponse:
    plant = await db.get(Plant, record.plant_code)
    return WipProcessResponse(
        code=record.code,
        name=record.name,
        description=record.description,
        process_type=record.process_type,
        plant_code=record.plant_code,
        plant_name=plant.name if plant else record.plant_code,
        is_active=record.is_active,
        can_edit=False,
        can_delete=False,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def transfer_response(
    db: AsyncSession, record: WarehouseMaterialTransfer, access: DepartmentModuleAccess
) -> WarehouseMaterialTransferResponse:
    job = (
        await db.execute(select(WipLotJob).where(WipLotJob.source_transfer_number == record.transfer_number))
    ).scalar_one_or_none()
    reverser = await db.get(User, record.reversed_by) if record.reversed_by else None
    target_untouched = True
    if job:
        target_untouched = job.status == WipLotStatus.queued and quantity(job.current_quantity) == quantity(
            job.input_quantity
        )
    elif record.destination_lot_id and record.status == WarehouseTransferStatus.posted:
        target = await db.get(ProductLot, record.destination_lot_id)
        target_untouched = bool(target and target.current_quantity_grams >= record.quantity_grams)
    return WarehouseMaterialTransferResponse(
        transfer_number=record.transfer_number,
        transfer_date=record.transfer_date,
        product_code=record.product_code,
        product_name=record.product_name,
        description=record.description,
        lot_number=record.lot_number,
        quantity=record.quantity_grams,
        unit=record.unit,
        plant_code=record.plant_code,
        plant_name=record.plant_name,
        source_lot_id=record.source_lot_id,
        source_storage_code=record.source_storage_code,
        source_storage_name=record.source_storage_name,
        source_location_code=record.source_location_code,
        source_location_name=record.source_location_name,
        destination_type=record.destination_type,
        destination_process_code=record.destination_process_code,
        destination_process_name=record.destination_process_name,
        destination_storage_code=record.destination_storage_code,
        destination_storage_name=record.destination_storage_name,
        destination_location_code=record.destination_location_code,
        destination_location_name=record.destination_location_name,
        document_number=record.document_number,
        notes=record.notes,
        status=record.status,
        performed_by=record.performed_by,
        performed_by_name=record.performed_by_name,
        reversed_by=record.reversed_by,
        reversed_by_name=(f"{reverser.first_name} {reverser.last_name}".strip() if reverser else None),
        reversed_at=record.reversed_at,
        reversal_reason=record.reversal_reason,
        wip_job_id=job.id if job else None,
        wip_lot_segment_code=job.lot_segment_code if job else None,
        wip_status=job.status if job else None,
        can_reverse=(
            record.status == WarehouseTransferStatus.posted and target_untouched and (access.is_pic or access.is_head)
        ),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/stock-lots", response_model=PaginatedWarehouseStockLots)
async def list_stock_lots(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    plant_code: str | None = None,
    product_code: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedWarehouseStockLots:
    await current_access(db, current_user)
    filters = [
        ProductLot.current_quantity_grams > 0,
        WarehouseStorage.storage_type.in_([StorageType.raw_material, StorageType.general]),
    ]
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(Product.code.ilike(term), Product.description.ilike(term), ProductLot.lot_number.ilike(term))
        )
    if plant_code:
        filters.append(ProductLot.plant_code == plant_code)
    if product_code:
        filters.append(ProductLot.product_code == product_code)
    base = (
        select(ProductLot, Product, Plant, StorageLocation, WarehouseStorage)
        .join(Product, Product.code == ProductLot.product_code)
        .join(Plant, Plant.code == ProductLot.plant_code)
        .join(StorageLocation, StorageLocation.code == ProductLot.storage_location_code)
        .join(WarehouseStorage, WarehouseStorage.code == StorageLocation.storage_code)
        .where(*filters)
    )
    rows = (await db.execute(base.order_by(ProductLot.created_at.desc()).offset((page - 1) * size).limit(size))).all()
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    return PaginatedWarehouseStockLots(
        items=[
            WarehouseStockLotResponse(
                lot_id=lot.id,
                product_code=product.code,
                product_name=product.part_name,
                description=product.description,
                lot_number=lot.lot_number,
                quantity=lot.current_quantity_grams,
                unit=lot.unit,
                plant_code=plant.code,
                plant_name=plant.name,
                storage_code=storage.code,
                storage_name=storage.name,
                storage_type=storage.storage_type,
                storage_location_code=location.code,
                storage_location_name=location.name,
            )
            for lot, product, plant, location, storage in rows
        ],
        total=total or 0,
        page=page,
        size=size,
    )


@router.get("/production-destinations", response_model=PaginatedWipProcesses)
async def list_production_destinations(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    plant_code: str | None = None,
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedWipProcesses:
    await current_access(db, current_user)
    filters = [WipProcess.process_type == WipProcessType.production]
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(WipProcess.code.ilike(term), WipProcess.name.ilike(term)))
    if plant_code:
        filters.append(WipProcess.plant_code == plant_code)
    if active_only:
        filters.append(WipProcess.is_active.is_(True))
    records = list(
        (
            await db.execute(
                select(WipProcess).where(*filters).order_by(WipProcess.code).offset((page - 1) * size).limit(size)
            )
        )
        .scalars()
        .all()
    )
    total = await db.scalar(select(func.count()).select_from(WipProcess).where(*filters))
    return PaginatedWipProcesses(
        items=[await destination_response(db, record) for record in records], total=total or 0, page=page, size=size
    )


@router.get("", response_model=PaginatedWarehouseMaterialTransfers)
async def list_transfers(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    product_code: str | None = None,
    plant_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    destination_type: WarehouseDestinationType | None = None,
    transfer_status: WarehouseTransferStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedWarehouseMaterialTransfers:
    access = await current_access(db, current_user)
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                WarehouseMaterialTransfer.transfer_number.ilike(term),
                WarehouseMaterialTransfer.product_code.ilike(term),
                WarehouseMaterialTransfer.description.ilike(term),
                WarehouseMaterialTransfer.lot_number.ilike(term),
                WarehouseMaterialTransfer.document_number.ilike(term),
            )
        )
    if product_code:
        filters.append(WarehouseMaterialTransfer.product_code == product_code)
    if plant_code:
        filters.append(WarehouseMaterialTransfer.plant_code == plant_code)
    if date_from:
        filters.append(WarehouseMaterialTransfer.transfer_date >= date_from)
    if date_to:
        filters.append(WarehouseMaterialTransfer.transfer_date <= date_to)
    if destination_type:
        filters.append(WarehouseMaterialTransfer.destination_type == destination_type)
    if transfer_status:
        filters.append(WarehouseMaterialTransfer.status == transfer_status)
    records = list(
        (
            await db.execute(
                select(WarehouseMaterialTransfer)
                .where(*filters)
                .order_by(WarehouseMaterialTransfer.transfer_date.desc(), WarehouseMaterialTransfer.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .scalars()
        .all()
    )
    total = await db.scalar(select(func.count()).select_from(WarehouseMaterialTransfer).where(*filters))
    return PaginatedWarehouseMaterialTransfers(
        items=[await transfer_response(db, record, access) for record in records],
        total=total or 0,
        page=page,
        size=size,
    )


@router.post("", response_model=WarehouseMaterialTransferResponse, status_code=status.HTTP_201_CREATED)
async def create_transfer(
    data: WarehouseMaterialTransferCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WarehouseMaterialTransferResponse:
    access = await current_access(db, current_user)
    source_lot = (
        await db.execute(select(ProductLot).where(ProductLot.id == data.source_lot_id).with_for_update())
    ).scalar_one_or_none()
    if not source_lot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source Lot not found")
    linked_item_ids = list(
        (
            await db.execute(
                select(Receiving.sales_order_item_id)
                .where(Receiving.lot_id == source_lot.id, Receiving.sales_order_item_id.is_not(None))
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    sales_order_item_id = linked_item_ids[0] if len(linked_item_ids) == 1 else None
    product = await db.get(Product, source_lot.product_code)
    plant = await db.get(Plant, source_lot.plant_code)
    source_location = await db.get(StorageLocation, source_lot.storage_location_code)
    source_storage = await db.get(WarehouseStorage, source_location.storage_code) if source_location else None
    if not product or not plant or not source_location or not source_storage:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Source Lot storage reference is incomplete")
    if source_storage.storage_type not in (StorageType.raw_material, StorageType.general):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only Raw Material or General Storage stock can be transferred from this module",
        )
    try:
        require_whole_quantity(data.quantity, source_lot.unit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    moved = quantity(data.quantity)
    try:
        source_after, _ = move_quantity(source_lot.current_quantity_grams, Decimal("0"), moved)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    process: WipProcess | None = None
    target_location: StorageLocation | None = None
    target_storage: WarehouseStorage | None = None
    target_lot: ProductLot | None = None
    if data.destination_type == WarehouseDestinationType.wip:
        process = await db.get(WipProcess, data.destination_process_code)
        if (
            not process
            or not process.is_active
            or process.process_type != WipProcessType.production
            or process.plant_code != plant.code
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Destination must be an active Production WIP Process in the same Plant",
            )
    else:
        target_location = await db.get(StorageLocation, data.destination_location_code)
        target_storage = await db.get(WarehouseStorage, target_location.storage_code) if target_location else None
        if (
            not target_location
            or not target_storage
            or target_location.plant_code != plant.code
            or target_storage.storage_type != StorageType.finished_goods
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Destination must be a Finished Goods Location in the same Plant",
            )
        if target_location.code == source_location.code:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Destination equals source")
        target_lot = (
            await db.execute(
                select(ProductLot)
                .where(
                    ProductLot.product_code == product.code,
                    ProductLot.lot_number == source_lot.lot_number,
                    ProductLot.storage_location_code == target_location.code,
                    ProductLot.unit == source_lot.unit,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if target_lot:
            _, target_after = move_quantity(Decimal("0"), target_lot.current_quantity_grams, moved)
            target_lot.initial_quantity_grams += moved
            target_lot.current_quantity_grams = target_after
        else:
            target_lot = ProductLot(
                product_code=product.code,
                lot_number=source_lot.lot_number,
                plant_code=plant.code,
                storage_location_code=target_location.code,
                unit=source_lot.unit,
                initial_quantity_grams=moved,
                current_quantity_grams=moved,
            )
            db.add(target_lot)
            await db.flush()

    transfer_number = await generate_transfer_number(db, data.transfer_date)
    source_lot.current_quantity_grams = source_after
    record = WarehouseMaterialTransfer(
        transfer_number=transfer_number,
        transfer_date=data.transfer_date,
        product_code=product.code,
        product_name=product.part_name,
        description=product.description,
        lot_number=source_lot.lot_number,
        quantity_grams=moved,
        unit=source_lot.unit,
        plant_code=plant.code,
        plant_name=plant.name,
        source_lot_id=source_lot.id,
        sales_order_item_id=sales_order_item_id,
        source_storage_code=source_storage.code,
        source_storage_name=source_storage.name,
        source_location_code=source_location.code,
        source_location_name=source_location.name,
        destination_type=data.destination_type,
        destination_process_code=process.code if process else None,
        destination_process_name=process.name if process else None,
        destination_storage_code=target_storage.code if target_storage else None,
        destination_storage_name=target_storage.name if target_storage else None,
        destination_location_code=target_location.code if target_location else None,
        destination_location_name=target_location.name if target_location else None,
        destination_lot_id=target_lot.id if target_lot else None,
        document_number=data.document_number,
        notes=data.notes,
        status=WarehouseTransferStatus.posted,
        performed_by=current_user.id,
        performed_by_name=f"{current_user.first_name} {current_user.last_name}".strip(),
    )
    db.add(record)
    await db.flush()
    if process:
        db.add(
            WipLotJob(
                source_transfer_number=transfer_number,
                sales_order_item_id=sales_order_item_id,
                process_code=process.code,
                product_code=product.code,
                lot_number=source_lot.lot_number,
                lot_segment_code=f"{source_lot.lot_number}-{transfer_number}",
                plant_code=plant.code,
                unit=source_lot.unit,
                input_quantity=moved,
                current_quantity=moved,
                status=WipLotStatus.queued,
            )
        )
    db.add(
        InventoryMovement(
            movement_type=InventoryMovementType.warehouse_out,
            product_code=product.code,
            lot_id=source_lot.id,
            unit=source_lot.unit,
            quantity_grams=-moved,
            product_stock_after_grams=product.current_stock_grams,
            lot_stock_after_grams=source_after,
            reference_type="warehouse_transfer",
            reference_number=transfer_number,
            performed_by=current_user.id,
            notes=data.notes,
        )
    )
    if target_lot:
        db.add(
            InventoryMovement(
                movement_type=InventoryMovementType.warehouse_in,
                product_code=product.code,
                lot_id=target_lot.id,
                unit=target_lot.unit,
                quantity_grams=moved,
                product_stock_after_grams=product.current_stock_grams,
                lot_stock_after_grams=target_lot.current_quantity_grams,
                reference_type="warehouse_transfer",
                reference_number=transfer_number,
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
            detail="Warehouse transfer conflicts with stock",
        ) from exc
    return await transfer_response(db, record, access)


@router.get("/{transfer_number}", response_model=WarehouseMaterialTransferResponse)
async def get_transfer(
    transfer_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WarehouseMaterialTransferResponse:
    access = await current_access(db, current_user)
    record = await db.get(WarehouseMaterialTransfer, transfer_number)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse transfer not found")
    return await transfer_response(db, record, access)


@router.post("/{transfer_number}/reverse", response_model=WarehouseMaterialTransferResponse)
async def reverse_transfer(
    transfer_number: str,
    data: WarehouseTransferReversal,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WarehouseMaterialTransferResponse:
    access = await current_access(db, current_user)
    ensure_can_reverse(access)
    record = await db.get(WarehouseMaterialTransfer, transfer_number)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse transfer not found")
    ensure_transfer_posted(record.status)
    source_lot = (
        await db.execute(select(ProductLot).where(ProductLot.id == record.source_lot_id).with_for_update())
    ).scalar_one()
    if record.destination_type == WarehouseDestinationType.wip:
        job = (
            await db.execute(
                select(WipLotJob).where(WipLotJob.source_transfer_number == transfer_number).with_for_update()
            )
        ).scalar_one()
        ensure_wip_job_reversible(job.status, job.current_quantity, job.input_quantity)
        job.current_quantity = Decimal("0")
        job.status = WipLotStatus.reversed
    else:
        target_lot = (
            await db.execute(select(ProductLot).where(ProductLot.id == record.destination_lot_id).with_for_update())
        ).scalar_one()
        if target_lot.current_quantity_grams < record.quantity_grams:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Transfer cannot be reversed because Finished Goods stock has already been used",
            )
        target_lot.current_quantity_grams = quantity(target_lot.current_quantity_grams - record.quantity_grams)
    source_lot.current_quantity_grams = quantity(source_lot.current_quantity_grams + record.quantity_grams)
    record.status = WarehouseTransferStatus.reversed
    record.reversed_by = current_user.id
    record.reversed_at = datetime.now(timezone.utc)
    record.reversal_reason = data.reason
    product = await db.get(Product, record.product_code)
    db.add(
        InventoryMovement(
            movement_type=InventoryMovementType.warehouse_reversal,
            product_code=record.product_code,
            lot_id=source_lot.id,
            unit=record.unit,
            quantity_grams=record.quantity_grams,
            product_stock_after_grams=product.current_stock_grams,
            lot_stock_after_grams=source_lot.current_quantity_grams,
            reference_type="warehouse_reversal",
            reference_number=record.transfer_number,
            performed_by=current_user.id,
            notes=data.reason,
        )
    )
    await db.commit()
    await db.refresh(record)
    return await transfer_response(db, record, access)
