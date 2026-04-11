"""Implementation of ``modes decode`` subcommand.

Three input shapes:

- Single-message: ``modes decode HEX`` → one pretty-printed JSON
  object on stdout (or compact with ``--compact``).
- Inline batch: ``modes decode HEX1,HEX2,HEX3`` → one compact JSON
  line per message on stdout. Whitespace around each hex is stripped.
- File-based: ``modes decode --file PATH`` → one compact JSON line
  per input. Use ``-`` as ``PATH`` for stdin. File format is
  auto-detected: if the first non-blank line has two comma-separated
  fields and the first parses as ``float``, the file is treated as
  ``timestamp,hex`` CSV and timestamps are forwarded to PipeDecoder.
  Otherwise the file is treated as one hex message per line.

Malformed messages in batch (inline or file) mode produce error-dicts
in the output stream (matching the existing batch-mode contract)
rather than aborting. ``--reference`` is rejected in both batch modes
because a single airborne reference cannot meaningfully apply to
multiple aircraft at different positions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pyModeS import decode as pyModeS_decode
from pyModeS.message import Decoded


def run(args: argparse.Namespace) -> int:
    """Entry point for ``modes decode``. Returns exit code."""
    if args.message is not None:
        if "," in args.message:
            return _run_inline_batch(args)
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
        result = pyModeS_decode(
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


def _run_inline_batch(args: argparse.Namespace) -> int:
    """Inline-batch path: split the comma-separated MESSAGE and emit JSON lines."""
    hexes = [h.strip() for h in args.message.split(",") if h.strip()]
    if not hexes:
        return 0
    return _emit_batch(hexes, None, args)


def _run_file(args: argparse.Namespace) -> int:
    """File-based path: emit one JSON line per input message."""
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

    return _emit_batch(hexes, timestamps, args)


def _emit_batch(
    hexes: list[str],
    timestamps: list[float] | None,
    args: argparse.Namespace,
) -> int:
    """Batch decode and emit results to stdout.

    Shared by the inline (``HEX1,HEX2``) and file-based (``--file PATH``)
    input shapes. Uses ``pyModeS.decode(list, timestamps=...)``'s
    batch-mode contract: individual message errors become error-dicts
    in the results list, so the stream stays line-aligned with input.

    Output format:

    - Default: one pretty-printed JSON object per message, separated
      by a blank line. One parameter per line — the same shape as
      the single-message pretty output, just repeated for each item
      in the batch. Human-readable when pasting a few messages into
      a terminal and eyeballing the decoded fields.
    - ``--compact``: one compact JSON line per message — pipe-friendly,
      composable with ``jq``, suitable for redirecting to a file.

    When the caller doesn't have real timestamps (inline batch and the
    plain-hex file format), we synthesize list-position timestamps
    here. That's exactly what ``pyModeS.core.decode`` would do
    internally anyway — doing it at the CLI layer suppresses core's
    "no timestamps provided" stderr warning for the common case where
    a user pastes hex messages into a terminal.
    """
    surface_ref = _parse_surface_ref(args.surface_ref)
    if timestamps is None:
        timestamps = [float(i) for i in range(len(hexes))]
    results: list[Decoded] = pyModeS_decode(
        hexes,
        timestamps=timestamps,
        surface_ref=surface_ref,
        full_dict=args.full_dict,
    )

    if args.compact:
        for result in results:
            print(json.dumps(result, separators=(",", ":"), default=str))
        return 0

    # Pretty: one JSON object per message, blank line between.
    for i, result in enumerate(results):
        if i > 0:
            print()
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
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
