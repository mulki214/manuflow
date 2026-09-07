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
    AccessLevel,
    ConsumableDisposition,
    Department,
    FinishGoodReceipt,
    FinishGoodStatus,
    Machine,
    Plant,
    Product,
    ProductionExecution,
    ProductLot,
    ProductProcessStandard,
    QualityInspection,
    RepairRoute,
    RepairRouteStep,
    StorageLocation,
    User,
    WipLotJob,
    WipLotStatus,
    WipProcess,
    WipProcessType,
)
from app.module_permissions import DepartmentModuleAccess, resolve_department_membership
from app.operational_services import actual_cycle_time_seconds, ng_limit_exceeded, require_whole_quantity
from app.production_services import (
    child_segment_code,
    ensure_production_execution_reversible,
    generate_production_number,
    next_job_status,
    validate_execution_quantities,
)
from app.schemas import (
    ConsumableDispositionCreate,
    ConsumableDispositionResponse,
    PaginatedProductionExecutions,
    PaginatedProductionWipJobs,
    PaginatedWipProcesses,
    ProductionExecutionCreate,
    ProductionExecutionResponse,
    ProductionExecutionReverse,
    ProductionWipJobResponse,
    ProductProcessStandardCreate,
    ProductProcessStandardResponse,
    RepairRouteCreate,
    RepairRouteResponse,
    WipProcessCreate,
    WipProcessResponse,
    WipProcessUpdate,
)
from app.warehouse_services import quantity

router = APIRouter(prefix="/production", tags=["Production"])


@router.get("/standards", response_model=list[ProductProcessStandardResponse])
async def list_standards(
    product_code: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProductProcessStandard]:
    await current_access(db, current_user)
    query = select(ProductProcessStandard).order_by(
        ProductProcessStandard.product_code, ProductProcessStandard.process_code
    )
    if product_code:
        query = query.where(ProductProcessStandard.product_code == product_code)
    return list((await db.execute(query)).scalars().all())


@router.get("/stock")
async def production_stock(
    product_code: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    await current_access(db, current_user)
    query = (
        select(ProductLot)
        .where(ProductLot.current_quantity_grams > 0)
        .order_by(ProductLot.product_code, ProductLot.lot_number)
    )
    if product_code:
        query = query.where(ProductLot.product_code == product_code)
    records = list((await db.execute(query)).scalars())
    return [
        {
            "lot_id": row.id,
            "product_code": row.product_code,
            "lot_number": row.lot_number,
            "plant_code": row.plant_code,
            "storage_location_code": row.storage_location_code,
            "quantity": row.current_quantity_grams,
            "unit": row.unit,
        }
        for row in records
    ]


@router.post("/standards", response_model=ProductProcessStandardResponse, status_code=201)
async def create_standard(
    data: ProductProcessStandardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductProcessStandard:
    await current_access(db, current_user)
    if not await db.get(Product, data.product_code) or not await db.get(WipProcess, data.process_code):
        raise HTTPException(status_code=422, detail="Product or Process not found")
    record = ProductProcessStandard(**data.model_dump(mode="json"))
    db.add(record)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Product Process Standard already exists") from exc
    await db.refresh(record)
    return record


@router.get("/repair-routes", response_model=list[RepairRouteResponse])
async def list_repair_routes(
    product_code: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RepairRouteResponse]:
    await current_access(db, current_user)
    query = select(RepairRoute).order_by(RepairRoute.code)
    if product_code:
        query = query.where(RepairRoute.product_code == product_code)
    routes = list((await db.execute(query)).scalars().all())
    result = []
    for route in routes:
        steps = list(
            (
                await db.execute(
                    select(RepairRouteStep)
                    .where(RepairRouteStep.route_code == route.code)
                    .order_by(RepairRouteStep.step_order)
                )
            ).scalars()
        )
        result.append(
            RepairRouteResponse(
                code=route.code,
                name=route.name,
                product_code=route.product_code,
                source_process_code=route.source_process_code,
                return_process_code=route.return_process_code,
                step_process_codes=[step.process_code for step in steps],
                is_active=route.is_active,
                created_at=route.created_at,
                updated_at=route.updated_at,
            )
        )
    return result


@router.post("/repair-routes", response_model=RepairRouteResponse, status_code=201)
async def create_repair_route(
    data: RepairRouteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RepairRouteResponse:
    await current_access(db, current_user)
    source_process = await db.get(WipProcess, data.source_process_code)
    return_process = await db.get(WipProcess, data.return_process_code) if data.return_process_code else None
    processes = [await db.get(WipProcess, code) for code in data.step_process_codes]
    if (
        not await db.get(Product, data.product_code)
        or not source_process
        or any(process is None for process in processes)
    ):
        raise HTTPException(status_code=422, detail="Product or one of the Repair Processes was not found")
    if any(process.process_type != WipProcessType.repair for process in processes if process):
        raise HTTPException(status_code=422, detail="Every Repair Route step must use a Repair process")
    if return_process and return_process.process_type != WipProcessType.production:
        raise HTTPException(status_code=422, detail="Repair Route return process must be a Production process")
    route = RepairRoute(
        code=data.code.upper(),
        name=data.name.strip(),
        product_code=data.product_code,
        source_process_code=data.source_process_code,
        return_process_code=data.return_process_code,
        is_active=data.is_active,
        created_by=current_user.id,
    )
    db.add(route)
    await db.flush()
    for order, process_code in enumerate(data.step_process_codes, 1):
        db.add(RepairRouteStep(route_code=route.code, step_order=order, process_code=process_code))
    await db.commit()
    await db.refresh(route)
    payload = data.model_dump(exclude={"code"})
    return RepairRouteResponse(**payload, code=route.code, created_at=route.created_at, updated_at=route.updated_at)


async def current_access(db: AsyncSession, user: User) -> DepartmentModuleAccess:
    department = await db.get(Department, settings.production_department_code)
    access = resolve_department_membership(user, department)
    if not access.can_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active Production department members can access this module",
        )
    return access


def ensure_production_process_type(process_type: WipProcessType) -> None:
    if process_type not in (WipProcessType.production, WipProcessType.repair):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Production can only manage Production or Repair processes",
        )


def ensure_can_reverse(access: DepartmentModuleAccess, user: User) -> None:
    if not access.is_pic and not access.is_head and user.access_level != AccessLevel.administrator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Production PIC, Head, or administrator can reverse Production executions",
        )


async def process_response(db: AsyncSession, record: WipProcess) -> WipProcessResponse:
    plant = await db.get(Plant, record.plant_code)
    used = bool(
        await db.scalar(select(func.count()).select_from(WipLotJob).where(WipLotJob.process_code == record.code))
    )
    return WipProcessResponse(
        code=record.code,
        name=record.name,
        description=record.description,
        process_type=record.process_type,
        plant_code=record.plant_code,
        plant_name=plant.name if plant else record.plant_code,
        is_active=record.is_active,
        can_edit=True,
        can_delete=not used,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def job_response(db: AsyncSession, record: WipLotJob) -> ProductionWipJobResponse:
    process = await db.get(WipProcess, record.process_code)
    product = await db.get(Product, record.product_code)
    plant = await db.get(Plant, record.plant_code)
    return ProductionWipJobResponse(
        id=record.id,
        source_transfer_number=record.source_transfer_number,
        parent_job_id=record.parent_job_id,
        production_execution_id=record.production_execution_id,
        repair_route_code=getattr(record, "repair_route_code", None),
        repair_step_order=getattr(record, "repair_step_order", None),
        repair_return_process_code=getattr(record, "repair_return_process_code", None),
        process_code=record.process_code,
        process_name=process.name if process else record.process_code,
        process_type=process.process_type if process else WipProcessType.production,
        product_code=record.product_code,
        product_name=product.part_name if product else record.product_code,
        description=product.description if product else "",
        lot_number=record.lot_number,
        lot_segment_code=record.lot_segment_code,
        plant_code=record.plant_code,
        plant_name=plant.name if plant else record.plant_code,
        unit=record.unit,
        input_quantity=record.input_quantity,
        current_quantity=record.current_quantity,
        status=record.status,
        can_complete=record.status in (WipLotStatus.queued, WipLotStatus.in_process) and record.current_quantity > 0,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def execution_response(db: AsyncSession, record: ProductionExecution) -> ProductionExecutionResponse:
    plant = await db.get(Plant, record.plant_code)
    repair_process = await db.get(WipProcess, record.repair_process_code) if record.repair_process_code else None
    children = list(
        (
            await db.execute(
                select(WipLotJob).where(WipLotJob.production_execution_id == record.id).order_by(WipLotJob.id)
            )
        )
        .scalars()
        .all()
    )
    good_segment = next(
        (
            job.lot_segment_code
            for job in children
            if job.status in (WipLotStatus.queued, WipLotStatus.awaiting_qc)
            and job.process_code != record.repair_process_code
        ),
        None,
    )
    repair_segment = next(
        (job.lot_segment_code for job in children if job.process_code == record.repair_process_code), None
    )
    ng_segment = next((job.lot_segment_code for job in children if job.status == WipLotStatus.ng), None)
    return ProductionExecutionResponse(
        id=record.id,
        production_number=record.production_number,
        process_date=record.process_date,
        shift=record.shift,
        started_at=record.started_at,
        ended_at=record.ended_at,
        break_duration_minutes=record.break_duration_minutes,
        cycle_time_seconds=record.cycle_time_seconds,
        observed_cycle_time_seconds=record.observed_cycle_time_seconds,
        job_id=record.job_id,
        product_code=record.product_code,
        product_name=record.product_name,
        description=record.description,
        lot_number=record.lot_number,
        lot_segment_code=record.lot_segment_code,
        plant_code=record.plant_code,
        plant_name=plant.name if plant else record.plant_code,
        unit=record.unit,
        before_process_code=record.before_process_code,
        before_process_name=record.before_process_name,
        after_process_code=record.after_process_code,
        after_process_name=record.after_process_name,
        machine_code=record.machine_code,
        machine_name=record.machine_name,
        processing_quantity=record.processing_quantity,
        good_quantity=record.good_quantity,
        repair_quantity=record.repair_quantity,
        ng_quantity=record.ng_quantity,
        output_product_code=record.output_product_code,
        output_unit=record.output_unit,
        repair_process_code=record.repair_process_code,
        repair_process_name=repair_process.name if repair_process else None,
        repair_route_code=record.repair_route_code,
        ng_limit_exceeded=record.ng_limit_exceeded,
        ng_override_by=record.ng_override_by,
        ng_override_at=record.ng_override_at,
        ng_override_reason=record.ng_override_reason,
        notes=record.notes,
        performed_by=record.performed_by,
        performed_by_name=record.performed_by_name,
        reversed_by=record.reversed_by,
        reversed_at=record.reversed_at,
        reversal_reason=record.reversal_reason,
        can_reverse=record.reversed_at is None,
        good_segment_code=good_segment,
        repair_segment_code=repair_segment,
        ng_segment_code=ng_segment,
        created_at=record.created_at,
    )


@router.get("/processes", response_model=PaginatedWipProcesses)
async def list_processes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    plant_code: str | None = None,
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedWipProcesses:
    await current_access(db, current_user)
    filters = [WipProcess.process_type.in_([WipProcessType.production, WipProcessType.repair])]
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
        items=[await process_response(db, record) for record in records],
        total=total or 0,
        page=page,
        size=size,
    )


@router.get("/wip-jobs", response_model=PaginatedProductionWipJobs)
async def list_wip_jobs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    plant_code: str | None = None,
    process_code: str | None = None,
    job_status: WipLotStatus | None = Query(default=None, alias="status"),
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedProductionWipJobs:
    await current_access(db, current_user)
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                WipLotJob.lot_number.ilike(term),
                WipLotJob.lot_segment_code.ilike(term),
                WipLotJob.source_transfer_number.ilike(term),
                WipLotJob.product_code.ilike(term),
            )
        )
    if plant_code:
        filters.append(WipLotJob.plant_code == plant_code)
    if process_code:
        filters.append(WipLotJob.process_code == process_code)
    if job_status:
        filters.append(WipLotJob.status == job_status)
    elif active_only:
        filters.append(WipLotJob.status.in_([WipLotStatus.queued, WipLotStatus.in_process]))
    records = list(
        (
            await db.execute(
                select(WipLotJob)
                .where(*filters)
                .order_by(WipLotJob.updated_at.desc(), WipLotJob.id.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .scalars()
        .all()
    )
    total = await db.scalar(select(func.count()).select_from(WipLotJob).where(*filters))
    return PaginatedProductionWipJobs(
        items=[await job_response(db, record) for record in records],
        total=total or 0,
        page=page,
        size=size,
    )


@router.get("/wip-jobs/{job_id}", response_model=ProductionWipJobResponse)
async def get_wip_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductionWipJobResponse:
    await current_access(db, current_user)
    record = await db.get(WipLotJob, job_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WIP Job not found")
    return await job_response(db, record)


@router.get("/executions", response_model=PaginatedProductionExecutions)
async def list_executions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    plant_code: str | None = None,
    process_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedProductionExecutions:
    await current_access(db, current_user)
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                ProductionExecution.production_number.ilike(term),
                ProductionExecution.lot_number.ilike(term),
                ProductionExecution.lot_segment_code.ilike(term),
                ProductionExecution.product_code.ilike(term),
                ProductionExecution.description.ilike(term),
            )
        )
    if plant_code:
        filters.append(ProductionExecution.plant_code == plant_code)
    if process_code:
        filters.append(ProductionExecution.before_process_code == process_code)
    if date_from:
        filters.append(ProductionExecution.process_date >= date_from)
    if date_to:
        filters.append(ProductionExecution.process_date <= date_to)
    records = list(
        (
            await db.execute(
                select(ProductionExecution)
                .where(*filters)
                .order_by(ProductionExecution.process_date.desc(), ProductionExecution.id.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .scalars()
        .all()
    )
    total = await db.scalar(select(func.count()).select_from(ProductionExecution).where(*filters))
    return PaginatedProductionExecutions(
        items=[await execution_response(db, record) for record in records],
        total=total or 0,
        page=page,
        size=size,
    )


@router.post(
    "/wip-jobs/{job_id}/complete", response_model=ProductionExecutionResponse, status_code=status.HTTP_201_CREATED
)
async def complete_wip_job(
    job_id: int,
    data: ProductionExecutionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductionExecutionResponse:
    access = await current_access(db, current_user)
    job = (await db.execute(select(WipLotJob).where(WipLotJob.id == job_id).with_for_update())).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WIP Job not found")
    if job.status not in (WipLotStatus.queued, WipLotStatus.in_process) or job.current_quantity <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="WIP Job is not available for completion")
    current_process = await db.get(WipProcess, job.process_code)
    product = await db.get(Product, job.product_code)
    if not current_process or not product:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="WIP Job reference is incomplete")
    if current_process.plant_code != job.plant_code:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="WIP Job Process belongs to another Plant")
    try:
        for value, label in (
            (data.processing_quantity, "Processing Quantity"),
            (data.good_quantity, "Good Quantity"),
            (data.repair_quantity, "Repair Quantity"),
            (data.ng_quantity, "NG Quantity"),
        ):
            require_whole_quantity(value, job.unit, label)
        _, processing, good, repair, ng = validate_execution_quantities(
            job.current_quantity,
            data.processing_quantity,
            data.good_quantity,
            data.repair_quantity,
            data.ng_quantity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    continuing_repair_route = await db.get(RepairRoute, job.repair_route_code) if job.repair_route_code else None
    continuing_repair_step = None
    if continuing_repair_route and job.repair_step_order:
        continuing_repair_step = (
            await db.execute(
                select(RepairRouteStep)
                .where(
                    RepairRouteStep.route_code == continuing_repair_route.code,
                    RepairRouteStep.step_order > job.repair_step_order,
                )
                .order_by(RepairRouteStep.step_order)
                .limit(1)
            )
        ).scalar_one_or_none()
    automatic_next_code = None
    if continuing_repair_route:
        automatic_next_code = (
            continuing_repair_step.process_code
            if continuing_repair_step
            else job.repair_return_process_code or continuing_repair_route.return_process_code
        )
    selected_next_code = automatic_next_code if continuing_repair_route else data.next_process_code
    next_process = await db.get(WipProcess, selected_next_code) if selected_next_code else None
    if next_process and (
        not next_process.is_active
        or next_process.plant_code != job.plant_code
        or (continuing_repair_route is None and next_process.process_type != WipProcessType.production)
        or (
            continuing_repair_route is not None
            and next_process.process_type not in (WipProcessType.production, WipProcessType.repair)
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Next Process must be an active Production Process in the same Plant",
        )
    if good > 0 and selected_next_code == job.process_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Next Process must differ from Current Process"
        )
    repair_process = await db.get(WipProcess, data.repair_process_code) if repair > 0 else None
    if (
        repair > 0
        and not data.repair_route_code
        and (
            not repair_process
            or not repair_process.is_active
            or repair_process.plant_code != job.plant_code
            or repair_process.process_type != WipProcessType.repair
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Repair Process must be an active Repair Process in the same Plant",
        )
    machine = await db.get(Machine, data.machine_code) if data.machine_code else None
    if machine and machine.plant_code != job.plant_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Machine must belong to the same Plant"
        )
    output_product = await db.get(Product, data.output_product_code) if data.output_product_code else product
    if good > 0 and not output_product:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Output Product not found")
    output_unit = data.output_unit or job.unit
    repair_route = await db.get(RepairRoute, data.repair_route_code) if data.repair_route_code else None
    repair_step = None
    if repair > 0 and repair_route:
        repair_step = (
            await db.execute(
                select(RepairRouteStep)
                .where(RepairRouteStep.route_code == repair_route.code)
                .order_by(RepairRouteStep.step_order)
                .limit(1)
            )
        ).scalar_one_or_none()
        if (
            not repair_route.is_active
            or repair_route.product_code != job.product_code
            or repair_route.source_process_code != job.process_code
            or not repair_step
        ):
            raise HTTPException(status_code=422, detail="Repair Route is not valid for this Product and Process")
    standard = (
        await db.execute(
            select(ProductProcessStandard)
            .where(
                ProductProcessStandard.product_code == job.product_code,
                ProductProcessStandard.process_code == job.process_code,
                ProductProcessStandard.is_active.is_(True),
                or_(
                    ProductProcessStandard.machine_code == data.machine_code,
                    ProductProcessStandard.machine_code.is_(None),
                ),
            )
            .order_by(ProductProcessStandard.machine_code.desc().nullslast())
            .limit(1)
        )
    ).scalar_one_or_none()
    exceeded = ng_limit_exceeded(
        processing,
        ng,
        standard.maximum_ng_quantity if standard else None,
        standard.maximum_ng_percent if standard else None,
    )
    if exceeded and (
        not (access.is_head or current_user.access_level == AccessLevel.administrator)
        or not data.ng_override_reason
        or len(data.ng_override_reason.strip()) < 3
    ):
        raise HTTPException(
            status_code=422, detail="NG exceeds the configured limit and requires Head override with reason"
        )
    try:
        cycle_time = actual_cycle_time_seconds(data.started_at, data.ended_at, data.break_duration_minutes, good)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record = ProductionExecution(
        production_number=await generate_production_number(db, data.process_date),
        process_date=data.process_date,
        shift=data.shift,
        started_at=data.started_at,
        ended_at=data.ended_at,
        break_duration_minutes=data.break_duration_minutes,
        cycle_time_seconds=cycle_time,
        observed_cycle_time_seconds=data.observed_cycle_time_seconds,
        job_id=job.id,
        product_code=job.product_code,
        product_name=product.part_name,
        description=product.description,
        lot_number=job.lot_number,
        lot_segment_code=job.lot_segment_code,
        plant_code=job.plant_code,
        unit=job.unit,
        before_process_code=current_process.code,
        before_process_name=current_process.name,
        after_process_code=next_process.code if next_process else None,
        after_process_name=next_process.name if next_process else ("Quality Queue" if good > 0 else None),
        machine_code=machine.code if machine else None,
        machine_name=machine.name if machine else None,
        processing_quantity=processing,
        good_quantity=good,
        repair_quantity=repair,
        ng_quantity=ng,
        output_product_code=output_product.code if good > 0 and output_product else None,
        output_unit=output_unit if good > 0 else None,
        repair_process_code=repair_process.code if repair_process else None,
        repair_route_code=repair_route.code if repair_route else None,
        ng_limit_exceeded=exceeded,
        ng_override_by=current_user.id if exceeded else None,
        ng_override_at=datetime.now(timezone.utc) if exceeded else None,
        ng_override_reason=data.ng_override_reason.strip() if exceeded and data.ng_override_reason else None,
        notes=data.notes,
        performed_by=current_user.id,
        performed_by_name=f"{current_user.first_name} {current_user.last_name}".strip(),
    )
    db.add(record)
    await db.flush()
    job.current_quantity = quantity(job.current_quantity - processing)
    job.status = next_job_status(job.current_quantity)

    if good > 0:
        db.add(
            WipLotJob(
                source_transfer_number=job.source_transfer_number,
                sales_order_item_id=job.sales_order_item_id,
                parent_job_id=job.id,
                production_execution_id=record.id,
                repair_route_code=job.repair_route_code if continuing_repair_step else None,
                repair_step_order=continuing_repair_step.step_order if continuing_repair_step else None,
                repair_return_process_code=job.repair_return_process_code if continuing_repair_step else None,
                process_code=next_process.code if next_process else current_process.code,
                product_code=output_product.code,
                lot_number=job.lot_number,
                lot_segment_code=child_segment_code(job.lot_segment_code, record.id, "G"),
                plant_code=job.plant_code,
                unit=output_unit,
                input_quantity=good,
                current_quantity=good,
                status=WipLotStatus.queued if next_process else WipLotStatus.awaiting_qc,
            )
        )
    if repair > 0:
        db.add(
            WipLotJob(
                source_transfer_number=job.source_transfer_number,
                sales_order_item_id=job.sales_order_item_id,
                parent_job_id=job.id,
                production_execution_id=record.id,
                repair_route_code=repair_route.code if repair_route else None,
                repair_step_order=repair_step.step_order if repair_step else None,
                repair_return_process_code=repair_route.return_process_code if repair_route else None,
                process_code=repair_step.process_code if repair_step else repair_process.code,
                product_code=job.product_code,
                lot_number=job.lot_number,
                lot_segment_code=child_segment_code(job.lot_segment_code, record.id, "R"),
                plant_code=job.plant_code,
                unit=job.unit,
                input_quantity=repair,
                current_quantity=repair,
                status=WipLotStatus.queued,
            )
        )
    if ng > 0:
        db.add(
            WipLotJob(
                source_transfer_number=job.source_transfer_number,
                sales_order_item_id=job.sales_order_item_id,
                parent_job_id=job.id,
                production_execution_id=record.id,
                process_code=current_process.code,
                product_code=job.product_code,
                lot_number=job.lot_number,
                lot_segment_code=child_segment_code(job.lot_segment_code, record.id, "N"),
                plant_code=job.plant_code,
                unit=job.unit,
                input_quantity=ng,
                current_quantity=ng,
                status=WipLotStatus.ng,
            )
        )
    await db.commit()
    await db.refresh(record)
    return await execution_response(db, record)


@router.post("/executions/{execution_id}/reverse", response_model=ProductionExecutionResponse)
async def reverse_production_execution(
    execution_id: int,
    data: ProductionExecutionReverse,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductionExecutionResponse:
    access = await current_access(db, current_user)
    ensure_can_reverse(access, current_user)
    record = (
        await db.execute(select(ProductionExecution).where(ProductionExecution.id == execution_id).with_for_update())
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Production execution not found")
    if record.reversed_at:
        raise HTTPException(status_code=409, detail="Production execution has already been reversed")
    source_job = (
        await db.execute(select(WipLotJob).where(WipLotJob.id == record.job_id).with_for_update())
    ).scalar_one()
    children = list(
        (
            await db.execute(
                select(WipLotJob).where(WipLotJob.production_execution_id == record.id).with_for_update()
            )
        ).scalars()
    )
    child_ids = [child.id for child in children]
    has_consumables = bool(
        await db.scalar(
            select(func.count())
            .select_from(ConsumableDisposition)
            .where(ConsumableDisposition.production_execution_id == record.id)
        )
    )
    has_downstream_activity = False
    if child_ids:
        has_downstream_activity = bool(
            await db.scalar(
                select(func.count())
                .select_from(WipLotJob)
                .where(WipLotJob.parent_job_id.in_(child_ids), WipLotJob.status != WipLotStatus.reversed)
            )
        ) or bool(
            await db.scalar(
                select(func.count())
                .select_from(QualityInspection)
                .where(QualityInspection.job_id.in_(child_ids), QualityInspection.reversed_at.is_(None))
            )
        ) or bool(
            await db.scalar(
                select(func.count())
                .select_from(FinishGoodReceipt)
                .where(
                    FinishGoodReceipt.source_wip_job_id.in_(child_ids),
                    FinishGoodReceipt.status == FinishGoodStatus.posted,
                )
            )
        ) or bool(
            await db.scalar(
                select(func.count())
                .select_from(ProductionExecution)
                .where(ProductionExecution.job_id.in_(child_ids), ProductionExecution.reversed_at.is_(None))
            )
        )
    try:
        ensure_production_execution_reversible(len(children), has_downstream_activity, has_consumables)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit_child_ids: set[int] = set()
    if child_ids:
        audit_child_ids.update(
            (await db.execute(select(QualityInspection.job_id).where(QualityInspection.job_id.in_(child_ids))))
            .scalars()
            .all()
        )
        audit_child_ids.update(
            (
                await db.execute(
                    select(FinishGoodReceipt.source_wip_job_id).where(FinishGoodReceipt.source_wip_job_id.in_(child_ids))
                )
            )
            .scalars()
            .all()
        )
        audit_child_ids.update(
            (await db.execute(select(ProductionExecution.job_id).where(ProductionExecution.job_id.in_(child_ids))))
            .scalars()
            .all()
        )
    for child in children:
        if child.id in audit_child_ids:
            child.current_quantity = Decimal("0")
            child.status = WipLotStatus.reversed
        else:
            await db.delete(child)
    source_job.current_quantity += record.processing_quantity
    source_job.status = next_job_status(source_job.current_quantity)
    record.reversed_by = current_user.id
    record.reversed_at = datetime.now(timezone.utc)
    record.reversal_reason = data.reason
    await db.commit()
    await db.refresh(record)
    return await execution_response(db, record)


@router.post(
    "/executions/{execution_id}/consumables",
    response_model=ConsumableDispositionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_consumable_disposition(
    execution_id: int,
    data: ConsumableDispositionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConsumableDisposition:
    await current_access(db, current_user)
    execution = await db.get(ProductionExecution, execution_id)
    source = (
        await db.execute(select(ProductLot).where(ProductLot.id == data.source_lot_id).with_for_update())
    ).scalar_one_or_none()
    if not execution or not source:
        raise HTTPException(status_code=404, detail="Production Execution or Consumable Lot not found")
    total = quantity(data.consumed_quantity + data.waste_quantity + data.scrap_quantity)
    if total > source.current_quantity_grams:
        raise HTTPException(status_code=422, detail="Consumable disposition exceeds available Lot stock")
    destination = None
    if data.scrap_quantity > 0:
        location = await db.get(StorageLocation, data.scrap_storage_location_code)
        if not location or location.plant_code != source.plant_code:
            raise HTTPException(status_code=422, detail="Scrap Storage Location must belong to the source Plant")
        destination = (
            await db.execute(
                select(ProductLot)
                .where(
                    ProductLot.product_code == source.product_code,
                    ProductLot.lot_number == source.lot_number,
                    ProductLot.storage_location_code == location.code,
                    ProductLot.unit == source.unit,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not destination:
            destination = ProductLot(
                product_code=source.product_code,
                lot_number=source.lot_number,
                plant_code=source.plant_code,
                storage_location_code=location.code,
                unit=source.unit,
                initial_quantity_grams=Decimal("0"),
                current_quantity_grams=Decimal("0"),
            )
            db.add(destination)
    source.current_quantity_grams = quantity(source.current_quantity_grams - total)
    if destination:
        destination.current_quantity_grams = quantity(destination.current_quantity_grams + data.scrap_quantity)
        if destination.id != source.id:
            destination.initial_quantity_grams = quantity(destination.initial_quantity_grams + data.scrap_quantity)
    product = await db.get(Product, source.product_code)
    product.current_stock_grams = quantity(product.current_stock_grams - data.consumed_quantity - data.waste_quantity)
    record = ConsumableDisposition(
        production_execution_id=execution.id,
        source_lot_id=source.id,
        consumed_quantity=data.consumed_quantity,
        waste_quantity=data.waste_quantity,
        scrap_quantity=data.scrap_quantity,
        unit=source.unit,
        scrap_storage_location_code=data.scrap_storage_location_code if data.scrap_quantity > 0 else None,
        performed_by=current_user.id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.post("/processes", response_model=WipProcessResponse, status_code=status.HTTP_201_CREATED)
async def create_process(
    data: WipProcessCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WipProcessResponse:
    await current_access(db, current_user)
    ensure_production_process_type(data.process_type)
    if not await db.get(Plant, data.plant_code):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Plant not found")
    record = WipProcess(
        code=data.code.upper(),
        name=data.name.strip(),
        description=data.description.strip(),
        process_type=data.process_type,
        plant_code=data.plant_code,
        is_active=data.is_active,
        created_by=current_user.id,
    )
    db.add(record)
    try:
        await db.commit()
        await db.refresh(record)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="WIP Process Code already exists") from exc
    return await process_response(db, record)


@router.patch("/processes/{process_code}", response_model=WipProcessResponse)
async def update_process(
    process_code: str,
    data: WipProcessUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WipProcessResponse:
    await current_access(db, current_user)
    record = await db.get(WipProcess, process_code.upper())
    if not record or record.process_type == WipProcessType.quality:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production Process not found")
    updates = data.model_dump(exclude_unset=True)
    if updates.get("process_type") is not None:
        ensure_production_process_type(updates["process_type"])
    used = await db.scalar(select(func.count()).select_from(WipLotJob).where(WipLotJob.process_code == record.code))
    if used and (
        ("plant_code" in updates and updates["plant_code"] != record.plant_code)
        or ("process_type" in updates and updates["process_type"] != record.process_type)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Plant and Process Type cannot change after material has entered this Process",
        )
    if updates.get("plant_code") and not await db.get(Plant, updates["plant_code"]):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Plant not found")
    for field, value in updates.items():
        setattr(record, field, value.strip() if isinstance(value, str) else value)
    await db.commit()
    await db.refresh(record)
    return await process_response(db, record)


@router.delete("/processes/{process_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_process(
    process_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await current_access(db, current_user)
    record = await db.get(WipProcess, process_code.upper())
    if not record or record.process_type == WipProcessType.quality:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production Process not found")
    used = await db.scalar(select(func.count()).select_from(WipLotJob).where(WipLotJob.process_code == record.code))
    if used:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Used Process cannot be deleted; deactivate it",
        )
    await db.delete(record)
    await db.commit()
