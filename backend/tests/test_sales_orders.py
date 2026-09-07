from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.middleware import is_sales_order_path
from app.models import AccessLevel, SalesOrderStatus
from app.module_permissions import ensure_department_head, resolve_department_access
from app.sales_order_services import (
    bom_would_create_cycle,
    calculate_sales_line_amount,
    calculate_sales_total,
    ensure_sales_waiting_review,
    expand_bom_leaf_requirements,
    format_sales_order_number,
)
from app.schemas import SalesOrderCreate


def user(user_id: str = "130826000", active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        is_active=active,
        access_level=AccessLevel.staff,
    )


def department(pic: str | None, head: str | None) -> SimpleNamespace:
    return SimpleNamespace(pic_user_id=pic, head_user_id=head)


def valid_order_data() -> dict:
    return {
        "po_receipt_date": date(2026, 8, 13),
        "customer_po_date": date(2026, 8, 12),
        "customer_po_number": "CPO-001",
        "customer_code": "CUS",
        "delivery_date": date(2026, 8, 20),
        "order_type": "regular",
        "items": [
            {
                "product_code": "PRD",
                "quantity_grams": Decimal("1000.000"),
                "unit_price": Decimal("2.5555"),
            }
        ],
    }


def test_sales_order_middleware_path_match_is_segment_safe() -> None:
    assert is_sales_order_path("/api/v1/sales-orders")
    assert is_sales_order_path("/api/v1/sales-orders/SO-130826-000")
    assert not is_sales_order_path("/api/v1/sales-orders-report")


def test_sales_pic_and_head_access_but_only_head_reviews() -> None:
    pic = resolve_department_access(user("PIC"), department("PIC", "HEAD"))
    head = resolve_department_access(user("HEAD"), department("PIC", "HEAD"))
    outsider = resolve_department_access(user("OTHER"), department("PIC", "HEAD"))

    assert pic.can_access and not pic.can_review
    assert head.can_access and head.can_review
    assert not outsider.can_access
    with pytest.raises(HTTPException) as error:
        ensure_department_head(pic, "Sales")
    assert error.value.status_code == 403


def test_sales_order_number_and_decimal_total() -> None:
    assert format_sales_order_number(date(2026, 8, 13), 0) == "SO-130826-000"
    first = calculate_sales_line_amount(Decimal("1000.000"), Decimal("2.5555"))
    second = calculate_sales_line_amount(Decimal("250.000"), Decimal("1.2000"))
    assert first == Decimal("2555.50")
    assert calculate_sales_total([first, second]) == Decimal("2855.50")


def test_sales_order_terminal_status_is_read_only() -> None:
    ensure_sales_waiting_review(SalesOrderStatus.waiting_review)
    for terminal_status in (SalesOrderStatus.approved, SalesOrderStatus.rejected):
        with pytest.raises(HTTPException) as error:
            ensure_sales_waiting_review(terminal_status)
        assert error.value.status_code == 409


def test_sales_order_validates_dates_and_unique_products() -> None:
    invalid_date = valid_order_data()
    invalid_date["po_receipt_date"] = date(2026, 8, 11)
    with pytest.raises(ValidationError, match="receipt date"):
        SalesOrderCreate(**invalid_date)

    duplicate = valid_order_data()
    duplicate["items"] = [duplicate["items"][0], duplicate["items"][0]]
    with pytest.raises(ValidationError, match="same product"):
        SalesOrderCreate(**duplicate)


def test_sales_order_accepts_supported_order_types() -> None:
    for order_type in ("mass_pro", "job_order", "trial"):
        data = valid_order_data()
        data["order_type"] = order_type
        assert SalesOrderCreate(**data).order_type.value == order_type


def test_sales_order_maps_legacy_order_types() -> None:
    expected = {
        "regular": "mass_pro",
        "sample": "job_order",
        "replacement": "job_order",
        "trial": "trial",
    }
    for old_value, new_value in expected.items():
        data = valid_order_data()
        data["order_type"] = old_value
        assert SalesOrderCreate(**data).order_type.value == new_value


def bom(output: str, material: str, quantity: str, unit: str = "pcs") -> SimpleNamespace:
    return SimpleNamespace(
        finished_product_code=output,
        material_product_code=material,
        quantity=Decimal(quantity),
        unit=unit,
    )


def test_multilevel_bom_allocates_only_leaf_raw_materials() -> None:
    rows = [
        bom("FG-ABC", "WIP-OP2", "1"),
        bom("WIP-OP2", "WIP-OP1", "3"),
        bom("WIP-OP1", "RM-ALPHA", "2", "kg"),
    ]

    assert expand_bom_leaf_requirements("FG-ABC", Decimal("10"), rows) == [
        ("RM-ALPHA", Decimal("60"), "kg")
    ]


def test_bom_cycle_is_detected_before_saving_wip_bom() -> None:
    rows = [bom("WIP-OP2", "WIP-OP1", "1")]

    assert bom_would_create_cycle("WIP-OP1", ["WIP-OP2"], rows) is True
