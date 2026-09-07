from datetime import date

import pytest
from pydantic import ValidationError

from app.models import Gender
from app.schemas import UserCreate
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
