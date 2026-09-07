from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.middleware import is_production_path
from app.models import WipLotStatus, WipProcessType
from app.production_services import (
    child_segment_code,
    ensure_production_execution_reversible,
    format_production_number,
    next_job_status,
    validate_execution_quantities,
)
from app.routers.production import ensure_production_process_type


def test_production_middleware_path_match_is_segment_safe() -> None:
    assert is_production_path("/api/v1/production")
    assert is_production_path("/api/v1/production/processes")
    assert not is_production_path("/api/v1/production-report")


def test_production_owns_production_and_repair_process_types() -> None:
    ensure_production_process_type(WipProcessType.production)
    ensure_production_process_type(WipProcessType.repair)


def test_production_rejects_quality_process_type() -> None:
    with pytest.raises(HTTPException) as error:
        ensure_production_process_type(WipProcessType.quality)
    assert error.value.status_code == 422


def test_production_execution_conserves_partial_outcomes() -> None:
    values = validate_execution_quantities(Decimal("100"), Decimal("50"), Decimal("30"), Decimal("15"), Decimal("5"))
    assert values[1:] == (Decimal("50.000"), Decimal("30.000"), Decimal("15.000"), Decimal("5.000"))
    assert next_job_status(Decimal("50")) == WipLotStatus.queued
    assert next_job_status(Decimal("0")) == WipLotStatus.completed


def test_production_execution_rejects_overdraw_and_unbalanced_outcomes() -> None:
    with pytest.raises(ValueError, match="exceeds available"):
        validate_execution_quantities(Decimal("10"), Decimal("10.001"), Decimal("10.001"), Decimal("0"), Decimal("0"))
    with pytest.raises(ValueError, match="must equal"):
        validate_execution_quantities(Decimal("10"), Decimal("10"), Decimal("5"), Decimal("3"), Decimal("1"))


def test_production_number_and_child_segment_are_traceable() -> None:
    assert format_production_number(date(2026, 8, 19), 0) == "WP-190826-000"
    assert child_segment_code("LOT-001-SM-190826-000", 12, "G") == "LOT-001-SM-190826-000-12G"


def test_production_reverse_rejects_used_output_or_consumables() -> None:
    ensure_production_execution_reversible(1, False, False)
    with pytest.raises(ValueError, match="already been used"):
        ensure_production_execution_reversible(1, True, False)
    with pytest.raises(ValueError, match="consumables"):
        ensure_production_execution_reversible(1, False, True)
