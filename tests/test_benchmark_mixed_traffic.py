import runpy
from pathlib import Path
from typing import Any

import pytest

_SCRIPT = Path(__file__).parents[1] / "scripts/benchmark_mixed_traffic.py"
_NAMESPACE = runpy.run_path(str(_SCRIPT))
_position_comparison = _NAMESPACE["_position_comparison"]
_require_position_quality = _NAMESPACE["_require_position_quality"]


def _result(
    api: str,
    positions: list[tuple[int, float, float]],
) -> dict[str, Any]:
    return {
        "api": api,
        "position_samples": positions,
        "event_counts": {"position": len(positions)},
    }


def test_position_comparison_reports_missing_overlap_as_unavailable():
    baseline = _result("v2", [(0, 52.0, 4.0)])
    candidate = _result("v3-working", [(1, 52.0, 4.0)])

    comparison = _position_comparison(baseline, candidate)

    assert comparison["shared"] == 0
    assert comparison["agreement_100m_pct"] is None
    assert comparison["median_distance_m"] is None
    assert comparison["max_distance_m"] is None


def test_position_quality_rejects_insufficient_yield():
    v2_positions = [(row, 52.0, 4.0) for row in range(10)]
    results = [
        _result("v2", v2_positions),
        _result("v3", v2_positions[:2]),
        _result("v3-working", v2_positions[:7]),
    ]

    with pytest.raises(RuntimeError, match="below the required v2 coverage"):
        _require_position_quality(
            results,
            min_v2_yield_pct=80.0,
            min_agreement_pct=99.0,
        )


def test_position_quality_rejects_coordinate_disagreement():
    results = [
        _result("v2", [(0, 52.0, 4.0)]),
        _result("v3", [(0, 52.0, 4.0)]),
        _result("v3-working", [(0, 53.0, 5.0)]),
    ]

    with pytest.raises(RuntimeError, match="agreement is below"):
        _require_position_quality(
            results,
            min_v2_yield_pct=80.0,
            min_agreement_pct=99.0,
        )


def test_position_quality_accepts_expected_improvement():
    v2_positions = [(row, 52.0, 4.0) for row in range(10)]
    results = [
        _result("v2", v2_positions),
        _result("v3", v2_positions[:2]),
        _result("v3-working", v2_positions[:8]),
    ]

    _require_position_quality(
        results,
        min_v2_yield_pct=80.0,
        min_agreement_pct=99.0,
    )
