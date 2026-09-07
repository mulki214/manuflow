from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DailyQualitySequence, WipLotStatus
from app.warehouse_services import quantity


def format_quality_number(inspection_date: date, sequence: int) -> str:
    if sequence < 0 or sequence > 999:
        raise ValueError("Quality daily sequence must be between 000 and 999")
    return f"QC-{inspection_date:%d%m%y}-{sequence:03d}"


async def generate_quality_number(db: AsyncSession, inspection_date: date | None = None) -> str:
    current_date = inspection_date or datetime.now(ZoneInfo(settings.business_timezone)).date()
    statement = (
        insert(DailyQualitySequence)
        .values(sequence_date=current_date, last_value=0)
        .on_conflict_do_update(
            index_elements=[DailyQualitySequence.sequence_date],
            set_={"last_value": DailyQualitySequence.last_value + 1},
        )
        .returning(DailyQualitySequence.last_value)
    )
    sequence = (await db.execute(statement)).scalar_one()
    if sequence > 999:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Quality daily sequence limit reached")
    return format_quality_number(current_date, sequence)


def validate_inspection_quantities(
    available: Decimal,
    inspection: Decimal,
    passed: Decimal,
    repair: Decimal,
    ng: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    values = tuple(quantity(value) for value in (available, inspection, passed, repair, ng))
    normalized_available, normalized_inspection, normalized_pass, normalized_repair, normalized_ng = values
    if normalized_inspection <= 0:
        raise ValueError("Inspection Quantity must be greater than zero")
    if normalized_inspection > normalized_available:
        raise ValueError("Inspection Quantity exceeds available Quality Queue Quantity")
    if normalized_pass + normalized_repair + normalized_ng != normalized_inspection:
        raise ValueError("Pass, Repair, and NG Quantity must equal Inspection Quantity")
    return values


def ensure_quality_inspection_reversible(
    source_status: WipLotStatus,
    source_quantity: Decimal,
    child_count: int,
    has_downstream_activity: bool,
) -> None:
    if source_status != WipLotStatus.completed or quantity(source_quantity) != Decimal("0"):
        raise ValueError("Only the latest fully completed Quality inspection can be reversed")
    if child_count == 0:
        raise ValueError("Quality inspection result is incomplete and cannot be reversed")
    if has_downstream_activity:
        raise ValueError("Quality inspection cannot be reversed because its result has already been used")
