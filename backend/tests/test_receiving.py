from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.inventory_services import (
    apply_stock_delta,
    ensure_receiving_posted,
    format_receipt_number,
    grams,
)
from app.middleware import is_receiving_path
from app.models import AccessLevel, ReceivingStatus
from app.module_permissions import resolve_department_membership
from app.operational_services import require_whole_quantity
from app.schemas import ReceivingCreate, ReceivingReversal


def user(user_id: str, department_code: str, active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        department_code=department_code,
        is_active=active,
        access_level=AccessLevel.staff,
    )


def warehouse() -> SimpleNamespace:
    return SimpleNamespace(code="WAREHOUSE", pic_user_id="PIC", head_user_id="HEAD")


def test_receiving_middleware_path_match_is_segment_safe() -> None:
    assert is_receiving_path("/api/v1/receiving")
    assert is_receiving_path("/api/v1/receiving/RCV-140826-000")
    assert not is_receiving_path("/api/v1/receiving-report")


def test_all_active_warehouse_members_access_but_pic_head_are_identified() -> None:
    member = resolve_department_membership(user("STAFF", "WAREHOUSE"), warehouse())
    pic = resolve_department_membership(user("PIC", "WAREHOUSE"), warehouse())
    outsider = resolve_department_membership(user("OTHER", "SALES"), warehouse())
    inactive = resolve_department_membership(user("STAFF", "WAREHOUSE", active=False), warehouse())

    assert member.can_access and not member.is_pic and not member.is_head
    assert pic.can_access and pic.is_pic
    assert not outsider.can_access
    assert not inactive.can_access


def test_pic_and_head_can_access_department_outside_primary_membership() -> None:
    pic = resolve_department_membership(user("PIC", "PRODUCTION"), warehouse())
    head = resolve_department_membership(user("HEAD", "PRODUCTION"), warehouse())

    assert pic.can_access and pic.is_pic and not pic.is_head
    assert head.can_access and head.is_head and not head.is_pic


def test_administrator_can_access_receiving_without_warehouse_membership() -> None:
    admin = user("ADMIN", "GENERAL")
    admin.access_level = AccessLevel.administrator
    assert resolve_department_membership(admin, warehouse()).can_access


def test_receipt_number_and_gram_precision() -> None:
    assert format_receipt_number(date(2026, 8, 14), 0) == "RCV-140826-000"
    assert grams(Decimal("1000.1236")) == Decimal("1000.124")
    require_whole_quantity(Decimal("1000"), "pcs")
    with pytest.raises(ValueError, match="whole number"):
        require_whole_quantity(Decimal("0.5"), "pcs")
    require_whole_quantity(Decimal("0.5"), "liter")


def test_inventory_delta_updates_product_and_lot_together() -> None:
    product, lot = apply_stock_delta(Decimal("1500"), Decimal("500"), Decimal("250"))
    assert product == Decimal("1750.000")
    assert lot == Decimal("750.000")

    product, lot = apply_stock_delta(product, lot, Decimal("-300"))
    assert product == Decimal("1450.000")
    assert lot == Decimal("450.000")


def test_inventory_delta_rejects_negative_lot_even_when_product_has_stock() -> None:
    with pytest.raises(ValueError, match="negative stock"):
        apply_stock_delta(Decimal("10000"), Decimal("100"), Decimal("-101"))


def test_reversed_receiving_cannot_be_reversed_again() -> None:
    ensure_receiving_posted(ReceivingStatus.posted)
    with pytest.raises(HTTPException) as error:
        ensure_receiving_posted(ReceivingStatus.reversed)
    assert error.value.status_code == 409


def test_receiving_schema_requires_positive_quantity_and_reversal_reason() -> None:
    with pytest.raises(ValidationError):
        ReceivingCreate(
            receipt_date=date(2026, 8, 14),
            source_type="supplier",
            source_code="SUP",
            source_document_item_id=1,
            lot_number="LOT-01",
            quantity_grams=0,
            plant_code="A1B2C",
            storage_location_code="RACK",
        )
    with pytest.raises(ValidationError, match="internal transportation"):
        ReceivingCreate(
            receipt_date=date(2026, 8, 14),
            source_type="supplier",
            source_code="SUP",
            source_document_item_id=1,
            lot_number="LOT-01",
            quantity_grams=1,
            plant_code="A1B2C",
            storage_location_code="RACK",
            transport_source="internal",
        )
    with pytest.raises(ValidationError):
        ReceivingReversal(reason="x")


def test_receiving_schema_rejects_document_type_source_mismatch() -> None:
    with pytest.raises(ValidationError, match="Purchase Order Receiving"):
        ReceivingCreate(
            receipt_date=date(2026, 8, 14),
            source_type="supplier",
            source_code="SUP",
            source_document_item_id=1,
            document_type="purchase_order",
            lot_number="LOT-01",
            quantity_grams=1,
            plant_code="A1B2C",
            storage_location_code="RACK",
        )
