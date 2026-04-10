"""One-shot snapshot of pyModeS 2.21.1 output over the tests/data/ corpus.

Run with pyModeS 2.21.1 in a transient virtualenv (2.22.0 is not
published on PyPI; 2.21.1 is the latest v2 release):

    uv run --no-project --with pyModeS==2.21.1 python scripts/snapshot_v2.py

Reads the three CSVs under tests/data/, dedups by hex, caps each DF
bucket at 200 messages, dispatches to v2 functions based on DF/TC/BDS,
and writes tests/fixtures/golden_v2.json sorted by hex.

The output is committed to the repo. Re-run this script only when:
- V2_DEPRECATED_KEYS or V2_VALUE_TOLERANCE change in meaning
- The dispatch table below gains new v2 function coverage
- The source CSVs in tests/data/ change
"""

from __future__ import annotations

import contextlib
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

# v2 imports — only valid under
# `uv run --no-project --with pyModeS==2.21.1`. We keep these as
# plain imports and let the script crash loudly if the wrong env
# is used.
from pyModeS import adsb, allcall, bds, commb, common  # type: ignore[import-not-found]

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "tests" / "data"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "golden_v2.json"
PER_DF_CAP = 200

CSV_FILES = [
    DATA_DIR / "sample_data_adsb.csv",
    DATA_DIR / "sample_data_commb_df20.csv",
    DATA_DIR / "sample_data_commb_df21.csv",
]


def _extract_hex_msg(row: list[str]) -> str | None:
    """Pick the Mode-S message cell from a CSV row.

    The three CSVs have inconsistent column layouts:
    - sample_data_adsb.csv:        timestamp, hex, icao, tc
    - sample_data_commb_df20.csv:  timestamp, icao, hex
    - sample_data_commb_df21.csv:  timestamp, icao, hex
    Mode-S long messages are 28 hex chars and short are 14, while
    ICAO addresses are always 6. Picking the longest all-hex cell
    reliably distinguishes them regardless of column order.
    """
    best: str | None = None
    for cell in row:
        s = cell.strip().lower().lstrip("\ufeff")
        if len(s) not in (14, 28):
            continue
        try:
            int(s, 16)
        except ValueError:
            continue
        if best is None or len(s) > len(best):
            best = s
    return best


def _load_corpus() -> list[str]:
    """Load hex strings from all three CSVs, dedup, cap per DF."""
    seen: set[str] = set()
    per_df: dict[int, list[str]] = defaultdict(list)

    for path in CSV_FILES:
        with path.open() as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2:
                    continue
                hex_msg = _extract_hex_msg(row)
                if not hex_msg or hex_msg in seen:
                    continue
                seen.add(hex_msg)
                try:
                    df = common.df(hex_msg)
                except Exception:
                    continue
                if len(per_df[df]) < PER_DF_CAP:
                    per_df[df].append(hex_msg)

    # Flatten, sorted by hex for deterministic output
    return sorted(msg for msgs in per_df.values() for msg in msgs)


def _safe_call(fn, *args, **kwargs):
    """Call a v2 function, swallowing exceptions and returning None."""
    try:
        val = fn(*args, **kwargs)
    except Exception:
        return None
    # Normalize NaN → None so tests can compare with v3's None semantics
    if isinstance(val, float) and math.isnan(val):
        return None
    return val


def _decode_v2(msg: str) -> dict[str, Any]:
    """Run every applicable v2 decoder on `msg` and return a dict."""
    out: dict[str, Any] = {}

    try:
        df = common.df(msg)
    except Exception as e:
        return {"_v2_error": f"common.df: {e}"}

    out["df"] = df

    with contextlib.suppress(Exception):
        out["icao"] = common.icao(msg)

    if df in (4, 20):
        out["altitude"] = _safe_call(common.altcode, msg)

    if df in (5, 21):
        out["squawk"] = _safe_call(common.idcode, msg)

    if df == 11:
        out["capability"] = _safe_call(allcall.interrogator, msg)

    if df == 17:
        tc = _safe_call(common.typecode, msg)
        out["typecode"] = tc
        if tc is None:
            return out

        if 1 <= tc <= 4:  # identification
            out["callsign"] = _safe_call(adsb.callsign, msg)
            out["category"] = _safe_call(adsb.category, msg)

        if 5 <= tc <= 8:  # surface position
            out["cpr_format"] = _safe_call(adsb.oe_flag, msg)
            v = _safe_call(adsb.surface_velocity, msg)
            if v is not None:
                out["groundspeed"] = v[0]
                out["track"] = v[1]

        if 9 <= tc <= 18:  # airborne position (baro altitude)
            out["altitude"] = _safe_call(adsb.altitude, msg)
            out["cpr_format"] = _safe_call(adsb.oe_flag, msg)

        if tc == 19:  # velocity
            v = _safe_call(adsb.velocity, msg)
            if v is not None:
                spd, trk, vr, t = v
                if t == "GS":
                    out["groundspeed"] = spd
                    out["track"] = trk
                elif t == "TAS":
                    out["airspeed"] = spd
                    out["airspeed_type"] = "TAS"
                    out["heading"] = trk
                elif t == "IAS":
                    out["airspeed"] = spd
                    out["airspeed_type"] = "IAS"
                    out["heading"] = trk
                out["vertical_rate"] = vr

        if 20 <= tc <= 22:  # airborne position (GNSS altitude)
            out["altitude"] = _safe_call(adsb.altitude, msg)
            out["cpr_format"] = _safe_call(adsb.oe_flag, msg)

    if df in (20, 21):
        bds_code = _safe_call(bds.infer, msg, mrar=True)
        if bds_code:
            out["bds"] = bds_code

        if bds_code == "BDS20":
            out["callsign"] = _safe_call(commb.cs20, msg)

        if bds_code == "BDS40":
            out["selected_altitude_mcp"] = _safe_call(commb.selalt40mcp, msg)
            out["selected_altitude_fms"] = _safe_call(commb.selalt40fms, msg)
            out["baro_pressure_setting"] = _safe_call(commb.p40baro, msg)

        if bds_code == "BDS50":
            out["roll"] = _safe_call(commb.roll50, msg)
            out["true_track"] = _safe_call(commb.trk50, msg)
            out["track_rate"] = _safe_call(commb.rtrk50, msg)
            out["groundspeed"] = _safe_call(commb.gs50, msg)
            out["true_airspeed"] = _safe_call(commb.tas50, msg)

        if bds_code == "BDS60":
            out["magnetic_heading"] = _safe_call(commb.hdg60, msg)
            out["indicated_airspeed"] = _safe_call(commb.ias60, msg)
            out["mach"] = _safe_call(commb.mach60, msg)
            out["baro_vertical_rate"] = _safe_call(commb.vr60baro, msg)
            out["inertial_vertical_rate"] = _safe_call(commb.vr60ins, msg)

    # Drop keys whose value is None — v3 omits missing fields entirely,
    # so comparing None == None is meaningless and just bloats the JSON.
    return {k: v for k, v in out.items() if v is not None}


def main() -> None:
    corpus = _load_corpus()
    per_df: dict[int, int] = defaultdict(int)
    results: dict[str, dict[str, Any]] = {}
    for msg in corpus:
        decoded = _decode_v2(msg)
        results[msg] = decoded
        per_df[decoded.get("df", -1)] += 1

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FIXTURE_PATH.open("w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"Wrote {FIXTURE_PATH} with {len(results)} messages")
    print(f"Per-DF counts: {dict(sorted(per_df.items()))}")
    unique_keys: set[str] = set()
    for d in results.values():
        unique_keys.update(d.keys())
    print(f"Unique keys across corpus: {sorted(unique_keys)}")


if __name__ == "__main__":
    main()
