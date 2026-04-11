"""Golden-file oracle test: v3 decode output must match pyModeS 2.21.1.

Loads tests/fixtures/golden_v2.json (a deduplicated + per-DF-capped
snapshot of pyModeS 2.21.1 output on tests/data/*.csv) and asserts
that pyModeS.decode() produces matching values for every v2-emitted
key.

Renamed keys are mapped via pyModeS._v2_compat.V2_DEPRECATED_KEYS.
Numeric fields with known small divergence use absolute tolerances
from V2_VALUE_TOLERANCE. Unknown mismatches fail the test with a
precise message identifying the hex and the mismatched key.

If the snapshot itself recorded a v2 error for a given message
(``_v2_error`` key), the comparison is skipped for that message.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pyModeS import decode
from pyModeS._v2_compat import V2_DEPRECATED_KEYS, V2_VALUE_TOLERANCE

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_v2.json"


def _load_golden() -> dict[str, dict[str, Any]]:
    try:
        with FIXTURE_PATH.open() as f:
            data: dict[str, dict[str, Any]] = json.load(f)
    except FileNotFoundError as e:
        raise RuntimeError(
            f"golden_v2.json fixture not found at {FIXTURE_PATH}. "
            f"Run `uv run --no-project --with 'pyModeS==2.21.1' "
            f"python scripts/snapshot_v2.py` to regenerate it."
        ) from e
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"golden_v2.json at {FIXTURE_PATH} is malformed (JSON decode failed "
            f"at line {e.lineno}). Re-run scripts/snapshot_v2.py to regenerate."
        ) from e
    return data


def _bds_one(token: str) -> str:
    """Convert a single 'BDSxy' token to v3's 'x,y' style."""
    if token.startswith("BDS") and len(token) == 5:
        return f"{token[3]},{token[4]}"
    return token


def _bds_normalize(v2_bds: str | None) -> str | set[str] | None:
    """Map v2's BDS value to v3's style.

    v2 may return a single 'BDS10'-style code or, when its
    heuristic infer() can't pick a winner, a comma-separated
    list like 'BDS17,BDS45'. v3 always picks a single winner
    via the two-phase dispatch, so a match means the v3 code
    is *one of* v2's candidates. Return a set in the multi
    case so the comparison can use ``in`` semantics.
    """
    if not v2_bds or not isinstance(v2_bds, str):
        return v2_bds
    if "," in v2_bds:
        return {_bds_one(tok) for tok in v2_bds.split(",")}
    return _bds_one(v2_bds)


def _callsign_normalize(val: Any) -> Any:
    """Strip v2's '_' pad characters from trailing callsign slots.

    v2 emitted '_' for unused 6-bit slots beyond the callsign;
    v3 strips whitespace and never emits '_' pads, so we trim
    them from the v2 side for comparison.
    """
    if isinstance(val, str):
        return val.rstrip("_")
    return val


def _icao_normalize(val: Any) -> Any:
    """Lowercase ICAO strings for v2↔v3 comparison.

    v3 always emits ICAO as uppercase hex; v2 emits lowercase.
    Normalize both sides by lowercasing, done in the test rather
    than in the snapshot so the snapshot stays faithful to v2.
    """
    if isinstance(val, str):
        return val.lower()
    return val


def _mismatch(msg: str, key: str, v2_value: Any, v3_value: Any) -> str:
    return f"mismatch on {msg[:16]}... key={key!r}: v2={v2_value!r} v3={v3_value!r}"


GOLDEN = _load_golden()


@pytest.mark.parametrize("msg", sorted(GOLDEN.keys()))
def test_v3_matches_v2_golden(msg: str) -> None:
    v2_output = GOLDEN[msg]
    if "_v2_error" in v2_output:
        pytest.skip(f"v2 itself failed on {msg[:16]}: {v2_output['_v2_error']}")

    v3_output = decode(msg)

    for v2_key, v2_value in v2_output.items():
        v3_key = V2_DEPRECATED_KEYS.get(v2_key, v2_key)

        # Normalize the bds key v2↔v3 style difference in the test,
        # not in the snapshot, so the snapshot stays faithful to v2.
        if v2_key == "bds":
            v2_value = _bds_normalize(v2_value)
        if v2_key == "icao":
            v2_value = _icao_normalize(v2_value)
        if v2_key == "callsign":
            v2_value = _callsign_normalize(v2_value)

        v3_value = v3_output.get(v3_key)
        if v2_key == "icao":
            v3_value = _icao_normalize(v3_value)
        tol = V2_VALUE_TOLERANCE.get(v3_key)

        if isinstance(v2_value, set):
            # bds: v2 emitted a candidate list, v3 picked one; match
            # if v3's single winner is one of v2's candidates.
            assert v3_value in v2_value, _mismatch(msg, v2_key, v2_value, v3_value)
        elif (
            tol is not None
            and isinstance(v3_value, (int, float))
            and isinstance(v2_value, (int, float))
        ):
            assert abs(v3_value - v2_value) < tol, _mismatch(
                msg, v2_key, v2_value, v3_value
            )
        else:
            assert v3_value == v2_value, _mismatch(msg, v2_key, v2_value, v3_value)


def test_golden_fixture_has_entries() -> None:
    """Fixture must not be empty (catches accidental wipe of golden_v2.json)."""
    assert len(GOLDEN) >= 100, f"golden fixture only has {len(GOLDEN)} entries"
