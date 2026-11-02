from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyInvoiceSequence


def invoice_line_amount(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return (quantity * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def invoice_totals(
    amounts: list[Decimal], discount_amount: Decimal, tax_rate: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    subtotal = sum(amounts, Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    discount = discount_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if discount > subtotal:
        raise ValueError("Discount cannot exceed invoice subtotal")
    taxable = subtotal - discount
    tax = (taxable * tax_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return subtotal, tax, taxable + tax


def invoice_quantity_available(delivered_quantity: Decimal, invoiced_quantity: Decimal) -> Decimal:
    return max(delivered_quantity - invoiced_quantity, Decimal("0"))


def format_invoice_number(invoice_date: date, sequence: int) -> str:
    if sequence < 1 or sequence > 999:
        raise ValueError("Daily invoice limit of 999 reached")
    return f"INV-{invoice_date:%y%m%d}-{sequence:03d}"


async def generate_invoice_number(db: AsyncSession, invoice_date: date) -> str:
    statement = (
        insert(DailyInvoiceSequence)
        .values(sequence_date=invoice_date, last_value=1)
        .on_conflict_do_update(
            index_elements=[DailyInvoiceSequence.sequence_date],
            set_={"last_value": DailyInvoiceSequence.last_value + 1},
        )
        .returning(DailyInvoiceSequence.last_value)
    )
    sequence = (await db.execute(statement)).scalar_one()
    if sequence > 999:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The daily invoice limit of 999 has been reached",
        )
    return format_invoice_number(invoice_date, sequence)
