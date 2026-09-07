from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DailyProductionSequence, WipLotStatus
from app.warehouse_services import quantity


def format_production_number(process_date: date, sequence: int) -> str:
    if sequence < 0 or sequence > 999:
        raise ValueError("Production daily sequence must be between 000 and 999")
    return f"WP-{process_date:%d%m%y}-{sequence:03d}"


async def generate_production_number(db: AsyncSession, process_date: date | None = None) -> str:
    current_date = process_date or datetime.now(ZoneInfo(settings.business_timezone)).date()
    statement = (
        insert(DailyProductionSequence)
        .values(sequence_date=current_date, last_value=0)
        .on_conflict_do_update(
            index_elements=[DailyProductionSequence.sequence_date],
            set_={"last_value": DailyProductionSequence.last_value + 1},
        )
        .returning(DailyProductionSequence.last_value)
    )
    sequence = (await db.execute(statement)).scalar_one()
    if sequence > 999:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Production daily sequence limit reached")
    return format_production_number(current_date, sequence)


def validate_execution_quantities(
    available: Decimal,
    processing: Decimal,
    good: Decimal,
    repair: Decimal,
    ng: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    values = tuple(quantity(value) for value in (available, processing, good, repair, ng))
    normalized_available, normalized_processing, normalized_good, normalized_repair, normalized_ng = values
    if normalized_processing <= 0:
        raise ValueError("Processing Quantity must be greater than zero")
    if normalized_processing > normalized_available:
        raise ValueError("Processing Quantity exceeds available WIP Quantity")
    if normalized_good + normalized_repair + normalized_ng != normalized_processing:
        raise ValueError("Good, Repair, and NG Quantity must equal Processing Quantity")
    return values


def next_job_status(remaining_quantity: Decimal) -> WipLotStatus:
    return WipLotStatus.queued if quantity(remaining_quantity) > 0 else WipLotStatus.completed


def ensure_production_execution_reversible(
    child_count: int, has_downstream_activity: bool, has_consumables: bool
) -> None:
    if child_count == 0:
        raise ValueError("Production execution result is incomplete and cannot be reversed")
    if has_consumables:
        raise ValueError("Production execution cannot be reversed because consumables were recorded")
    if has_downstream_activity:
        raise ValueError("Production execution cannot be reversed because its result has already been used")


def child_segment_code(parent_segment: str, execution_id: int, outcome: str) -> str:
    return f"{parent_segment[:32]}-{execution_id}{outcome}"[:40]
