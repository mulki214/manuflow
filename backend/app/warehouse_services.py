from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DailyWarehouseTransferSequence, WarehouseTransferStatus, WipLotStatus

QUANTITY_PRECISION = Decimal("0.001")


def quantity(value: Decimal) -> Decimal:
    return value.quantize(QUANTITY_PRECISION, rounding=ROUND_HALF_UP)


def format_transfer_number(transfer_date: date, sequence: int) -> str:
    if sequence < 0 or sequence > 999:
        raise ValueError("Warehouse transfer daily sequence must be between 000 and 999")
    return f"SM-{transfer_date:%d%m%y}-{sequence:03d}"


async def generate_transfer_number(db: AsyncSession, transfer_date: date | None = None) -> str:
    current_date = transfer_date or datetime.now(ZoneInfo(settings.business_timezone)).date()
    statement = (
        insert(DailyWarehouseTransferSequence)
        .values(sequence_date=current_date, last_value=0)
        .on_conflict_do_update(
            index_elements=[DailyWarehouseTransferSequence.sequence_date],
            set_={"last_value": DailyWarehouseTransferSequence.last_value + 1},
        )
        .returning(DailyWarehouseTransferSequence.last_value)
    )
    sequence = (await db.execute(statement)).scalar_one()
    if sequence > 999:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Daily Warehouse transfer limit reached")
    return format_transfer_number(current_date, sequence)


def move_quantity(source_balance: Decimal, destination_balance: Decimal, moved: Decimal) -> tuple[Decimal, Decimal]:
    normalized = quantity(moved)
    if normalized <= 0:
        raise ValueError("Transfer quantity must be greater than zero")
    source_after = quantity(source_balance - normalized)
    destination_after = quantity(destination_balance + normalized)
    if source_after < 0:
        raise ValueError("Transfer quantity exceeds available Lot stock")
    return source_after, destination_after


def ensure_transfer_posted(current_status: WarehouseTransferStatus) -> None:
    if current_status != WarehouseTransferStatus.posted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Warehouse transfer has already been reversed")


def ensure_wip_job_reversible(job_status: WipLotStatus, current: Decimal, original: Decimal) -> None:
    if job_status != WipLotStatus.queued or quantity(current) != quantity(original):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transfer cannot be reversed because its WIP quantity has already been processed",
        )
