#!/usr/bin/env python3
"""Benchmark selective streaming on a captured mixed Beast feed.

The committed default corpus is a two-minute capture from the TU Delft
AirSquitter Beast feed.  It contains both short and long Mode-S frames and a
realistic mixture of DF0/4/5/11/16/17/20/21 traffic.

The four timed paths are intentionally isolated in separate ``uv``
environments:

* pyModeS 2.21.1: inspect DF first, then selectively decode the DF17/20/21
  fields consumed by the example processor; use global and local CPR with
  O(1) per-aircraft state.
* released pyModeS 3.4.0: offer every frame to ``PipeDecoder`` before applying
  the same output selection, matching the supplied v3 processor.
* pyModeS 3.5.0 from the working tree: the same v3 code path, from a
  freshly-built wheel.
* pyModeS 3.5.0 with the recommended header prefilter applied before
  ``PipeDecoder`` (the filter itself remains inside the timed loop).

The benchmark fixes the stripped example's accidental loop termination,
renamed v3 velocity keys, flight-level units, and null-position emission. It
checks filtered/unfiltered v3.5 output equality, unchanged non-position output
from v3.4, immediate position yield, and coordinate agreement with v2 on every
frame where both implementations emit a position.
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
import tomllib
from collections import Counter
from collections.abc import Callable
from importlib.metadata import version as distribution_version
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = Path(__file__).resolve()
DEFAULT_CORPUS = REPO_ROOT / "scripts/data/airsquitter_2026-07-13_120s.csv.gz"
DEFAULT_REPORT = REPO_ROOT / "scripts/benchmark_results/mixed_traffic.md"


def _working_tree_version() -> str:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    return str(data["project"]["version"])


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


def _distance_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    """Great-circle distance used by the position-quality checks."""
    lat1, lon1 = first
    lat2, lon2 = second
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlam = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlam / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(a))


def _record_event(
    hasher: Any,
    non_position_hasher: Any,
    event_counts: Counter[str],
    event: tuple[Any, ...],
) -> None:
    _digest_event(hasher, event)
    kind = str(event[0])
    event_counts[kind] += 1
    if kind != "position":
        _digest_event(non_position_hasher, event)


RunnerOutput = tuple[
    str,
    str,
    int,
    dict[str, int],
    dict[str, int],
    list[tuple[int, float, float]],
]


def _v2_runner(
    rows: list[tuple[float, str]],
) -> Callable[[], RunnerOutput]:
    import pyModeS as pms  # type: ignore[import-not-found]

    def run() -> RunnerOutput:
        hasher = hashlib.sha256()
        non_position_hasher = hashlib.sha256()
        event_counts: Counter[str] = Counter()
        events = 0
        pending: dict[str, dict[int, tuple[str, float]]] = {}
        fresh_parities: dict[str, set[int]] = {}
        position_refs: dict[str, tuple[float, float, float]] = {}
        position_samples: list[tuple[int, float, float]] = []

        for row_index, (timestamp, message) in enumerate(rows):
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
                    _record_event(hasher, non_position_hasher, event_counts, event)
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
                        _record_event(hasher, non_position_hasher, event_counts, event)
                        events += 1

                # Standards-based streaming position workflow used by the
                # supplied v2 application: establish a global even/odd seed,
                # then use the last recent position for locally-unambiguous
                # CPR while periodically cross-checking fresh global pairs.
                if 9 <= typecode <= 13 or typecode == 20:
                    parity = pms.adsb.oe_flag(message)
                    aircraft_pending = pending.setdefault(icao, {})
                    aircraft_pending[parity] = (message, timestamp)
                    aircraft_fresh = fresh_parities.setdefault(icao, set())
                    aircraft_fresh.add(parity)

                    local_position = None
                    reference = position_refs.get(icao)
                    if reference is not None and 0 <= timestamp - reference[2] < 30:
                        candidate = pms.adsb.position_with_ref(
                            message, reference[0], reference[1]
                        )
                        if (
                            candidate is not None
                            and _distance_km(reference[:2], candidate) < 6 * 1.852
                        ):
                            local_position = candidate

                    global_position = None
                    if aircraft_fresh == {0, 1}:
                        even, even_time = aircraft_pending[0]
                        odd, odd_time = aircraft_pending[1]
                        if abs(even_time - odd_time) <= 10.0:
                            global_position = pms.adsb.position(
                                even, odd, even_time, odd_time
                            )
                            if global_position is not None:
                                aircraft_fresh.clear()

                    position = global_position or local_position
                    if (
                        global_position is not None
                        and local_position is not None
                        and _distance_km(global_position, local_position) > 0.1
                    ):
                        position = None
                    if position is not None:
                        position_refs[icao] = (
                            float(position[0]),
                            float(position[1]),
                            timestamp,
                        )
                        altitude = pms.adsb.altitude(message)
                        event = (
                            "position",
                            icao,
                            position[0],
                            position[1],
                            altitude / 100 if altitude is not None else None,
                        )
                        _record_event(hasher, non_position_hasher, event_counts, event)
                        position_samples.append(
                            (row_index, float(position[0]), float(position[1]))
                        )
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
                _record_event(hasher, non_position_hasher, event_counts, event)
                events += 1

        return (
            hasher.hexdigest(),
            non_position_hasher.hexdigest(),
            events,
            {
                "state": len(pending),
                "velocity_anchors": 0,
            },
            dict(event_counts),
            position_samples,
        )

    return run


def _v3_runner(
    rows: list[tuple[float, str]],
    *,
    prefilter: bool = False,
) -> Callable[[], RunnerOutput]:
    from pyModeS import PipeDecoder, util

    def run() -> RunnerOutput:
        pipe = PipeDecoder()
        hasher = hashlib.sha256()
        non_position_hasher = hashlib.sha256()
        event_counts: Counter[str] = Counter()
        position_samples: list[tuple[int, float, float]] = []
        events = 0

        for row_index, (timestamp, message) in enumerate(rows):
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
                    _record_event(hasher, non_position_hasher, event_counts, event)
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
                    _record_event(hasher, non_position_hasher, event_counts, event)
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
                    _record_event(hasher, non_position_hasher, event_counts, event)
                    position_samples.append(
                        (row_index, float(latitude), float(longitude))
                    )
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
                _record_event(hasher, non_position_hasher, event_counts, event)
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
                _record_event(hasher, non_position_hasher, event_counts, event)
                events += 1
            elif decoded.get("bds") == "4,4":
                _record_event(
                    hasher,
                    non_position_hasher,
                    event_counts,
                    ("bds44", icao),
                )
                events += 1

        return (
            hasher.hexdigest(),
            non_position_hasher.hexdigest(),
            events,
            {
                "state": len(pipe._state),
                "velocity_anchors": len(pipe._adsb_velocity),
            },
            dict(event_counts),
            position_samples,
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
    non_position_digest: str | None = None
    event_count: int | None = None
    cache_sizes: dict[str, int] = {}
    event_counts: dict[str, int] = {}
    position_samples: list[tuple[int, float, float]] = []
    for _ in range(args.rounds):
        gc.collect()
        started = time.perf_counter()
        (
            round_digest,
            round_non_position_digest,
            round_events,
            cache_sizes,
            round_event_counts,
            round_position_samples,
        ) = runner()
        samples.append(time.perf_counter() - started)
        if digest is None:
            digest = round_digest
            non_position_digest = round_non_position_digest
            event_count = round_events
            event_counts = round_event_counts
            position_samples = round_position_samples
        elif (
            round_digest != digest
            or round_non_position_digest != non_position_digest
            or round_events != event_count
            or round_event_counts != event_counts
            or round_position_samples != position_samples
        ):
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
                "non_position_digest": non_position_digest,
                "event_counts": event_counts,
                "position_samples": position_samples,
                "samples": samples,
                "cache_sizes": cache_sizes,
            },
            separators=(",", ":"),
        )
    )
    return 0


def _run_command(command: list[str], *, cwd: Path) -> str:
    environment = os.environ.copy()
    for key in (
        "PYTHONPATH",
        "UV_EXCLUDE_NEWER",
        "VIRTUAL_ENV",
        "UV_PROJECT_ENVIRONMENT",
    ):
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
            "--exclude-newer-package",
            "pymodes=2026-07-15T23:59:59Z",
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


def _position_comparison(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, float | int | None]:
    baseline_positions = {
        int(row): (float(lat), float(lon))
        for row, lat, lon in baseline["position_samples"]
    }
    candidate_positions = {
        int(row): (float(lat), float(lon))
        for row, lat, lon in candidate["position_samples"]
    }
    shared_rows = sorted(baseline_positions.keys() & candidate_positions.keys())
    distances = [
        _distance_km(baseline_positions[row], candidate_positions[row])
        for row in shared_rows
    ]
    return {
        "baseline": len(baseline_positions),
        "candidate": len(candidate_positions),
        "shared": len(shared_rows),
        "coverage_pct": (
            100 * len(candidate_positions) / len(baseline_positions)
            if baseline_positions
            else None
        ),
        "agreement_100m_pct": (
            100 * sum(distance <= 0.1 for distance in distances) / len(distances)
            if distances
            else None
        ),
        "median_distance_m": (
            1000 * statistics.median(distances) if distances else None
        ),
        "max_distance_m": 1000 * max(distances) if distances else None,
    }


def _require_position_quality(
    results: list[dict[str, Any]],
    *,
    min_v2_yield_pct: float,
    min_agreement_pct: float,
) -> None:
    """Fail when the working decoder falls below the declared quality floor."""
    v2 = next(result for result in results if result["api"] == "v2")
    released = next(result for result in results if result["api"] == "v3")
    working = next(result for result in results if result["api"] == "v3-working")
    quality = _position_comparison(v2, working)

    working_positions = int(quality["candidate"])
    released_positions = int(released["event_counts"].get("position", 0))
    if working_positions < released_positions:
        raise RuntimeError(
            "working-tree position yield regressed below released v3.4.0: "
            f"{working_positions:,} < {released_positions:,}"
        )

    # A corpus without v2 positions cannot provide a position-quality oracle.
    # Throughput and non-position checks remain useful, so do not reject it.
    if int(quality["baseline"]) == 0:
        return

    coverage = quality["coverage_pct"]
    if coverage is None or coverage < min_v2_yield_pct:
        coverage_text = "n/a" if coverage is None else f"{coverage:.2f}%"
        raise RuntimeError(
            "working-tree position yield is below the required v2 coverage: "
            f"{coverage_text} < {min_v2_yield_pct:.2f}%"
        )

    agreement = quality["agreement_100m_pct"]
    if agreement is None or agreement < min_agreement_pct:
        agreement_text = "n/a" if agreement is None else f"{agreement:.2f}%"
        raise RuntimeError(
            "working-tree position agreement is below the required threshold: "
            f"{agreement_text} < {min_agreement_pct:.2f}% within 100 m"
        )


def _format_optional(value: float | int | None, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}{suffix}"


def _format_report(
    results: list[dict[str, Any]],
    *,
    corpus: Path,
    stats: dict[str, Any],
    rounds: int,
    warmups: int,
    min_v2_yield_pct: float,
    min_agreement_pct: float,
) -> str:
    current = next(result for result in results if result["label"] == "v3.4.0")
    working = next(result for result in results if result["api"] == "v3-working")
    v2 = next(result for result in results if result["api"] == "v2")
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
            "decoding, including global plus locally-unambiguous airborne CPR. "
            "The released and unfiltered working-tree v3 paths "
            "offer every frame to `PipeDecoder`, matching the supplied v3 "
            "processor. The prefiltered working-tree path includes cheap header "
            "filtering inside its timed loop. Position counts refer to coordinates "
            "available immediately from each streaming decode call."
        ),
        "",
        (
            "| Decoder | Version | Median | Throughput | vs v3.4.0 | "
            "Events | Positions | State / velocity anchors |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|",
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
            f"{result['event_counts'].get('position', 0):,} | {cache_text} |"
        )

    filtered = next(result for result in results if result["api"] == "v3-filtered")
    working_match = (working["events"], working["digest"]) == (
        filtered["events"],
        filtered["digest"],
    )
    non_position_match = (
        current["non_position_digest"] == working["non_position_digest"]
    )
    current_quality = _position_comparison(v2, current)
    working_quality = _position_comparison(v2, working)
    lines.extend(
        [
            "",
            (
                "Working-tree filtered/unfiltered output check: "
                f"**{'PASS' if working_match else 'FAIL'}**."
            ),
            (
                "Released/working-tree non-position output check: "
                f"**{'PASS' if non_position_match else 'FAIL'}** — identification, "
                "velocity, and Comm-B output is unchanged."
            ),
            "",
            "Position yield and agreement against the v2 streaming reference:",
            (
                f"Required for v{working['version']}: at least "
                f"{min_v2_yield_pct:.1f}% of v2 position yield, at least "
                f"{min_agreement_pct:.1f}% of shared positions within 100 m, "
                "and no yield regression from v3.4.0."
            ),
            "",
            "| Decoder | Immediate positions | v2 yield | Shared messages | "
            "Within 100 m | Median delta | Maximum delta |",
            "|---|---:|---:|---:|---:|---:|---:|",
            (
                f"| v3.4.0 | {current_quality['candidate']:,} | "
                f"{_format_optional(current_quality['coverage_pct'], '%')} | "
                f"{current_quality['shared']:,} | "
                f"{_format_optional(current_quality['agreement_100m_pct'], '%')} | "
                f"{_format_optional(current_quality['median_distance_m'], ' m')} | "
                f"{_format_optional(current_quality['max_distance_m'], ' m')} |"
            ),
            (
                f"| {working['label']} | {working_quality['candidate']:,} | "
                f"{_format_optional(working_quality['coverage_pct'], '%')} | "
                f"{working_quality['shared']:,} | "
                f"{_format_optional(working_quality['agreement_100m_pct'], '%')} | "
                f"{_format_optional(working_quality['median_distance_m'], ' m')} | "
                f"{_format_optional(working_quality['max_distance_m'], ' m')} |"
            ),
            "",
            "V2 and v3 position totals need not be identical: v3 retains its "
            "multi-candidate bootstrap and motion validation. Agreement is measured "
            "only where both implementations emit a position for the same frame.",
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

        working_version = _working_tree_version()
        variants = [
            ("v2.21.1", "v2", "pyModeS==2.21.1"),
            ("v3.4.0", "v3", "pyModeS==3.4.0"),
            (f"v{working_version}", "v3-working", str(wheel_files[0])),
            (
                f"v{working_version} + header prefilter",
                "v3-filtered",
                str(wheel_files[0]),
            ),
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
        working_results = [
            result
            for result in results
            if result["api"] in ("v3-working", "v3-filtered")
        ]
        if len({(r["events"], r["digest"]) for r in working_results}) != 1:
            raise RuntimeError("working-tree output differs with header filtering")
        released = next(result for result in results if result["api"] == "v3")
        working = next(result for result in results if result["api"] == "v3-working")
        if released["non_position_digest"] != working["non_position_digest"]:
            raise RuntimeError("non-position v3 output changed")
        _require_position_quality(
            results,
            min_v2_yield_pct=args.min_v2_position_yield,
            min_agreement_pct=args.min_position_agreement,
        )

        report = _format_report(
            results,
            corpus=corpus,
            stats=stats,
            rounds=args.rounds,
            warmups=args.warmups,
            min_v2_yield_pct=args.min_v2_position_yield,
            min_agreement_pct=args.min_position_agreement,
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
        "--min-v2-position-yield",
        type=float,
        default=80.0,
        metavar="PERCENT",
        help="minimum working-tree position count as a percentage of v2 (default: 80)",
    )
    parser.add_argument(
        "--min-position-agreement",
        type=float,
        default=99.0,
        metavar="PERCENT",
        help="minimum shared positions within 100 m of v2 (default: 99)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT,
        help=f"markdown report path (default: {DEFAULT_REPORT})",
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--api",
        choices=("v2", "v3", "v3-working", "v3-filtered"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--label", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds must be >= 1")
    if args.warmups < 0:
        parser.error("--warmups must be >= 0")
    if not 0 <= args.min_v2_position_yield <= 100:
        parser.error("--min-v2-position-yield must be between 0 and 100")
    if not 0 <= args.min_position_agreement <= 100:
        parser.error("--min-position-agreement must be between 0 and 100")
    if args.worker and (args.api is None or args.label is None):
        parser.error("worker mode requires --api and --label")
    return args


def main() -> int:
    args = _parse_args()
    return _worker(args) if args.worker else _parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
