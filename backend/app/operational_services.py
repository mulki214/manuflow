from datetime import datetime
from decimal import Decimal

WEIGHT_UNITS = {"gram", "kg"}
DISCRETE_UNITS = {"pcs", "bar", "pail"}


def require_whole_quantity(value: Decimal, unit: str, label: str = "Quantity") -> None:
    """Reject fractional quantities for countable inventory units."""
    if unit in DISCRETE_UNITS and value != value.to_integral_value():
        raise ValueError(f"{label} must be a whole number for {unit}")


def to_grams(value: Decimal, unit: str) -> Decimal:
    """Normalize weight without pretending count/volume units are convertible."""
    if unit == "kg":
        return value * Decimal("1000")
    if unit == "gram":
        return value
    raise ValueError(f"Unit {unit} is not a weight unit")


def from_grams(value: Decimal, unit: str) -> Decimal:
    """Convert a canonical gram balance back to a document weight unit."""
    if unit == "kg":
        return value / Decimal("1000")
    if unit == "gram":
        return value
    raise ValueError(f"Unit {unit} is not a weight unit")


def inventory_unit(unit: str) -> str:
    """Weight inventory is always persisted in grams; other units stay discrete."""
    return "gram" if unit in WEIGHT_UNITS else unit


def to_inventory_quantity(value: Decimal, unit: str) -> Decimal:
    return to_grams(value, unit) if unit in WEIGHT_UNITS else value


def from_inventory_quantity(value: Decimal, document_unit: str) -> Decimal:
    return from_grams(value, document_unit) if document_unit in WEIGHT_UNITS else value


def display_quantity(value: Decimal, document_unit: str) -> Decimal | int:
    """Return document quantities without cosmetic decimal zeros for count units."""
    converted = from_inventory_quantity(value, document_unit)
    return int(converted) if document_unit in DISCRETE_UNITS else converted


def shipment_weight_kg(quantity: Decimal, unit: str, gross_weight_grams: Decimal) -> Decimal:
    if unit == "kg":
        return quantity
    if unit == "gram":
        return quantity / Decimal("1000")
    return quantity * gross_weight_grams / Decimal("1000")


def actual_cycle_time_seconds(
    started_at: datetime | None,
    ended_at: datetime | None,
    break_duration_minutes: int,
    good_quantity: Decimal,
) -> Decimal | None:
    if not started_at or not ended_at or good_quantity <= 0:
        return None
    productive_seconds = Decimal(str((ended_at - started_at).total_seconds())) - Decimal(break_duration_minutes * 60)
    if productive_seconds <= 0:
        raise ValueError("Break duration must be shorter than the production time range")
    return (productive_seconds / good_quantity).quantize(Decimal("0.001"))


def ng_limit_exceeded(
    processed_quantity: Decimal,
    ng_quantity: Decimal,
    maximum_quantity: Decimal | None,
    maximum_percent: Decimal | None,
) -> bool:
    if maximum_quantity is not None and ng_quantity > maximum_quantity:
        return True
    if maximum_percent is not None and processed_quantity > 0:
        return (ng_quantity * Decimal("100") / processed_quantity) > maximum_percent
    return False
