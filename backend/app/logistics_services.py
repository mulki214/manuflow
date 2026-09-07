from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyDeliverySequence, DailyFinishGoodSequence


def format_document_number(prefix: str, record_date: date, sequence: int) -> str:
    if not 0 <= sequence <= 999:
        raise ValueError("Daily sequence must be between 000 and 999")
    return f"{prefix}-{record_date:%d%m%y}-{sequence:03d}"


async def _number(db: AsyncSession, model: type, prefix: str, record_date: date) -> str:
    statement = (
        insert(model)
        .values(sequence_date=record_date, last_value=0)
        .on_conflict_do_update(index_elements=[model.sequence_date], set_={"last_value": model.last_value + 1})
        .returning(model.last_value)
    )
    sequence = (await db.execute(statement)).scalar_one()
    if sequence > 999:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Daily document sequence limit reached")
    return format_document_number(prefix, record_date, sequence)


async def finish_good_number(db: AsyncSession, record_date: date) -> str:
    return await _number(db, DailyFinishGoodSequence, "FG", record_date)


async def delivery_number(db: AsyncSession, record_date: date) -> str:
    return await _number(db, DailyDeliverySequence, "DLV", record_date)
