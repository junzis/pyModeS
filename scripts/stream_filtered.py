#!/usr/bin/env python3
"""High-throughput pyModeS v3 example for filtered Beast traffic.

The important performance detail is to inspect the cheap DF/typecode header
bits *before* calling ``PipeDecoder``.  ``PipeDecoder`` intentionally performs
a complete decode, including CRC and stateful validation, for every message it
receives. If an application consumes only selected formats, fully decoding
the rest of a mixed 1090 MHz feed wastes most of the CPU time.

Live Beast feed::

    python scripts/stream_filtered.py \
        --network localhost:10006 > decoded.jsonl

Replay the benchmark capture::

    python scripts/stream_filtered.py \
        --input scripts/data/airsquitter_2026-07-13_120s.csv.gz \
        > decoded.jsonl

Every output line is one complete v3 decode with ``raw_msg`` and ``timestamp``
added.  Replace ``emit_json()`` with the application's Kafka/database handoff
while keeping ``is_relevant()`` before ``pipe.decode()``.

``surface_ref`` is optional and only affects ground/surface CPR messages.
Airborne local CPR starts automatically after validated global pairs establish
the aircraft's position; no externally supplied airborne reference is needed.
Comm-B BDS 4,4/4,5 meteorological inference is heuristic and remains disabled
unless ``--include-meteo`` is supplied.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import TextIO

from pyModeS import PipeDecoder
from pyModeS.util import df, typecode

DEFAULT_NETWORK = "localhost:10006"
DEFAULT_DOWNLINK_FORMATS = frozenset((17, 20, 21))
DEFAULT_EXCLUDED_TYPECODES = frozenset((28, 29, 31))


def is_relevant(
    raw_msg: str,
    downlink_formats: frozenset[int] = DEFAULT_DOWNLINK_FORMATS,
    excluded_typecodes: frozenset[int] = DEFAULT_EXCLUDED_TYPECODES,
) -> bool:
    """Return whether a message passes the configured header filter."""
    if len(raw_msg) not in (14, 28):
        return False

    downlink_format = df(raw_msg)
    if downlink_format not in downlink_formats:
        return False

    # ADS-B operational/status typecodes are commonly irrelevant to
    # position/velocity consumers and need no full payload decode.
    return not (downlink_format in (17, 18) and typecode(raw_msg) in excluded_typecodes)


def emit_json(
    decoded: dict[str, object],
    raw_msg: str,
    timestamp: float,
    *,
    output: TextIO = sys.stdout,
) -> None:
    """Write one self-contained compact JSON record."""
    record = dict(decoded)
    record["raw_msg"] = raw_msg
    record["timestamp"] = timestamp
    output.write(json.dumps(record, separators=(",", ":")) + "\n")


def _open_capture(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="ascii")
    return path.open(encoding="ascii")


def _capture_source(path: Path) -> Iterator[tuple[str, float]]:
    """Yield ``(message, timestamp)`` from benchmark capture CSV."""
    with _open_capture(path) as source:
        for line_number, line in enumerate(source, start=1):
            try:
                timestamp, raw_msg = line.rstrip().split(",", 1)
                yield raw_msg.upper(), float(timestamp)
            except ValueError as error:
                raise ValueError(
                    f"invalid capture row {path}:{line_number}: {line.rstrip()!r}"
                ) from error


def _network_source(endpoint: str) -> Iterable[tuple[str, float]]:
    try:
        host, port_text = endpoint.rsplit(":", 1)
        port = int(port_text)
    except ValueError as error:
        raise ValueError(
            f"network endpoint must use HOST:PORT form, got {endpoint!r}"
        ) from error
    if not host or not 1 <= port <= 65535:
        raise ValueError(f"invalid network endpoint: {endpoint!r}")

    # This is the production Beast TCP reader used by the `modes live`
    # command. It handles framing, escaped bytes, timestamps and reconnects.
    from pyModeS.cli._source import NetworkSource

    return NetworkSource(host, port)


def _surface_ref(value: str | None) -> str | tuple[float, float] | None:
    if value is None or "," not in value:
        return value
    try:
        latitude, longitude = value.split(",", 1)
        return float(latitude), float(longitude)
    except ValueError as error:
        raise ValueError("--surface-ref must be an airport ICAO or LAT,LON") from error


def _integer_set(value: str) -> frozenset[int]:
    """Parse a comma-separated set of 5-bit DF/typecode values."""
    if not value:
        return frozenset()
    try:
        values = frozenset(int(item) for item in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected comma-separated integers") from error
    if any(item < 0 or item > 31 for item in values):
        raise argparse.ArgumentTypeError("values must be between 0 and 31")
    return values


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Decode selected messages from a Mode-S Beast feed.",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--network",
        default=DEFAULT_NETWORK,
        metavar="HOST:PORT",
        help=f"Mode-S Beast TCP endpoint (default: {DEFAULT_NETWORK})",
    )
    source.add_argument(
        "--input",
        type=Path,
        metavar="CAPTURE.csv[.gz]",
        help="replay a timestamp,message capture instead of connecting",
    )
    parser.add_argument(
        "--surface-ref",
        metavar="ICAO|LAT,LON",
        help="optional airport/receiver reference used only for ground "
        "(surface CPR) positions",
    )
    parser.add_argument(
        "--df",
        type=_integer_set,
        default=DEFAULT_DOWNLINK_FORMATS,
        metavar="LIST",
        dest="downlink_formats",
        help="comma-separated downlink formats (default: 17,20,21)",
    )
    parser.add_argument(
        "--exclude-typecode",
        type=_integer_set,
        default=DEFAULT_EXCLUDED_TYPECODES,
        metavar="LIST",
        dest="excluded_typecodes",
        help="ADS-B typecodes to skip; pass an empty value for none "
        "(default: 28,29,31)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="stop after N relevant messages (useful for a quick check)",
    )
    parser.add_argument(
        "--no-output",
        action="store_true",
        help="decode without JSON output (useful for throughput measurement)",
    )
    parser.add_argument(
        "--include-meteo",
        action="store_true",
        help="include heuristic Comm-B BDS 4,4/4,5 meteorological inference",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be >= 1")

    try:
        source = (
            _capture_source(args.input)
            if args.input is not None
            else _network_source(args.network)
        )
        pipe = PipeDecoder(
            surface_ref=_surface_ref(args.surface_ref),
            include_meteo=args.include_meteo,
        )
    except ValueError as error:
        print(f"stream_filtered: error: {error}", file=sys.stderr)
        return 2

    started = time.perf_counter()
    received = 0
    decoded_count = 0
    try:
        for raw_msg, timestamp in source:
            received += 1
            if not is_relevant(
                raw_msg,
                args.downlink_formats,
                args.excluded_typecodes,
            ):
                continue

            decoded = pipe.decode(raw_msg, timestamp=timestamp)
            decoded_count += 1
            if not args.no_output:
                emit_json(decoded, raw_msg, timestamp)
            if args.limit is not None and decoded_count >= args.limit:
                break
    except KeyboardInterrupt:
        pass
    except (OSError, RuntimeError, ValueError) as error:
        print(f"stream_filtered: error: {error}", file=sys.stderr)
        return 1

    elapsed = time.perf_counter() - started
    rate = received / elapsed if elapsed else 0.0
    print(
        "stream_filtered: "
        f"received={received:,} decoded={decoded_count:,} "
        f"elapsed={elapsed:.3f}s feed_rate={rate:,.0f} msg/s "
        f"pipe_stats={pipe.stats}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
