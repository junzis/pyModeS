"""Build src/pymodes/data/airports.py from OurAirports CSV.

Run periodically before a release to refresh the curated airport
database. Not run at install time — the generated file is committed
to the repo so users don't pay download cost on install.

Usage:
    uv run scripts/build_airport_db.py
    uv run ruff format src/pymodes/data/airports.py
"""

from __future__ import annotations

import csv
import sys
import urllib.request
from pathlib import Path

SOURCE = "https://davidmegginson.github.io/ourairports-data/airports.csv"
OUTPUT = Path(__file__).parent.parent / "src" / "pymodes" / "data" / "airports.py"
ALLOWED_TYPES = ("large_airport", "medium_airport")

HEADER = '''# ruff: noqa: E501, RUF001
"""Curated airport database.

Generated from OurAirports dataset by scripts/build_airport_db.py.
Source: https://davidmegginson.github.io/ourairports-data/airports.csv
Filter: large_airport + medium_airport with an assigned 4-letter ICAO code.

Do not edit by hand — rerun the build script to regenerate.
"""

AIRPORTS: dict[str, tuple[float, float]] = {
'''


def _is_icao_code(ident: str) -> bool:
    """Return True if `ident` is a plausible 4-letter ICAO code.

    OurAirports emits two styles of `ident`: real 4-letter ICAO
    codes (e.g. "EHAM", "KJFK") and surrogate identifiers for
    airports without an assigned ICAO code (e.g. "5A8", "07FA",
    "AE-0221"). We keep only the former.
    """
    return len(ident) == 4 and ident.isascii() and ident.isalpha() and ident.isupper()


def fetch_csv() -> list[dict[str, str]]:
    with urllib.request.urlopen(SOURCE) as resp:
        text = resp.read().decode("utf-8")
    reader = csv.DictReader(text.splitlines())
    return list(reader)


def filter_and_sort(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in rows:
        if row["type"] not in ALLOWED_TYPES:
            continue
        if not _is_icao_code(row["ident"]):
            continue
        try:
            lat = float(row["latitude_deg"])
            lon = float(row["longitude_deg"])
        except (KeyError, ValueError):
            continue
        out.append(
            {
                "icao": row["ident"],
                "name": row["name"],
                "lat": lat,
                "lon": lon,
            }
        )
    out.sort(key=lambda r: r["icao"])  # type: ignore[arg-type,return-value]
    return out


def _escape_name(name: str) -> str:
    return name.replace("\\", "\\\\").replace('"', '\\"')


def write_module(rows: list[dict[str, object]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w") as f:
        f.write(HEADER)
        for row in rows:
            f.write(f'    "{row["icao"]}": ({row["lat"]:.5f}, {row["lon"]:.5f}),\n')
        f.write("}\n\n")
        f.write("AIRPORT_NAMES: dict[str, str] = {\n")
        for row in rows:
            name = _escape_name(str(row["name"]))
            f.write(f'    "{row["icao"]}": "{name}",\n')
        f.write("}\n")


def build() -> int:
    try:
        rows = fetch_csv()
    except Exception as e:
        print(f"error: failed to fetch {SOURCE}: {e}", file=sys.stderr)
        return 1
    filtered = filter_and_sort(rows)
    write_module(filtered)
    print(f"wrote {len(filtered)} airports to {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(build())
