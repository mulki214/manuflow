from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DailyReceivingSequence, ReceivingStatus

GRAMS = Decimal("0.001")


def grams(value: Decimal) -> Decimal:
    return value.quantize(GRAMS, rounding=ROUND_HALF_UP)


def format_receipt_number(receipt_date: date, sequence: int) -> str:
    if sequence < 0 or sequence > 999:
        raise ValueError("Receiving daily sequence must be between 000 and 999")
    return f"RCV-{receipt_date:%d%m%y}-{sequence:03d}"


async def generate_receipt_number(db: AsyncSession, receipt_date: date | None = None) -> str:
    current_date = receipt_date or datetime.now(ZoneInfo(settings.business_timezone)).date()
    statement = (
        insert(DailyReceivingSequence)
        .values(sequence_date=current_date, last_value=0)
        .on_conflict_do_update(
            index_elements=[DailyReceivingSequence.sequence_date],
            set_={"last_value": DailyReceivingSequence.last_value + 1},
        )
        .returning(DailyReceivingSequence.last_value)
    )
    sequence = (await db.execute(statement)).scalar_one()
    if sequence > 999:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Daily Receiving limit reached")
    return format_receipt_number(current_date, sequence)


def apply_stock_delta(current_product: Decimal, current_lot: Decimal, delta: Decimal) -> tuple[Decimal, Decimal]:
    product_after = grams(current_product + delta)
    lot_after = grams(current_lot + delta)
    if product_after < 0 or lot_after < 0:
        raise ValueError("Inventory movement would cause negative stock")
    return product_after, lot_after


def ensure_receiving_posted(current_status: ReceivingStatus) -> None:
    if current_status != ReceivingStatus.posted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Receiving has already been reversed")
