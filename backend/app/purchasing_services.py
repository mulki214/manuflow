from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DailyPurchaseOrderSequence, PurchaseOrderStatus

MONEY = Decimal("0.01")


@dataclass(frozen=True)
class PurchaseTotals:
    subtotal: Decimal
    discount_amount: Decimal
    ppn_amount: Decimal
    pph23_amount: Decimal
    grand_total: Decimal


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def calculate_line_amount(quantity_grams: Decimal, unit_price: Decimal) -> Decimal:
    return money(quantity_grams * unit_price)


def calculate_purchase_totals(
    line_amounts: list[Decimal],
    discount_amount: Decimal,
    ppn_rate: Decimal,
    pph23_rate: Decimal,
) -> PurchaseTotals:
    subtotal = money(sum(line_amounts, Decimal("0")))
    discount = money(discount_amount)
    if discount > subtotal:
        raise ValueError("Discount amount cannot exceed subtotal")
    taxable_amount = subtotal - discount
    ppn_amount = money(taxable_amount * ppn_rate / Decimal("100"))
    pph23_amount = money(taxable_amount * pph23_rate / Decimal("100"))
    return PurchaseTotals(
        subtotal=subtotal,
        discount_amount=discount,
        ppn_amount=ppn_amount,
        pph23_amount=pph23_amount,
        grand_total=money(taxable_amount + ppn_amount - pph23_amount),
    )


def format_purchase_order_number(order_date: date, sequence: int) -> str:
    if sequence < 0 or sequence > 999:
        raise ValueError("Purchase order daily sequence must be between 000 and 999")
    return f"PO-{order_date:%d%m%y}-{sequence:03d}"


async def generate_purchase_order_number(db: AsyncSession, order_date: date | None = None) -> str:
    current_date = order_date or datetime.now(ZoneInfo(settings.business_timezone)).date()
    statement = (
        insert(DailyPurchaseOrderSequence)
        .values(sequence_date=current_date, last_value=0)
        .on_conflict_do_update(
            index_elements=[DailyPurchaseOrderSequence.sequence_date],
            set_={"last_value": DailyPurchaseOrderSequence.last_value + 1},
        )
        .returning(DailyPurchaseOrderSequence.last_value)
    )
    sequence = (await db.execute(statement)).scalar_one()
    if sequence > 999:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The daily purchase order limit of 999 has been reached",
        )
    return format_purchase_order_number(current_date, sequence)


def payment_due_date(po_date: date, payment_terms_days: int) -> date:
    return po_date + timedelta(days=payment_terms_days)


def ensure_waiting_review(current_status: PurchaseOrderStatus) -> None:
    if current_status != PurchaseOrderStatus.waiting_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approved or rejected purchase orders are read-only",
        )
