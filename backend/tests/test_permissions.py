from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models import AccessLevel
from app.permissions import can_manage_department, ensure_can_assign_access, ensure_can_manage
from app.schemas import PasswordChangeRequest


def actor(access_level: AccessLevel, department_code: str = "PROD") -> SimpleNamespace:
    return SimpleNamespace(access_level=access_level, department_code=department_code)


def test_administrator_can_manage_every_department() -> None:
    assert can_manage_department(actor(AccessLevel.administrator), "FIN")


def test_head_can_only_manage_own_department() -> None:
    head = actor(AccessLevel.head)
    assert can_manage_department(head, "PROD")
    assert not can_manage_department(head, "FIN")


def test_staff_can_submit_but_cannot_edit_submitted_data() -> None:
    with pytest.raises(HTTPException) as error:
        ensure_can_manage(actor(AccessLevel.staff), "PROD")
    assert error.value.status_code == 403


def test_non_admin_cannot_assign_administrator_access() -> None:
    with pytest.raises(HTTPException) as error:
        ensure_can_assign_access(actor(AccessLevel.head), AccessLevel.administrator)
    assert error.value.status_code == 403


def test_password_change_requires_a_different_password() -> None:
    with pytest.raises(ValueError):
        PasswordChangeRequest(current_password="Password123!", new_password="Password123!")
