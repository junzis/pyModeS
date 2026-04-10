"""Implementation of ``modes decode`` subcommand.

Two modes:

- Single-message: ``modes decode HEX`` → one JSON object on stdout
- File-based: ``modes decode --file PATH`` → one JSON line per input

The file path ``-`` reads from stdin. File format is auto-detected
by inspecting the first non-blank line: if it has two comma-separated
fields and the first parses as ``float``, the file is treated as
``timestamp,hex`` CSV and timestamps are passed through to PipeDecoder
via ``pymodes.decode(list, timestamps=[...])``. Otherwise the file is
treated as one hex message per line.

Malformed lines in ``--file`` mode produce error-dicts in the output
stream (matching the existing batch-mode contract) rather than aborting.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pymodes import decode as pymodes_decode


def run(args: argparse.Namespace) -> int:
    """Entry point for ``modes decode``. Returns exit code."""
    if args.message is not None:
        return _run_single(args)
    return _run_file(args)


def _parse_surface_ref(value: str | None) -> Any:
    """Parse a --surface-ref value.

    Accepts an ICAO airport code (e.g. "LFBO") or a "lat,lon" string
    (e.g. "43.63,1.37"). ICAO codes are passed through as strings;
    tuples are parsed into (float, float).
    """
    if value is None:
        return None
    if "," in value:
        lat_str, lon_str = value.split(",", 1)
        return (float(lat_str.strip()), float(lon_str.strip()))
    return value


def _run_single(args: argparse.Namespace) -> int:
    """Single-message path: one hex → one JSON object to stdout."""
    reference = tuple(args.reference) if args.reference is not None else None
    surface_ref = _parse_surface_ref(args.surface_ref)
    try:
        result = pymodes_decode(
            args.message,
            reference=reference,
            surface_ref=surface_ref,
            full_dict=args.full_dict,
        )
    except Exception as e:
        print(f"modes decode: error: {e}", file=sys.stderr)
        return 1

    if args.compact:
        print(json.dumps(result, separators=(",", ":"), default=str))
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


def _run_file(args: argparse.Namespace) -> int:
    """File-based path: emit one JSON line per input message."""
    surface_ref = _parse_surface_ref(args.surface_ref)

    try:
        hexes, timestamps = _read_file(args.file)
    except FileNotFoundError as e:
        print(f"modes decode: error: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"modes decode: error: {e}", file=sys.stderr)
        return 1

    if not hexes:
        return 0

    # Batch decode via pymodes.decode(list, timestamps=...) — errors in
    # individual messages become error-dicts in the results list, not
    # exceptions. That matches the existing batch-mode contract.
    results = pymodes_decode(
        hexes,
        timestamps=timestamps,
        surface_ref=surface_ref,
        full_dict=args.full_dict,
    )

    for result in results:
        print(json.dumps(result, separators=(",", ":"), default=str))
    return 0


def _read_file(path: str) -> tuple[list[str], list[float] | None]:
    """Read hex strings (and optional timestamps) from file.

    Returns (hexes, timestamps). ``timestamps`` is None for the
    plain-hex-per-line format and a parallel list for ``timestamp,hex``
    CSV format.
    """
    source = sys.stdin.read() if path == "-" else Path(path).read_text()

    raw_lines = [line.strip() for line in source.splitlines()]
    # Drop blank lines up front
    lines = [line for line in raw_lines if line]

    if not lines:
        return [], None

    # Auto-detect CSV by inspecting the first non-blank line
    first = lines[0]
    if "," in first:
        left, _, _right = first.partition(",")
        try:
            float(left.strip())
            is_csv = True
        except ValueError:
            is_csv = False
    else:
        is_csv = False

    if not is_csv:
        return lines, None

    hexes: list[str] = []
    timestamps: list[float] = []
    for i, line in enumerate(lines):
        left, _, right = line.partition(",")
        try:
            ts = float(left.strip())
        except ValueError:
            # Row doesn't match CSV shape; treat hex verbatim with a
            # synthetic timestamp that preserves order
            hexes.append(line)
            timestamps.append(float(i))
            continue
        hexes.append(right.strip())
        timestamps.append(ts)
    return hexes, timestamps
