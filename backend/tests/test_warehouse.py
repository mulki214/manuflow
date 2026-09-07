from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.middleware import is_warehouse_path
from app.models import WarehouseTransferStatus, WipLotStatus
from app.routers.production import router as production_router
from app.routers.warehouse import router as warehouse_router
from app.schemas import WarehouseMaterialTransferCreate
from app.warehouse_services import (
    ensure_transfer_posted,
    ensure_wip_job_reversible,
    format_transfer_number,
    move_quantity,
)


def test_warehouse_middleware_path_match_is_segment_safe() -> None:
    assert is_warehouse_path("/api/v1/warehouse")
    assert is_warehouse_path("/api/v1/warehouse/SM-190826-000")
    assert not is_warehouse_path("/api/v1/warehouse-report")


def test_warehouse_exposes_read_only_production_destination_lookup() -> None:
    warehouse_routes = {
        (route.path, method) for route in warehouse_router.routes for method in getattr(route, "methods", set())
    }
    production_routes = {
        (route.path, method) for route in production_router.routes for method in getattr(route, "methods", set())
    }
    assert ("/warehouse/production-destinations", "GET") in warehouse_routes
    assert ("/warehouse/wip-processes", "GET") not in warehouse_routes
    assert ("/warehouse/wip-processes", "POST") not in warehouse_routes
    assert ("/production/processes", "GET") in production_routes
    assert ("/production/processes", "POST") in production_routes


def test_transfer_number_uses_daily_sequence() -> None:
    assert format_transfer_number(date(2026, 8, 19), 0) == "SM-190826-000"
    assert format_transfer_number(date(2026, 8, 19), 999) == "SM-190826-999"
    with pytest.raises(ValueError):
        format_transfer_number(date(2026, 8, 19), 1000)


def test_partial_transfer_preserves_source_and_destination_quantity() -> None:
    source, destination = move_quantity(Decimal("100"), Decimal("20"), Decimal("15.1254"))
    assert source == Decimal("84.875")
    assert destination == Decimal("35.125")
    assert source + destination == Decimal("120.000")


def test_transfer_rejects_zero_and_negative_stock() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        move_quantity(Decimal("100"), Decimal("0"), Decimal("0"))
    with pytest.raises(ValueError, match="exceeds available"):
        move_quantity(Decimal("10"), Decimal("0"), Decimal("10.001"))


def test_transfer_schema_requires_exactly_one_destination() -> None:
    base = {
        "transfer_date": date(2026, 8, 19),
        "source_lot_id": 1,
        "quantity": Decimal("10"),
    }
    wip = WarehouseMaterialTransferCreate(**base, destination_type="wip", destination_process_code="CUT")
    finished_goods = WarehouseMaterialTransferCreate(
        **base,
        destination_type="finished_goods",
        destination_location_code="FG-A",
    )
    assert wip.destination_process_code == "CUT"
    assert finished_goods.destination_location_code == "FG-A"
    with pytest.raises(ValidationError):
        WarehouseMaterialTransferCreate(**base, destination_type="wip", destination_location_code="FG-A")


def test_only_untouched_queued_wip_job_can_be_reversed() -> None:
    ensure_wip_job_reversible(WipLotStatus.queued, Decimal("10"), Decimal("10"))
    for job_status, current in ((WipLotStatus.in_process, Decimal("10")), (WipLotStatus.queued, Decimal("9"))):
        with pytest.raises(HTTPException) as error:
            ensure_wip_job_reversible(job_status, current, Decimal("10"))
        assert error.value.status_code == 409


def test_reversed_transfer_is_terminal() -> None:
    ensure_transfer_posted(WarehouseTransferStatus.posted)
    with pytest.raises(HTTPException) as error:
        ensure_transfer_posted(WarehouseTransferStatus.reversed)
    assert error.value.status_code == 409
