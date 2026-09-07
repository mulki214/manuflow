from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    AccessLevel,
    Department,
    FinishGoodReceipt,
    FinishGoodStatus,
    Plant,
    Product,
    ProductionExecution,
    ProductProcessStandard,
    QualityInspection,
    RepairRoute,
    RepairRouteStep,
    User,
    WipLotJob,
    WipLotStatus,
    WipProcess,
    WipProcessType,
)
from app.module_permissions import DepartmentModuleAccess, resolve_department_membership
from app.operational_services import ng_limit_exceeded, require_whole_quantity
from app.production_services import child_segment_code, next_job_status
from app.quality_services import (
    ensure_quality_inspection_reversible,
    generate_quality_number,
    validate_inspection_quantities,
)
from app.schemas import (
    PaginatedQualityInspections,
    PaginatedQualityWipJobs,
    QualityInspectionCreate,
    QualityInspectionResponse,
    QualityInspectionReverse,
    QualityWipJobResponse,
)

router = APIRouter(prefix="/quality", tags=["Quality"])


async def current_access(db: AsyncSession, user: User) -> DepartmentModuleAccess:
    department = await db.get(Department, settings.quality_department_code)
    access = resolve_department_membership(user, department)
    if not access.can_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active Quality department members can access this module",
        )
    return access


def ensure_can_reverse(access: DepartmentModuleAccess, user: User) -> None:
    if not access.is_pic and not access.is_head and user.access_level != AccessLevel.administrator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Quality PIC, Head, or administrator can reverse Quality inspections",
        )


@router.get("/repair-options")
async def quality_repair_options(
    plant_code: str,
    product_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, list[dict]]:
    """Expose read-only repair configuration to authorized QC users."""
    await current_access(db, current_user)
    plant = await db.get(Plant, plant_code)
    processes = list(
        (
            await db.execute(
                select(WipProcess)
                .where(
                    WipProcess.plant_code == plant_code,
                    WipProcess.process_type == WipProcessType.repair,
                    WipProcess.is_active.is_(True),
                )
                .order_by(WipProcess.code)
            )
        ).scalars()
    )
    routes = list(
        (
            await db.execute(
                select(RepairRoute)
                .where(RepairRoute.product_code == product_code, RepairRoute.is_active.is_(True))
                .order_by(RepairRoute.code)
            )
        ).scalars()
    )
    route_rows = []
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
        route_rows.append(
            {
                "code": route.code,
                "name": route.name,
                "source_process_code": route.source_process_code,
                "return_process_code": route.return_process_code,
                "step_process_codes": [step.process_code for step in steps],
            }
        )
    return {
        "processes": [
            {
                "code": process.code,
                "name": process.name,
                "description": process.description,
                "process_type": process.process_type.value,
                "plant_code": process.plant_code,
                "plant_name": plant.name if plant else plant_code,
                "is_active": process.is_active,
                "can_delete": False,
            }
            for process in processes
        ],
        "routes": route_rows,
    }


async def job_response(db: AsyncSession, record: WipLotJob) -> QualityWipJobResponse:
    process = await db.get(WipProcess, record.process_code)
    product = await db.get(Product, record.product_code)
    plant = await db.get(Plant, record.plant_code)
    return QualityWipJobResponse(
        id=record.id,
        source_transfer_number=record.source_transfer_number,
        parent_job_id=record.parent_job_id,
        production_execution_id=record.production_execution_id,
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
        can_complete=False,
        can_inspect=record.status == WipLotStatus.awaiting_qc and record.current_quantity > 0,
        repair_route_code=record.repair_route_code,
        repair_step_order=record.repair_step_order,
        repair_return_process_code=record.repair_return_process_code,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def inspection_response(db: AsyncSession, record: QualityInspection) -> QualityInspectionResponse:
    plant = await db.get(Plant, record.plant_code)
    repair_process = await db.get(WipProcess, record.repair_process_code) if record.repair_process_code else None
    children = list(
        (await db.execute(select(WipLotJob).where(WipLotJob.parent_job_id == record.job_id))).scalars().all()
    )
    pass_segment = child_segment_code(record.lot_segment_code, record.id, "QP")
    repair_segment = child_segment_code(record.lot_segment_code, record.id, "QR")
    ng_segment = child_segment_code(record.lot_segment_code, record.id, "QN")
    return QualityInspectionResponse(
        id=record.id,
        quality_number=record.quality_number,
        inspection_date=record.inspection_date,
        shift=record.shift,
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
        inspection_quantity=record.inspection_quantity,
        pass_quantity=record.pass_quantity,
        repair_quantity=record.repair_quantity,
        ng_quantity=record.ng_quantity,
        repair_process_code=record.repair_process_code,
        repair_process_name=repair_process.name if repair_process else None,
        repair_route_code=record.repair_route_code,
        ng_limit_exceeded=record.ng_limit_exceeded,
        ng_override_by=record.ng_override_by,
        ng_override_at=record.ng_override_at,
        ng_override_reason=record.ng_override_reason,
        problem=record.problem,
        notes=record.notes,
        performed_by=record.performed_by,
        performed_by_name=record.performed_by_name,
        reversed_by=record.reversed_by,
        reversed_at=record.reversed_at,
        reversal_reason=record.reversal_reason,
        can_reverse=record.reversed_at is None,
        pass_segment_code=next(
            (job.lot_segment_code for job in children if job.lot_segment_code == pass_segment), None
        ),
        repair_segment_code=next(
            (job.lot_segment_code for job in children if job.lot_segment_code == repair_segment), None
        ),
        ng_segment_code=next((job.lot_segment_code for job in children if job.lot_segment_code == ng_segment), None),
        created_at=record.created_at,
    )


@router.get("/wip-jobs", response_model=PaginatedQualityWipJobs)
async def list_quality_queue(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    plant_code: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedQualityWipJobs:
    await current_access(db, current_user)
    filters = [WipLotJob.status == WipLotStatus.awaiting_qc, WipLotJob.current_quantity > 0]
    if search and (term := search.strip()):
        filters.append(
            or_(
                WipLotJob.lot_number.ilike(f"%{term}%"),
                WipLotJob.lot_segment_code.ilike(f"%{term}%"),
                WipLotJob.product_code.ilike(f"%{term}%"),
            )
        )
    if plant_code:
        filters.append(WipLotJob.plant_code == plant_code)
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
    return PaginatedQualityWipJobs(
        items=[await job_response(db, item) for item in records], total=total or 0, page=page, size=size
    )


@router.get("/inspections", response_model=PaginatedQualityInspections)
async def list_inspections(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    plant_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedQualityInspections:
    await current_access(db, current_user)
    filters = []
    if search and (term := search.strip()):
        filters.append(
            or_(
                QualityInspection.quality_number.ilike(f"%{term}%"),
                QualityInspection.lot_number.ilike(f"%{term}%"),
                QualityInspection.product_code.ilike(f"%{term}%"),
                QualityInspection.problem.ilike(f"%{term}%"),
            )
        )
    if plant_code:
        filters.append(QualityInspection.plant_code == plant_code)
    if date_from:
        filters.append(QualityInspection.inspection_date >= date_from)
    if date_to:
        filters.append(QualityInspection.inspection_date <= date_to)
    records = list(
        (
            await db.execute(
                select(QualityInspection)
                .where(*filters)
                .order_by(QualityInspection.inspection_date.desc(), QualityInspection.id.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .scalars()
        .all()
    )
    total = await db.scalar(select(func.count()).select_from(QualityInspection).where(*filters))
    return PaginatedQualityInspections(
        items=[await inspection_response(db, item) for item in records], total=total or 0, page=page, size=size
    )


@router.post(
    "/wip-jobs/{job_id}/inspect", response_model=QualityInspectionResponse, status_code=status.HTTP_201_CREATED
)
async def inspect_wip_job(
    job_id: int,
    data: QualityInspectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QualityInspectionResponse:
    access = await current_access(db, current_user)
    job = (await db.execute(select(WipLotJob).where(WipLotJob.id == job_id).with_for_update())).scalar_one_or_none()
    if not job or job.status != WipLotStatus.awaiting_qc or job.current_quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="WIP Job is not available for Quality inspection"
        )
    process = await db.get(WipProcess, job.process_code)
    product = await db.get(Product, job.product_code)
    if not process or not product:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="WIP Job reference is incomplete")
    try:
        for value, label in (
            (data.inspection_quantity, "Inspection Quantity"),
            (data.pass_quantity, "Pass Quantity"),
            (data.repair_quantity, "Repair Quantity"),
            (data.ng_quantity, "NG Quantity"),
        ):
            require_whole_quantity(value, job.unit, label)
        _, inspected, passed, repair, ng = validate_inspection_quantities(
            job.current_quantity, data.inspection_quantity, data.pass_quantity, data.repair_quantity, data.ng_quantity
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    repair_process = await db.get(WipProcess, data.repair_process_code) if data.repair_process_code else None
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
            detail="Repair Process must be active, type Repair, and belong to the same Plant",
        )
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
            raise HTTPException(status_code=422, detail="Repair Route is not valid for this Product")
    standard = (
        await db.execute(
            select(ProductProcessStandard)
            .where(
                ProductProcessStandard.product_code == job.product_code,
                ProductProcessStandard.process_code == job.process_code,
                ProductProcessStandard.is_active.is_(True),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    exceeded = ng_limit_exceeded(
        inspected,
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
    record = QualityInspection(
        quality_number=await generate_quality_number(db, data.inspection_date),
        inspection_date=data.inspection_date,
        shift=data.shift,
        job_id=job.id,
        product_code=job.product_code,
        product_name=product.part_name,
        description=product.description,
        lot_number=job.lot_number,
        lot_segment_code=job.lot_segment_code,
        plant_code=job.plant_code,
        unit=job.unit,
        before_process_code=job.process_code,
        before_process_name=process.name,
        inspection_quantity=inspected,
        pass_quantity=passed,
        repair_quantity=repair,
        ng_quantity=ng,
        repair_process_code=repair_process.code if repair_process else None,
        repair_route_code=repair_route.code if repair_route else None,
        ng_limit_exceeded=exceeded,
        ng_override_by=current_user.id if exceeded else None,
        ng_override_at=datetime.now(timezone.utc) if exceeded else None,
        ng_override_reason=data.ng_override_reason.strip() if exceeded and data.ng_override_reason else None,
        problem=data.problem,
        notes=data.notes,
        performed_by=current_user.id,
        performed_by_name=f"{current_user.first_name} {current_user.last_name}".strip(),
    )
    db.add(record)
    await db.flush()
    job.current_quantity -= inspected
    job.status = next_job_status(job.current_quantity)
    for outcome, amount, target_process, target_status in (
        ("P", passed, job.process_code, WipLotStatus.awaiting_finish_goods),
        (
            "R",
            repair,
            repair_step.process_code if repair_step else repair_process.code if repair_process else job.process_code,
            WipLotStatus.queued,
        ),
        ("N", ng, job.process_code, WipLotStatus.ng),
    ):
        if amount > 0:
            db.add(
                WipLotJob(
                    source_transfer_number=job.source_transfer_number,
                    sales_order_item_id=job.sales_order_item_id,
                    parent_job_id=job.id,
                    production_execution_id=job.production_execution_id,
                    repair_route_code=repair_route.code if outcome == "R" and repair_route else None,
                    repair_step_order=repair_step.step_order if outcome == "R" and repair_step else None,
                    repair_return_process_code=(
                        repair_route.return_process_code if outcome == "R" and repair_route else None
                    ),
                    process_code=target_process,
                    product_code=job.product_code,
                    lot_number=job.lot_number,
                    lot_segment_code=child_segment_code(job.lot_segment_code, record.id, f"Q{outcome}"),
                    plant_code=job.plant_code,
                    unit=job.unit,
                    input_quantity=amount,
                    current_quantity=amount,
                    status=target_status,
                )
            )
    await db.commit()
    await db.refresh(record)
    return await inspection_response(db, record)


@router.post("/inspections/{inspection_id}/reverse", response_model=QualityInspectionResponse)
async def reverse_quality_inspection(
    inspection_id: int,
    data: QualityInspectionReverse,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QualityInspectionResponse:
    access = await current_access(db, current_user)
    ensure_can_reverse(access, current_user)
    record = (
        await db.execute(select(QualityInspection).where(QualityInspection.id == inspection_id).with_for_update())
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quality inspection not found")
    if record.reversed_at:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Quality inspection has already been reversed")
    job = (await db.execute(select(WipLotJob).where(WipLotJob.id == record.job_id).with_for_update())).scalar_one()
    children = list(
        (
            await db.execute(select(WipLotJob).where(WipLotJob.parent_job_id == job.id).with_for_update())
        ).scalars()
    )
    child_ids = [child.id for child in children]
    finish_receipt_child_ids = set(
        (
            await db.execute(
                select(FinishGoodReceipt.source_wip_job_id).where(FinishGoodReceipt.source_wip_job_id.in_(child_ids))
            )
        )
        .scalars()
        .all()
    ) if child_ids else set()
    has_downstream_activity = False
    if child_ids:
        has_downstream_activity = bool(
            await db.scalar(select(func.count()).select_from(WipLotJob).where(WipLotJob.parent_job_id.in_(child_ids)))
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
                select(func.count()).select_from(ProductionExecution).where(ProductionExecution.job_id.in_(child_ids))
            )
        )
    try:
        ensure_quality_inspection_reversible(job.status, job.current_quantity, len(children), has_downstream_activity)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    for child in children:
        if child.id in finish_receipt_child_ids:
            # Preserve the immutable Finished Good receipt audit trail, even
            # when that receipt was already reversed.
            child.current_quantity = 0
            child.status = WipLotStatus.reversed
        else:
            await db.delete(child)
    job.current_quantity += record.inspection_quantity
    job.status = WipLotStatus.awaiting_qc
    record.reversed_by = current_user.id
    record.reversed_at = datetime.now(timezone.utc)
    record.reversal_reason = data.reason
    await db.commit()
    await db.refresh(record)
    return await inspection_response(db, record)
