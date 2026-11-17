from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.config import settings
from app.models import AccessLevel, PurchaseRequestItemApprovalStatus, PurchaseRequestStatus
from app.routers.purchase_requests import approve


@pytest.mark.asyncio
async def test_approving_free_text_request_records_decision_without_creating_po() -> None:
    now = datetime(2026, 11, 17, tzinfo=timezone.utc)
    requester = SimpleNamespace(id="REQUESTER", first_name="Ada", last_name="User")
    approver = SimpleNamespace(
        id="APPROVER",
        first_name="Pat",
        last_name="Purchasing",
        access_level=AccessLevel.head,
        department_code=settings.purchasing_department_code,
    )
    item = SimpleNamespace(
        id=12,
        line_number=1,
        product_code=None,
        sales_order_item_id=None,
        part_name="Custom tooling",
        part_no="TOOL-01",
        description="Special fixture",
        quantity=Decimal("3"),
        unit="pcs",
        remark="For maintenance",
        purchase_order_number=None,
        approval_status=PurchaseRequestItemApprovalStatus.pending,
        approved_quantity=None,
        review_reason=None,
        reviewed_by=None,
        reviewed_at=None,
    )
    record = SimpleNamespace(
        request_number="PR-171126-001",
        request_type="free_text",
        sales_order_number=None,
        request_date=date(2026, 11, 17),
        requested_delivery_date=date(2026, 11, 24),
        delivery_plant_code="PLANT",
        department_code="GENERAL",
        notes="",
        status=PurchaseRequestStatus.waiting_review,
        created_by=requester.id,
        reviewed_by=None,
        reviewed_at=None,
        rejection_reason=None,
        created_at=now,
        updated_at=now,
        items=[item],
    )

    class Result:
        def scalar_one_or_none(self):
            return record

    db = SimpleNamespace(
        execute=AsyncMock(return_value=Result()),
        get=AsyncMock(side_effect=lambda model, key: requester if key == requester.id else approver),
        commit=AsyncMock(),
        add=Mock(),
    )

    response = await approve(
        request_number=record.request_number,
        data=None,
        db=db,
        current_user=approver,
    )

    assert response.status == PurchaseRequestStatus.approved
    assert response.sales_order_number is None
    assert response.items[0].product_code is None
    assert response.items[0].part_name == "Custom tooling"
    assert response.items[0].purchase_order_number is None
    assert item.approval_status == PurchaseRequestItemApprovalStatus.approved
    assert item.approved_quantity == Decimal("3")
    db.commit.assert_awaited_once()
    db.add.assert_not_called()
