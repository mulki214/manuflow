from datetime import date

import pytest
from pydantic import ValidationError

from app.models import Gender
from app.schemas import PurchaseRequestCreate, PurchaseRequestItemInput, UserCreate
from app.services import format_user_id


def valid_user() -> dict:
    return {
        "first_name": "Andi",
        "last_name": "Mulki",
        "email": "andi@example.com",
        "gender": Gender.male,
        "role": "Administrator",
        "department_code": "GENERAL",
        "ktp_number": "1234567890123456",
        "password": "Secret123!",
    }


def test_user_create_normalizes_text() -> None:
    data = valid_user()
    data["first_name"] = "  Andi  "
    user = UserCreate(**data)
    assert user.first_name == "Andi"


@pytest.mark.parametrize("ktp", ["123", "abcdefghijklmnop", "12345678901234567"])
def test_user_rejects_invalid_ktp(ktp: str) -> None:
    data = valid_user()
    data["ktp_number"] = ktp
    with pytest.raises(ValidationError):
        UserCreate(**data)


def test_user_id_uses_date_and_three_digit_sequence() -> None:
    assert format_user_id(date(2026, 8, 8), 0) == "080826000"
    assert format_user_id(date(2026, 8, 8), 999) == "080826999"


def test_user_id_rejects_sequence_over_daily_limit() -> None:
    with pytest.raises(ValueError):
        format_user_id(date(2026, 8, 8), 1000)


def test_free_text_purchase_request_accepts_named_product_without_so_or_master_code() -> None:
    request = PurchaseRequestCreate(
        request_type="free_text",
        request_date=date(2026, 11, 17),
        requested_delivery_date=date(2026, 11, 24),
        delivery_plant_code="PLANT",
        items=[
            PurchaseRequestItemInput(
                part_name="Custom tooling",
                part_no="TOOL-01",
                description="Special fixture requested by maintenance",
                quantity=2,
                unit="pcs",
            )
        ],
    )

    assert request.sales_order_number is None
    assert request.items[0].product_code is None
    assert request.items[0].part_name == "Custom tooling"


def test_free_text_purchase_request_requires_name_and_rejects_master_product_code() -> None:
    common = {
        "request_type": "free_text",
        "request_date": date(2026, 11, 17),
        "requested_delivery_date": date(2026, 11, 24),
        "delivery_plant_code": "PLANT",
    }
    with pytest.raises(ValidationError):
        PurchaseRequestCreate(
            **common,
            items=[PurchaseRequestItemInput(quantity=1, unit="pcs")],
        )
    with pytest.raises(ValidationError):
        PurchaseRequestCreate(
            **common,
            items=[
                PurchaseRequestItemInput(
                    product_code="P-001",
                    part_name="Should not mix types",
                    quantity=1,
                    unit="pcs",
                )
            ],
        )


def test_master_data_purchase_request_still_requires_product_code() -> None:
    with pytest.raises(ValidationError):
        PurchaseRequestCreate(
            request_date=date(2026, 11, 17),
            requested_delivery_date=date(2026, 11, 24),
            delivery_plant_code="PLANT",
            sales_order_number="SO-171126-001",
            items=[PurchaseRequestItemInput(quantity=1, unit="pcs")],
        )
