from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.document_services import purchase_order_pdf_bytes
from app.middleware import is_purchasing_path
from app.models import AccessLevel, PurchaseOrderStatus
from app.purchasing_permissions import (
    ensure_purchasing_head,
    resolve_purchasing_access,
)
from app.purchasing_services import (
    calculate_line_amount,
    calculate_purchase_totals,
    ensure_waiting_review,
    format_purchase_order_number,
    payment_due_date,
)
from app.schemas import PurchaseOrderCreate


def user(user_id: str = "130826000", active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        is_active=active,
        access_level=AccessLevel.staff,
    )


def department(pic: str | None, head: str | None) -> SimpleNamespace:
    return SimpleNamespace(pic_user_id=pic, head_user_id=head)


def multi_pic_department(pics: list[str], head: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        pic_user_id=pics[0] if pics else None,
        pics=[SimpleNamespace(id=user_id) for user_id in pics],
        head_user_id=head,
    )


def valid_order_data() -> dict:
    return {
        "po_date": date(2026, 8, 13),
        "supplier_code": "SUP",
        "requested_delivery_date": date(2026, 8, 20),
        "delivery_plant_code": "A1B2C",
        "items": [
            {
                "product_code": "PRD",
                "quantity_grams": Decimal("1250.500"),
                "unit_price": Decimal("2.2500"),
            }
        ],
    }


def test_purchasing_middleware_path_match_is_segment_safe() -> None:
    assert is_purchasing_path("/api/v1/purchasing")
    assert is_purchasing_path("/api/v1/purchasing/PO-130826-000")
    assert not is_purchasing_path("/api/v1/purchasing-report")
    assert not is_purchasing_path("/api/v1/master-data/products")


def test_only_department_pic_or_head_can_access_purchasing() -> None:
    pic_access = resolve_purchasing_access(user("PIC"), department("PIC", "HEAD"))
    head_access = resolve_purchasing_access(user("HEAD"), department("PIC", "HEAD"))
    outsider_access = resolve_purchasing_access(user("OTHER"), department("PIC", "HEAD"))

    assert pic_access.can_access and pic_access.is_pic and not pic_access.can_review
    assert head_access.can_access and head_access.is_head and head_access.can_review
    assert not outsider_access.can_access


def test_inactive_pic_cannot_access_and_only_head_can_review() -> None:
    inactive = resolve_purchasing_access(user("PIC", active=False), department("PIC", "HEAD"))
    pic = resolve_purchasing_access(user("PIC"), department("PIC", "HEAD"))
    assert not inactive.can_access
    with pytest.raises(HTTPException) as error:
        ensure_purchasing_head(pic)
    assert error.value.status_code == 403


def test_every_registered_department_pic_can_access() -> None:
    department_record = multi_pic_department(["PIC-1", "PIC-2"], "HEAD")
    assert resolve_purchasing_access(user("PIC-1"), department_record).is_pic
    assert resolve_purchasing_access(user("PIC-2"), department_record).is_pic
    assert not resolve_purchasing_access(user("OTHER"), department_record).can_access


def test_administrator_can_access_but_cannot_review_as_department_head() -> None:
    admin = user("ADMIN")
    admin.access_level = AccessLevel.administrator
    access = resolve_purchasing_access(admin, None)
    assert access.can_access
    assert not access.can_review


def test_purchase_order_number_and_payment_due_date() -> None:
    order_date = date(2026, 8, 13)
    assert format_purchase_order_number(order_date, 0) == "PO-130826-000"
    assert payment_due_date(order_date, 30) == date(2026, 9, 12)


def test_purchase_totals_use_decimal_rounding_and_subtract_pph23() -> None:
    first = calculate_line_amount(Decimal("1000.000"), Decimal("2.5555"))
    second = calculate_line_amount(Decimal("500.000"), Decimal("1.1250"))
    totals = calculate_purchase_totals(
        [first, second],
        discount_amount=Decimal("100.00"),
        ppn_rate=Decimal("11"),
        pph23_rate=Decimal("2"),
    )
    assert first == Decimal("2555.50")
    assert totals.subtotal == Decimal("3118.00")
    assert totals.ppn_amount == Decimal("331.98")
    assert totals.pph23_amount == Decimal("60.36")
    assert totals.grand_total == Decimal("3289.62")


def test_discount_cannot_exceed_subtotal() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        calculate_purchase_totals([Decimal("100")], Decimal("101"), Decimal("0"), Decimal("0"))


def test_approved_and_rejected_purchase_orders_are_read_only() -> None:
    ensure_waiting_review(PurchaseOrderStatus.waiting_review)
    for terminal_status in (PurchaseOrderStatus.approved, PurchaseOrderStatus.rejected):
        with pytest.raises(HTTPException) as error:
            ensure_waiting_review(terminal_status)
        assert error.value.status_code == 409


def test_purchase_order_requires_quotation_date_and_unique_products() -> None:
    with pytest.raises(ValidationError, match="Quotation date"):
        PurchaseOrderCreate(**valid_order_data(), quotation_reference="QUOT-01")

    duplicate = valid_order_data()
    duplicate["items"] = [duplicate["items"][0], duplicate["items"][0]]
    with pytest.raises(ValidationError, match="same product"):
        PurchaseOrderCreate(**duplicate)


def test_purchase_order_item_accepts_supported_inventory_units() -> None:
    for unit in ("pcs", "bar", "liter", "pail", "kg", "gram"):
        data = valid_order_data()
        data["items"][0]["unit"] = unit
        assert PurchaseOrderCreate(**data).items[0].unit.value == unit


def test_purchase_order_pdf_contains_document_and_signatures() -> None:
    order = SimpleNamespace(
        po_number="PO-030926-001",
        po_date=date(2026, 9, 3),
        supplier_name="Supplier Test",
        delivery_plant_name="Plant A",
        requested_delivery_date=date(2026, 9, 10),
        delivery_address="Industrial Estate",
        quotation_reference="QT-01",
        currency="IDR",
        subtotal=Decimal("10000"),
        discount_amount=Decimal("0"),
        ppn_rate=Decimal("11"),
        ppn_amount=Decimal("1100"),
        pph23_rate=Decimal("2"),
        pph23_amount=Decimal("200"),
        grand_total=Decimal("10900"),
        creator_qr_payload="creator-signature",
        approval_qr_payload="approver-signature",
        created_by_name="Creator",
        reviewed_by_name="Head",
        items=[
            SimpleNamespace(
                line_number=1,
                product_code="PRD",
                description="Product Test",
                quantity_grams=Decimal("10"),
                unit="pcs",
                unit_price=Decimal("1000"),
                amount=Decimal("10000"),
            )
        ],
    )
    document = purchase_order_pdf_bytes(order)
    assert document.startswith(b"%PDF")
    assert len(document) > 1000
