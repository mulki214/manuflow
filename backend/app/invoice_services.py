from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyInvoiceSequence

_ONES = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
)
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
_SCALES = ("", "thousand", "million", "billion", "trillion", "quadrillion")


def _integer_words(value: int) -> str:
    if value < 20:
        return _ONES[value]
    if value < 100:
        return _TENS[value // 10] + (f"-{_ONES[value % 10]}" if value % 10 else "")
    if value < 1000:
        remainder = value % 100
        return f"{_ONES[value // 100]} hundred" + (f" {_integer_words(remainder)}" if remainder else "")
    parts: list[str] = []
    scale_index = 0
    while value:
        group = value % 1000
        if group:
            if scale_index >= len(_SCALES):
                raise ValueError("Invoice amount is too large to spell out")
            suffix = _SCALES[scale_index]
            parts.append(_integer_words(group) + (f" {suffix}" if suffix else ""))
        value //= 1000
        scale_index += 1
    return " ".join(reversed(parts))


def invoice_amount_in_words(amount: Decimal, currency: str = "IDR") -> str:
    """Spell the amount in English; append fractional cents only when non-zero."""
    rounded = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded < 0:
        raise ValueError("Invoice amount cannot be negative")
    whole = int(rounded)
    fraction = int((rounded - whole) * 100)
    currency_names = {"IDR": "rupiah", "USD": "US dollars", "EUR": "euros", "GBP": "pounds"}
    currency_name = currency_names.get(currency.upper(), currency.upper())
    words = f"{_integer_words(whole)} {currency_name}"
    if fraction:
        words += f" and {fraction:02d}/100"
    result = f"{words} only"
    return result[0].upper() + result[1:]


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
