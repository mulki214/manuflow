from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, Protocol
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DailySalesOrderSequence, SalesOrderStatus
from app.purchasing_services import money


class BomLine(Protocol):
    finished_product_code: str
    material_product_code: str
    quantity: Decimal
    unit: str


def expand_bom_leaf_requirements(
    product_code: str, ordered_quantity: Decimal, bom_rows: Iterable[BomLine]
) -> list[tuple[str, Decimal, str]]:
    """Resolve a product's active BOM into quantities of its leaf materials.

    A leaf is a product without an active BOM. This keeps an SO allocation at
    the supplier-receivable material level even when its product moves through
    one or more WIP stages before becoming a Finished Good.
    """
    bom_by_product: dict[str, list[BomLine]] = defaultdict(list)
    for bom in bom_rows:
        bom_by_product[bom.finished_product_code].append(bom)

    requirements: dict[str, tuple[Decimal, str]] = {}

    def visit(code: str, quantity: Decimal, unit: str | None, ancestry: tuple[str, ...]) -> None:
        if code in ancestry:
            cycle = " -> ".join((*ancestry, code))
            raise ValueError(f"Circular BOM detected: {cycle}")
        components = bom_by_product.get(code, [])
        if not components:
            existing = requirements.get(code)
            if existing and existing[1] != unit:
                raise ValueError(f"Material {code} has inconsistent units across its BOM paths")
            requirements[code] = ((existing[0] if existing else Decimal("0")) + quantity, unit or "")
            return
        for component in components:
            leaf_quantity = quantity * Decimal(component.quantity)
            visit(component.material_product_code, leaf_quantity, component.unit, (*ancestry, code))

    if bom_by_product.get(product_code):
        visit(product_code, ordered_quantity, None, ())
    return [
        (material_code, quantity, unit)
        for material_code, (quantity, unit) in requirements.items()
    ]


def bom_would_create_cycle(
    output_product_code: str, material_product_codes: Iterable[str], bom_rows: Iterable[BomLine]
) -> bool:
    """Return whether replacing one product's BOM would introduce a cycle."""
    graph: dict[str, set[str]] = defaultdict(set)
    for bom in bom_rows:
        if bom.finished_product_code != output_product_code:
            graph[bom.finished_product_code].add(bom.material_product_code)
    graph[output_product_code].update(material_product_codes)

    def reaches_target(code: str, visited: set[str]) -> bool:
        if code == output_product_code:
            return True
        if code in visited:
            return False
        return any(reaches_target(child, {*visited, code}) for child in graph.get(code, set()))

    return any(reaches_target(material, set()) for material in graph[output_product_code])


def format_sales_order_number(order_date: date, sequence: int) -> str:
    if sequence < 0 or sequence > 999:
        raise ValueError("Sales order daily sequence must be between 000 and 999")
    return f"SO-{order_date:%d%m%y}-{sequence:03d}"


async def generate_sales_order_number(db: AsyncSession, order_date: date | None = None) -> str:
    current_date = order_date or datetime.now(ZoneInfo(settings.business_timezone)).date()
    statement = (
        insert(DailySalesOrderSequence)
        .values(sequence_date=current_date, last_value=0)
        .on_conflict_do_update(
            index_elements=[DailySalesOrderSequence.sequence_date],
            set_={"last_value": DailySalesOrderSequence.last_value + 1},
        )
        .returning(DailySalesOrderSequence.last_value)
    )
    sequence = (await db.execute(statement)).scalar_one()
    if sequence > 999:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The daily sales order limit of 999 has been reached",
        )
    return format_sales_order_number(current_date, sequence)


def calculate_sales_line_amount(quantity_grams: Decimal, unit_price: Decimal) -> Decimal:
    return money(quantity_grams * unit_price)


def calculate_sales_total(line_amounts: list[Decimal]) -> Decimal:
    return money(sum(line_amounts, Decimal("0")))


def ensure_sales_waiting_review(current_status: SalesOrderStatus) -> None:
    if current_status != SalesOrderStatus.waiting_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approved or rejected sales orders are read-only",
        )
