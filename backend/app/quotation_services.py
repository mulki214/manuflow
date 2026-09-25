from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyQuotationSequence


def calculate_quotation_line_amount(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return (quantity * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_quotation_totals(
    amounts: list[Decimal], discount_amount: Decimal, tax_rate: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    subtotal = sum(amounts, Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    taxable = max(subtotal - discount_amount, Decimal("0"))
    tax_amount = (taxable * tax_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return subtotal, tax_amount, taxable + tax_amount


async def generate_quotation_number(db: AsyncSession, quotation_date: date) -> str:
    sequence = await db.get(DailyQuotationSequence, quotation_date, with_for_update=True)
    if sequence is None:
        sequence = DailyQuotationSequence(sequence_date=quotation_date, last_value=1)
        db.add(sequence)
        number = 1
    else:
        sequence.last_value += 1
        number = sequence.last_value
    if number > 999:
        raise ValueError("Daily quotation limit of 999 reached")
    return f"QT-{quotation_date.strftime('%y%m%d')}-{number:03d}"
