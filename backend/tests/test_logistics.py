from datetime import date, datetime

import pytest

from app.logistics_services import format_document_number
from app.middleware import is_delivery_path, is_finish_good_path
from app.models import Delivery, DeliveryStatus, FinishGoodReceipt, FinishGoodStatus
from app.routers.logistics import delivery_response, delivery_router, finish_response, finish_router
from app.schemas import BillOfMaterialReplace, BomItemInput, DeliveryBatchCreate, DeliveryConfirm


def test_logistics_document_numbers_use_daily_sequences() -> None:
    assert format_document_number("FG", date(2026, 8, 21), 0) == "FG-210826-000"
    assert format_document_number("DLV", date(2026, 8, 21), 999) == "DLV-210826-999"
    with pytest.raises(ValueError):
        format_document_number("DLV", date(2026, 8, 21), 1000)


def test_logistics_paths_are_segment_safe() -> None:
    assert is_finish_good_path("/api/v1/finish-goods/queue")
    assert is_delivery_path("/api/v1/delivery")
    assert not is_delivery_path("/api/v1/delivery-report")


def test_delivery_response_only_allows_reversing_posted_records() -> None:
    record = Delivery(
        delivery_number="DLV-210826-000",
        delivery_date=date(2026, 8, 21),
        sales_order_item_id=1,
        sales_order_number="SO-001",
        customer_name="Customer A",
        product_code="FG-001",
        lot_id=10,
        lot_number="LOT-1",
        quantity=10,
        unit="pcs",
        notes="",
        status=DeliveryStatus.posted,
        performed_by="USR-001",
        created_at=datetime(2026, 8, 21),
    )

    assert delivery_response(record).can_reverse is True
    assert delivery_response(record).status == "delivered"
    assert delivery_response(record).can_confirm_delivery is False
    record.status = DeliveryStatus.reversed
    assert delivery_response(record).can_reverse is False


def test_finish_good_response_only_allows_reversing_posted_receipts() -> None:
    receipt = FinishGoodReceipt(
        receipt_number="FG-210826-000",
        receipt_date=date(2026, 8, 21),
        source_wip_job_id=1,
        product_code="FG-001",
        lot_number="LOT-1",
        lot_segment_code="LOT-1-01",
        quantity=10,
        unit="pcs",
        plant_code="PL001",
        storage_location_code="LOC-001",
        lot_id=1,
        status=FinishGoodStatus.posted,
        notes="",
        performed_by="USR-001",
        created_at=datetime(2026, 8, 21),
    )

    assert finish_response(receipt).can_reverse is True
    receipt.status = FinishGoodStatus.reversed
    assert finish_response(receipt).can_reverse is False


def test_bill_of_material_rejects_duplicate_material_products() -> None:
    with pytest.raises(ValueError, match="same material"):
        BillOfMaterialReplace(
            items=[
                BomItemInput(material_product_code="MAT-001", quantity=1, unit="pcs"),
                BomItemInput(material_product_code="MAT-001", quantity=2, unit="pcs"),
            ]
        )


def test_finish_good_and_delivery_routes_expose_the_required_lifecycle_actions() -> None:
    finish_routes = {
        (route.path, method) for route in finish_router.routes for method in getattr(route, "methods", set())
    }
    delivery_routes = {
        (route.path, method) for route in delivery_router.routes for method in getattr(route, "methods", set())
    }
    assert ("/finish-goods/queue", "GET") in finish_routes
    assert ("/finish-goods/queue/{job_id}/post", "POST") in finish_routes
    assert ("/finish-goods/{receipt_number}/reverse", "POST") in finish_routes
    assert ("/delivery/lookup/sales-order-items", "GET") in delivery_routes
    assert ("/delivery/lookup/finish-good-lots", "GET") in delivery_routes
    assert ("/delivery/batch", "POST") in delivery_routes
    assert ("/delivery/{delivery_number_value}", "GET") in delivery_routes
    assert ("/delivery/{delivery_number_value}/deliver", "POST") in delivery_routes
    assert ("/delivery/{delivery_number_value}/reverse", "POST") in delivery_routes


def test_delivery_batch_rejects_duplicate_item_and_lot() -> None:
    with pytest.raises(ValueError, match="can only appear once"):
        DeliveryBatchCreate.model_validate(
            {
                "delivery_date": "2026-08-21",
                "driver_name": "Driver A",
                "lines": [
                    {"sales_order_item_id": 1, "lot_id": 5, "quantity": 1},
                    {"sales_order_item_id": 1, "lot_id": 5, "quantity": 2},
                ],
            }
        )


def test_delivery_confirmation_accepts_optional_notes() -> None:
    assert DeliveryConfirm(notes="Received by customer").notes == "Received by customer"
