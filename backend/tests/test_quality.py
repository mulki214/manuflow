from datetime import date
from decimal import Decimal

import pytest

from app.middleware import is_quality_path
from app.models import WipLotStatus
from app.quality_services import (
    ensure_quality_inspection_reversible,
    format_quality_number,
    validate_inspection_quantities,
)


def test_quality_middleware_path_match_is_segment_safe() -> None:
    assert is_quality_path("/api/v1/quality")
    assert is_quality_path("/api/v1/quality/wip-jobs")
    assert not is_quality_path("/api/v1/quality-report")


def test_quality_inspection_conserves_partial_outcomes() -> None:
    values = validate_inspection_quantities(Decimal("100"), Decimal("50"), Decimal("30"), Decimal("15"), Decimal("5"))
    assert values[1:] == (Decimal("50.000"), Decimal("30.000"), Decimal("15.000"), Decimal("5.000"))


def test_quality_inspection_rejects_overdraw_and_unbalanced_outcomes() -> None:
    with pytest.raises(ValueError, match="exceeds available"):
        validate_inspection_quantities(Decimal("10"), Decimal("10.001"), Decimal("10.001"), Decimal("0"), Decimal("0"))
    with pytest.raises(ValueError, match="must equal"):
        validate_inspection_quantities(Decimal("10"), Decimal("10"), Decimal("5"), Decimal("3"), Decimal("1"))


def test_quality_number_uses_daily_sequence() -> None:
    assert format_quality_number(date(2026, 8, 21), 0) == "QC-210826-000"
    assert format_quality_number(date(2026, 8, 21), 999) == "QC-210826-999"
    with pytest.raises(ValueError):
        format_quality_number(date(2026, 8, 21), 1000)


def test_passed_quality_result_waits_for_finished_goods() -> None:
    assert WipLotStatus.awaiting_finish_goods.value == "awaiting_finish_goods"


def test_quality_reverse_only_allows_unused_completed_result() -> None:
    ensure_quality_inspection_reversible(WipLotStatus.completed, Decimal("0"), 1, False)
    with pytest.raises(ValueError, match="already been used"):
        ensure_quality_inspection_reversible(WipLotStatus.completed, Decimal("0"), 1, True)
    with pytest.raises(ValueError, match="latest fully completed"):
        ensure_quality_inspection_reversible(WipLotStatus.awaiting_qc, Decimal("100"), 1, False)
