#!/usr/bin/env python3
"""Benchmark selective streaming on a captured mixed Beast feed.

The committed default corpus is a two-minute capture from the TU Delft
AirSquitter Beast feed.  It contains both short and long Mode-S frames and a
realistic mixture of DF0/4/5/11/16/17/20/21 traffic.

The four timed paths are intentionally isolated in separate ``uv``
environments:

* pyModeS 2.21.1: inspect DF first, then selectively decode the DF17/20/21
  fields consumed by the example processor; maintain a basic O(1)
  even/odd CPR-pair cache.
* released pyModeS 3.3.0: offer every frame to ``PipeDecoder`` before applying
  the same output selection, matching the supplied v3 processor.
* updated working-tree v3: the same v3 code path, from a freshly-built wheel.
* updated working-tree v3 with the recommended header prefilter applied
  before ``PipeDecoder`` (the filter itself remains inside the timed loop).

The benchmark fixes the stripped example's accidental loop termination,
renamed v3 velocity keys, flight-level units, and null-position emission.  It
requires released and updated v3 to produce identical event counts and output
digests.  V2 position/BDS inference is not required to match v3 because the
algorithms intentionally differ; its input count is still required to match.
"""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable
from importlib.metadata import version as distribution_version
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = Path(__file__).resolve()
DEFAULT_CORPUS = REPO_ROOT / "scripts/data/airsquitter_2026-07-13_120s.csv.gz"
DEFAULT_REPORT = REPO_ROOT / "scripts/benchmark_results/mixed_traffic.md"


def _open_corpus(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="ascii")
    return path.open(encoding="ascii")


def _load_corpus(path: Path) -> list[tuple[float, str]]:
    rows: list[tuple[float, str]] = []
    with _open_corpus(path) as source:
        for line in source:
            timestamp, message = line.rstrip().split(",", 1)
            rows.append((float(timestamp), message))
    return rows


def _digest_event(hasher: Any, event: tuple[Any, ...]) -> None:
    hasher.update(json.dumps(event, separators=(",", ":")).encode())
    hasher.update(b"\n")


def _v2_runner(
    rows: list[tuple[float, str]],
) -> Callable[[], tuple[str, int, dict[str, int]]]:
    import pyModeS as pms  # type: ignore[import-not-found]

    def run() -> tuple[str, int, dict[str, int]]:
        hasher = hashlib.sha256()
        events = 0
        pending: dict[str, dict[int, tuple[str, float]]] = {}

        for timestamp, message in rows:
            # This is the important v2 behavior in the example processor: cheap
            # header inspection happens before any payload decoder.
            downlink_format = pms.df(message)
            if len(message) < 28 or downlink_format not in (17, 20, 21):
                continue

            icao = pms.icao(message)
            if icao is None:
                continue

            if downlink_format == 17:
                typecode = pms.adsb.typecode(message)
                if typecode in (28, 29, 31) or typecode is None:
                    continue

                if 1 <= typecode <= 4:
                    event = (
                        "ident",
                        icao,
                        pms.adsb.callsign(message).replace("_", "").strip(),
                        pms.adsb.category(message),
                    )
                    _digest_event(hasher, event)
                    events += 1
                elif typecode == 19:
                    velocity = pms.adsb.velocity(message, source=True)
                    if velocity is not None:
                        speed, track, vertical_rate, speed_type, _, vr_source = velocity
                        nac_v, _, _ = pms.adsb.nuc_v(message)
                        event = (
                            "velocity",
                            icao,
                            speed if speed_type == "GS" else None,
                            track if speed_type == "GS" else None,
                            vertical_rate,
                            vr_source,
                            nac_v,
                            pms.bds.bds09.altitude_diff(message),
                        )
                        _digest_event(hasher, event)
                        events += 1

                # The stripped v2 position helper accepts only TC 9-13 and
                # TC20 after its own validation. Resolve fresh even/odd pairs
                # with an O(1) per-ICAO cache to include CPR work in timing.
                if 9 <= typecode <= 13 or typecode == 20:
                    parity = pms.adsb.oe_flag(message)
                    aircraft_pending = pending.setdefault(icao, {})
                    aircraft_pending[parity] = (message, timestamp)
                    if 0 in aircraft_pending and 1 in aircraft_pending:
                        even, even_time = aircraft_pending[0]
                        odd, odd_time = aircraft_pending[1]
                        if abs(even_time - odd_time) <= 10.0:
                            try:
                                position = pms.adsb.position(
                                    even, odd, even_time, odd_time
                                )
                            except Exception:
                                position = None
                            if position is not None:
                                altitude = pms.adsb.altitude(message)
                                event = (
                                    "position",
                                    icao,
                                    position[0],
                                    position[1],
                                    altitude / 100 if altitude is not None else None,
                                )
                                _digest_event(hasher, event)
                                events += 1

            else:
                bds = pms.bds.infer(message, mrar=True)
                if bds == "BDS50":
                    event = (
                        "bds50",
                        icao,
                        pms.commb.gs50(message),
                        pms.commb.trk50(message),
                        pms.commb.rtrk50(message),
                        pms.commb.tas50(message),
                        pms.commb.roll50(message),
                    )
                elif bds == "BDS60":
                    event = (
                        "bds60",
                        icao,
                        pms.commb.ias60(message),
                        pms.commb.hdg60(message),
                        pms.commb.mach60(message),
                        pms.commb.vr60baro(message),
                        pms.commb.vr60ins(message),
                    )
                elif bds == "BDS44":
                    event = ("bds44", icao)
                else:
                    continue
                _digest_event(hasher, event)
                events += 1

        return (
            hasher.hexdigest(),
            events,
            {
                "state": len(pending),
                "velocity_anchors": 0,
            },
        )

    return run


def _v3_runner(
    rows: list[tuple[float, str]],
    *,
    prefilter: bool = False,
) -> Callable[[], tuple[str, int, dict[str, int]]]:
    from pyModeS import PipeDecoder, util

    def run() -> tuple[str, int, dict[str, int]]:
        pipe = PipeDecoder()
        hasher = hashlib.sha256()
        events = 0

        for timestamp, message in rows:
            if prefilter:
                # Recommended selective path: cheap header inspection happens
                # before CRC, payload decoding, validation, and state work.
                if len(message) != 28:
                    continue
                header_df = util.df(message)
                if header_df not in (17, 20, 21):
                    continue
                if header_df == 17 and util.typecode(message) in (28, 29, 31):
                    continue

            # Unfiltered mode matches the supplied v3 processor: decode
            # every frame before selecting DF/TC.
            decoded = pipe.decode(message, timestamp=timestamp)
            downlink_format = decoded["df"]

            if len(message) < 28 or downlink_format not in (17, 20, 21):
                continue
            icao = decoded["icao"]

            if downlink_format == 17:
                typecode = decoded.get("typecode")
                if typecode in (28, 29, 31) or typecode is None:
                    continue

                if 1 <= typecode <= 4:
                    event = (
                        "ident",
                        icao,
                        decoded.get("callsign", "").replace("_", "").strip(),
                        decoded.get("category"),
                    )
                    _digest_event(hasher, event)
                    events += 1
                elif typecode == 19:
                    event = (
                        "velocity",
                        icao,
                        decoded.get("groundspeed"),
                        decoded.get("track"),
                        decoded.get("vertical_rate"),
                        decoded.get("vr_source"),
                        decoded.get("nac_v"),
                        decoded.get("geo_minus_baro"),
                    )
                    _digest_event(hasher, event)
                    events += 1

                latitude = decoded.get("latitude")
                longitude = decoded.get("longitude")
                if (
                    (9 <= typecode <= 13 or typecode == 20)
                    and latitude is not None
                    and longitude is not None
                ):
                    altitude = decoded.get("altitude")
                    event = (
                        "position",
                        icao,
                        latitude,
                        longitude,
                        altitude / 100 if altitude is not None else None,
                    )
                    _digest_event(hasher, event)
                    events += 1

            elif decoded.get("bds") == "5,0":
                event = (
                    "bds50",
                    icao,
                    decoded.get("groundspeed"),
                    decoded.get("true_track"),
                    decoded.get("track_rate"),
                    decoded.get("true_airspeed"),
                    decoded.get("roll"),
                )
                _digest_event(hasher, event)
                events += 1
            elif decoded.get("bds") == "6,0":
                event = (
                    "bds60",
                    icao,
                    decoded.get("indicated_airspeed"),
                    decoded.get("magnetic_heading"),
                    decoded.get("mach"),
                    decoded.get("baro_vertical_rate"),
                    decoded.get("inertial_vertical_rate"),
                )
                _digest_event(hasher, event)
                events += 1
            elif decoded.get("bds") == "4,4":
                _digest_event(hasher, ("bds44", icao))
                events += 1

        return (
            hasher.hexdigest(),
            events,
            {
                "state": len(pipe._state),
                "velocity_anchors": len(pipe._adsb_velocity),
            },
        )

    return run


def _worker(args: argparse.Namespace) -> int:
    rows = _load_corpus(args.corpus)
    runner = (
        _v2_runner(rows)
        if args.api == "v2"
        else _v3_runner(rows, prefilter=args.api == "v3-filtered")
    )

    for _ in range(args.warmups):
        runner()

    samples: list[float] = []
    digest: str | None = None
    event_count: int | None = None
    cache_sizes: dict[str, int] = {}
    for _ in range(args.rounds):
        gc.collect()
        started = time.perf_counter()
        round_digest, round_events, cache_sizes = runner()
        samples.append(time.perf_counter() - started)
        if digest is None:
            digest = round_digest
            event_count = round_events
        elif round_digest != digest or round_events != event_count:
            raise RuntimeError("output changed between benchmark rounds")

    print(
        json.dumps(
            {
                "label": args.label,
                "api": args.api,
                "version": distribution_version("pyModeS"),
                "python": platform.python_version(),
                "messages": len(rows),
                "events": event_count,
                "digest": digest,
                "samples": samples,
                "cache_sizes": cache_sizes,
            },
            separators=(",", ":"),
        )
    )
    return 0


def _run_command(command: list[str], *, cwd: Path) -> str:
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
        environment.pop(key, None)
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=None,
    )
    return completed.stdout


def _run_variant(
    *,
    label: str,
    api: str,
    requirement: str,
    corpus: Path,
    rounds: int,
    warmups: int,
    cwd: Path,
) -> dict[str, Any]:
    stdout = _run_command(
        [
            "uv",
            "run",
            "--quiet",
            "--no-project",
            "--with",
            requirement,
            "python",
            str(SCRIPT_PATH),
            "--worker",
            "--api",
            api,
            "--label",
            label,
            "--corpus",
            str(corpus),
            "--rounds",
            str(rounds),
            "--warmups",
            str(warmups),
        ],
        cwd=cwd,
    )
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"{label} worker produced no output")
    return json.loads(lines[-1])


def _corpus_stats(rows: list[tuple[float, str]]) -> dict[str, Any]:
    downlink_formats: Counter[int] = Counter()
    typecodes: Counter[int] = Counter()
    lengths: Counter[int] = Counter()
    explicit_icaos: set[str] = set()
    for _, message in rows:
        downlink_format = int(message[:2], 16) >> 3
        downlink_formats[downlink_format] += 1
        lengths[len(message)] += 1
        if downlink_format in (11, 17, 18):
            explicit_icaos.add(message[2:8])
        if downlink_format in (17, 18):
            typecodes[int(message[8:10], 16) >> 3] += 1
    return {
        "span": rows[-1][0] - rows[0][0],
        "dfs": dict(sorted(downlink_formats.items())),
        "typecodes": dict(sorted(typecodes.items())),
        "lengths": dict(sorted(lengths.items())),
        "explicit_icaos": len(explicit_icaos),
    }


def _format_counter(values: dict[int, int]) -> str:
    return ", ".join(f"{key}: {value:,}" for key, value in values.items())


def _format_report(
    results: list[dict[str, Any]],
    *,
    corpus: Path,
    stats: dict[str, Any],
    rounds: int,
    warmups: int,
) -> str:
    current = next(result for result in results if result["label"] == "v3.3.0")
    current_median = statistics.median(current["samples"])
    messages = current["messages"]

    lines = [
        f"# Mixed-traffic streaming benchmark — {messages:,} Mode-S frames",
        "",
        "Generated by `python scripts/benchmark_mixed_traffic.py`.",
        "",
        (
            f"Corpus: `{corpus.name}`, {stats['span']:.3f} timestamp seconds, "
            f"{stats['explicit_icaos']:,} explicit-address ICAOs."
        ),
        f"Message lengths: {_format_counter(stats['lengths'])} hex characters.",
        f"Downlink formats: {_format_counter(stats['dfs'])}.",
        f"ADS-B type codes: {_format_counter(stats['typecodes'])}.",
        (
            f"Timing: {warmups} discarded warmup(s), {rounds} measured round(s), "
            "median wall time reported."
        ),
        f"Host: `{platform.platform()}`.",
        "",
        (
            "V2 performs early DF filtering and selective field "
            "decoding. The released and unfiltered updated v3 paths offer every "
            "frame to `PipeDecoder`, matching the supplied v3 processor. The "
            "prefiltered updated path includes cheap header filtering inside its "
            "timed loop. All v3 paths must produce identical event output."
        ),
        "",
        (
            "| Decoder | Version | Median | Throughput | vs v3.3.0 | "
            "Events | State / velocity anchors |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        median = statistics.median(result["samples"])
        rate = messages / median
        relative = current_median / median
        caches = result["cache_sizes"]
        cache_text = (
            "n/a"
            if result["api"] == "v2"
            else f"{caches['state']:,} / {caches['velocity_anchors']:,}"
        )
        lines.append(
            f"| {result['label']} | {result['version']} | {median:.3f}s | "
            f"{rate:,.0f} msg/s | {relative:.2f}x | {result['events']:,} | "
            f"{cache_text} |"
        )

    v3_results = [result for result in results if result["api"].startswith("v3")]
    v3_match = len({(r["events"], r["digest"]) for r in v3_results}) == 1
    lines.extend(
        [
            "",
            (
                "Released/updated v3 output check: "
                f"**{'PASS' if v3_match else 'FAIL'}** "
                f"— {v3_results[0]['events']:,} events, digest "
                f"`{v3_results[0]['digest']}`."
            ),
            (
                "V2 event totals are reported but not compared for equality because "
                "its CPR validation and Comm-B inference intentionally differ from v3."
            ),
            "",
            "Samples (seconds):",
            "",
        ]
    )
    for result in results:
        samples = ", ".join(f"{sample:.3f}" for sample in result["samples"])
        lines.append(f"- {result['label']}: {samples}")
    return "\n".join(lines) + "\n"


def _parent(args: argparse.Namespace) -> int:
    corpus = args.corpus.resolve()
    rows = _load_corpus(corpus)
    if not rows:
        raise RuntimeError(f"empty corpus: {corpus}")
    stats = _corpus_stats(rows)

    with tempfile.TemporaryDirectory(prefix="pymodes-mixed-benchmark-") as tmp:
        temp_dir = Path(tmp)
        wheels = temp_dir / "wheels"
        wheels.mkdir()
        print("Building updated working-tree wheel...", file=sys.stderr)
        _run_command(
            ["uv", "build", "--quiet", "--wheel", "--out-dir", str(wheels)],
            cwd=REPO_ROOT,
        )
        wheel_files = sorted(wheels.glob("pymodes-*.whl"))
        if len(wheel_files) != 1:
            raise RuntimeError(f"expected one updated wheel, found {wheel_files}")

        variants = [
            ("v2.21.1", "v2", "pyModeS==2.21.1"),
            ("v3.3.0", "v3", "pyModeS==3.3.0"),
            ("updated v3", "v3", str(wheel_files[0])),
            ("updated v3 + header prefilter", "v3-filtered", str(wheel_files[0])),
        ]
        results = []
        for label, api, requirement in variants:
            print(f"Benchmarking {label}...", file=sys.stderr)
            results.append(
                _run_variant(
                    label=label,
                    api=api,
                    requirement=requirement,
                    corpus=corpus,
                    rounds=args.rounds,
                    warmups=args.warmups,
                    cwd=temp_dir,
                )
            )

        if {result["messages"] for result in results} != {len(rows)}:
            raise RuntimeError("worker input-count mismatch")
        v3_results = [result for result in results if result["api"].startswith("v3")]
        if len({(r["events"], r["digest"]) for r in v3_results}) != 1:
            raise RuntimeError("released and updated v3 outputs differ")

        report = _format_report(
            results,
            corpus=corpus,
            stats=stats,
            rounds=args.rounds,
            warmups=args.warmups,
        )
        print(report, end="")
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report)
            print(f"Report written to {args.output}", file=sys.stderr)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT,
        help=f"markdown report path (default: {DEFAULT_REPORT})",
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--api",
        choices=("v2", "v3", "v3-filtered"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--label", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds must be >= 1")
    if args.warmups < 0:
        parser.error("--warmups must be >= 0")
    if args.worker and (args.api is None or args.label is None):
        parser.error("worker mode requires --api and --label")
    return args


def main() -> int:
    args = _parse_args()
    return _worker(args) if args.worker else _parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
