from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.operational_services import (
    actual_cycle_time_seconds,
    from_inventory_quantity,
    inventory_unit,
    ng_limit_exceeded,
    shipment_weight_kg,
    to_grams,
    to_inventory_quantity,
)


def test_weight_units_are_normalized_to_grams() -> None:
    assert to_grams(Decimal("1.5"), "kg") == Decimal("1500.0")
    assert to_grams(Decimal("250"), "gram") == Decimal("250")
    with pytest.raises(ValueError):
        to_grams(Decimal("1"), "pcs")


def test_inventory_boundary_preserves_document_units() -> None:
    assert inventory_unit("kg") == "gram"
    assert inventory_unit("pcs") == "pcs"
    assert to_inventory_quantity(Decimal("1.25"), "kg") == Decimal("1250.00")
    assert to_inventory_quantity(Decimal("4"), "pcs") == Decimal("4")
    assert from_inventory_quantity(Decimal("1250"), "kg") == Decimal("1.25")


def test_shipment_weight_uses_product_weight_for_piece_units() -> None:
    assert shipment_weight_kg(Decimal("10"), "pcs", Decimal("250")) == Decimal("2.5")
    assert shipment_weight_kg(Decimal("2500"), "gram", Decimal("999")) == Decimal("2.5")


def test_cycle_time_excludes_break_and_uses_good_output() -> None:
    started = datetime(2026, 9, 3, 8, tzinfo=timezone.utc)
    ended = datetime(2026, 9, 3, 9, tzinfo=timezone.utc)
    assert actual_cycle_time_seconds(started, ended, 10, Decimal("100")) == Decimal("30.000")


def test_ng_limit_supports_quantity_and_percentage() -> None:
    assert ng_limit_exceeded(Decimal("100"), Decimal("6"), Decimal("5"), None)
    assert ng_limit_exceeded(Decimal("100"), Decimal("3"), None, Decimal("2"))
    assert not ng_limit_exceeded(Decimal("100"), Decimal("2"), Decimal("5"), Decimal("2"))
