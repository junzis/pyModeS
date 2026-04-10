"""Offline smoke test for scripts/build_airport_db.py.

We do not hit the network in CI. Instead we exercise filter_and_sort
and write_module with a synthetic row set and verify the output
contract: sorted, deterministic, correct dict shape.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "build_airport_db.py"


def _load_script() -> object:
    spec = importlib.util.spec_from_file_location("build_airport_db", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_filter_drops_small_airports():
    mod = _load_script()
    rows = [
        {
            "ident": "EHAM",
            "type": "large_airport",
            "latitude_deg": "52.30806",
            "longitude_deg": "4.76417",
        },
        {
            "ident": "ZZZZ",
            "type": "small_airport",
            "latitude_deg": "1.0",
            "longitude_deg": "2.0",
        },
        {
            "ident": "KLAX",
            "type": "medium_airport",
            "latitude_deg": "33.9425",
            "longitude_deg": "-118.40801",
        },
    ]
    out = mod.filter_and_sort(rows)  # type: ignore[attr-defined]
    codes = [r["icao"] for r in out]
    assert codes == ["EHAM", "KLAX"]  # sorted, small dropped


def test_filter_drops_non_icao_idents():
    mod = _load_script()
    rows = [
        # Real 4-letter ICAO — keep
        {
            "ident": "EHAM",
            "type": "large_airport",
            "latitude_deg": "52.3",
            "longitude_deg": "4.76",
        },
        # Surrogate IDs OurAirports issues when no ICAO exists — drop
        {
            "ident": "5A8",
            "type": "medium_airport",
            "latitude_deg": "59.28",
            "longitude_deg": "-158.61",
        },
        {
            "ident": "07FA",
            "type": "medium_airport",
            "latitude_deg": "25.32",
            "longitude_deg": "-80.27",
        },
        {
            "ident": "AE-0221",
            "type": "medium_airport",
            "latitude_deg": "24.44",
            "longitude_deg": "54.51",
        },
        # Lowercase — drop (ICAO codes are canonically uppercase)
        {
            "ident": "eham",
            "type": "large_airport",
            "latitude_deg": "52.3",
            "longitude_deg": "4.76",
        },
    ]
    out = mod.filter_and_sort(rows)  # type: ignore[attr-defined]
    assert [r["icao"] for r in out] == ["EHAM"]
    # Output rows should not carry the airport name
    assert "name" not in out[0]


def test_filter_drops_invalid_coords():
    mod = _load_script()
    rows = [
        {
            "ident": "OKAY",
            "type": "large_airport",
            "latitude_deg": "1.0",
            "longitude_deg": "2.0",
        },
        {
            "ident": "BAD1",
            "type": "large_airport",
            "latitude_deg": "",
            "longitude_deg": "2.0",
        },
    ]
    out = mod.filter_and_sort(rows)  # type: ignore[attr-defined]
    assert [r["icao"] for r in out] == ["OKAY"]


def test_write_module_produces_importable_file(tmp_path, monkeypatch):
    mod = _load_script()
    target = tmp_path / "airports.py"
    monkeypatch.setattr(mod, "OUTPUT", target)
    rows = [
        {"icao": "AAAA", "lat": 1.0, "lon": 2.0},
        {"icao": "BBBB", "lat": 3.5, "lon": 4.25},
    ]
    mod.write_module(rows)  # type: ignore[attr-defined]
    text = target.read_text()
    assert '"AAAA": (1.00000, 2.00000)' in text
    assert '"BBBB": (3.50000, 4.25000)' in text
    # Generated file should NOT contain a names dict
    assert "AIRPORT_NAMES" not in text
    # Compile the generated file as a sanity check
    compile(text, str(target), "exec")
