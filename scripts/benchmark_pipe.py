#!/usr/bin/env python3
"""Isolated v2/current-v3/working-tree PipeDecoder benchmark.

This benchmark targets the high-cardinality streaming regression reported
against pyModeS 3.3.  It generates valid DF17 airborne-velocity messages for
many ICAO addresses, keeps every aircraft active inside the default five-minute
TTL, and decodes the same timestamped corpus through:

1. pyModeS 2.21.1's public selective helpers;
2. the released pyModeS 3.5.0 ``PipeDecoder``;
3. a pyModeS 3.5.1 wheel built from the current working tree.

Every version runs in a separate ``uv run --no-project`` environment.  This is
important: pyModeS 2 and 3 share the same distribution/import name, so loading
both in one interpreter can silently benchmark the wrong implementation.

The worker normalizes the common DF17 velocity fields and hashes every output.
The parent refuses to report timings unless all three versions produce the same
message count and digest.

Typical usage from the repository root::

    python scripts/benchmark_pipe.py

For a quick smoke run::

    python scripts/benchmark_pipe.py \
        --aircraft 200 --messages 2000 --rounds 1 --warmups 0

The released versions are resolved from PyPI.  The updated version is always a
fresh wheel built into a temporary directory; the repository's active virtual
environment is never used by a timed worker.
"""

from __future__ import annotations

import argparse
import gc
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
from collections.abc import Callable
from importlib.metadata import version as distribution_version
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = Path(__file__).resolve()
DEFAULT_REPORT = REPO_ROOT / "scripts/benchmark_results/pipe.md"
BASELINE_VERSION = "3.5.0"
BASELINE_LABEL = f"v{BASELINE_VERSION}"
VELOCITY_TEMPLATE = "8D485020994409940838175B284F"
_CRC_POLY = 0xFFF409


def _working_tree_version() -> str:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    return str(data["project"]["version"])


def _build_crc_table() -> tuple[int, ...]:
    table = [0] * 256
    for i in range(256):
        crc = i << 16
        for _ in range(8):
            crc = ((crc << 1) ^ _CRC_POLY) if crc & 0x800000 else crc << 1
        table[i] = crc & 0xFFFFFF
    return tuple(table)


_CRC_TABLE = _build_crc_table()


def _crc_parity(message_without_parity: int) -> int:
    crc = 0
    shift = 104
    for _ in range(11):
        byte = (message_without_parity >> shift) & 0xFF
        index = ((crc >> 16) ^ byte) & 0xFF
        crc = ((crc << 8) & 0xFFFFFF) ^ _CRC_TABLE[index]
        shift -= 8
    return crc


def _message_for_icao(icao: int) -> str:
    """Rewrite the template AA field and generate a valid DF17 parity."""
    message = int(VELOCITY_TEMPLATE, 16)
    icao_mask = 0xFFFFFF << 80
    body = (message & ~icao_mask & ~0xFFFFFF) | (icao << 80)
    return f"{body | _crc_parity(body):028X}"


def _write_corpus(
    path: Path,
    *,
    aircraft: int,
    messages: int,
    duration: float,
) -> None:
    if aircraft < 1:
        raise ValueError("aircraft must be >= 1")
    if messages < aircraft:
        raise ValueError("messages must be >= aircraft")
    if duration < 0:
        raise ValueError("duration must be >= 0")

    frames = [_message_for_icao(0x400000 + i) for i in range(aircraft)]
    start = 1_700_000_000.0
    step = duration / max(messages - 1, 1)
    with path.open("w", encoding="ascii") as output:
        for i in range(messages):
            output.write(f"{start + i * step:.9f},{frames[i % aircraft]}\n")


def _load_corpus(path: Path) -> list[tuple[float, str]]:
    rows: list[tuple[float, str]] = []
    with path.open(encoding="ascii") as source:
        for line in source:
            timestamp, message = line.rstrip().split(",", 1)
            rows.append((float(timestamp), message))
    return rows


def _digest_row(hasher: Any, fields: tuple[Any, ...]) -> None:
    hasher.update(json.dumps(fields, separators=(",", ":")).encode())
    hasher.update(b"\n")


def _v2_runner(
    rows: list[tuple[float, str]],
) -> Callable[[], tuple[str, dict[str, int]]]:
    import pyModeS as pms  # type: ignore[import-not-found]

    def run() -> tuple[str, dict[str, int]]:
        hasher = hashlib.sha256()
        for _timestamp, message in rows:
            df = pms.df(message)
            icao = pms.icao(message)
            typecode = pms.adsb.typecode(message)
            velocity = pms.adsb.velocity(message, source=True)
            if velocity is None:
                fields = (df, icao, typecode, None, None, None, None, None)
            else:
                speed, track, vertical_rate, speed_type, _, vr_source = velocity
                nac_v, _, _ = pms.adsb.nuc_v(message)
                altitude_diff = pms.bds.bds09.altitude_diff(message)
                fields = (
                    df,
                    icao,
                    typecode,
                    speed if speed_type == "GS" else None,
                    track if speed_type == "GS" else None,
                    vertical_rate,
                    vr_source,
                    nac_v,
                    altitude_diff,
                )
            _digest_row(hasher, fields)
        return hasher.hexdigest(), {"state": 0, "velocity_anchors": 0}

    return run


def _v3_runner(
    rows: list[tuple[float, str]],
) -> Callable[[], tuple[str, dict[str, int]]]:
    from pyModeS import PipeDecoder

    def run() -> tuple[str, dict[str, int]]:
        pipe = PipeDecoder()
        hasher = hashlib.sha256()
        for timestamp, message in rows:
            decoded = pipe.decode(message, timestamp=timestamp)
            fields = (
                decoded["df"],
                decoded["icao"],
                decoded.get("typecode"),
                decoded.get("groundspeed"),
                decoded.get("track"),
                decoded.get("vertical_rate"),
                decoded.get("vr_source"),
                decoded.get("nac_v"),
                decoded.get("geo_minus_baro"),
            )
            _digest_row(hasher, fields)
        return hasher.hexdigest(), {
            "state": len(pipe._state),
            "velocity_anchors": len(pipe._adsb_velocity),
        }

    return run


def _worker(args: argparse.Namespace) -> int:
    rows = _load_corpus(args.corpus)
    runner = _v2_runner(rows) if args.api == "v2" else _v3_runner(rows)

    for _ in range(args.warmups):
        runner()

    samples: list[float] = []
    digest: str | None = None
    cache_sizes: dict[str, int] = {}
    for _ in range(args.rounds):
        gc.collect()
        started = time.perf_counter()
        round_digest, cache_sizes = runner()
        samples.append(time.perf_counter() - started)
        if digest is None:
            digest = round_digest
        elif round_digest != digest:
            raise RuntimeError("output digest changed between benchmark rounds")

    result = {
        "label": args.label,
        "api": args.api,
        "version": distribution_version("pyModeS"),
        "python": platform.python_version(),
        "messages": len(rows),
        "digest": digest,
        "samples": samples,
        "cache_sizes": cache_sizes,
    }
    print(json.dumps(result, separators=(",", ":")))
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
    command = [
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
    ]
    stdout = _run_command(command, cwd=cwd)
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"{label} worker produced no output")
    return json.loads(lines[-1])


def _format_report(
    results: list[dict[str, Any]],
    *,
    aircraft: int,
    messages: int,
    duration: float,
    rounds: int,
    warmups: int,
) -> str:
    current = next(result for result in results if result["label"] == BASELINE_LABEL)
    current_median = statistics.median(current["samples"])

    lines = [
        f"# PipeDecoder high-cardinality benchmark — {messages:,} messages",
        "",
        "Generated by `python scripts/benchmark_pipe.py`.",
        "",
        (
            f"Corpus: {aircraft:,} active ICAOs over {duration:g} timestamp seconds; "
            "valid DF17 TC=19 velocity frames; default 300-second TTL."
        ),
        (
            f"Timing: {warmups} discarded warmup(s), {rounds} measured round(s), "
            "median wall time reported."
        ),
        f"Host: `{platform.platform()}`.",
        "",
        (
            "Each version ran in a separate `uv run --no-project` environment. "
            "v2 uses its public selective DF17 helpers; both v3 variants use "
            "`PipeDecoder`. Common velocity outputs were normalized and SHA-256 "
            "checked before reporting."
        ),
        "",
        (
            "| Decoder | Version | Python | Median | Throughput | "
            f"vs {BASELINE_LABEL} | State / anchors |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        median = statistics.median(result["samples"])
        rate = result["messages"] / median
        relative = current_median / median
        caches = result["cache_sizes"]
        cache_text = (
            "n/a"
            if result["api"] == "v2"
            else f"{caches['state']:,} / {caches['velocity_anchors']:,}"
        )
        lines.append(
            f"| {result['label']} | {result['version']} | {result['python']} | "
            f"{median:.3f}s | {rate:,.0f} msg/s | {relative:.2f}x | "
            f"{cache_text} |"
        )

    digests = {result["digest"] for result in results}
    lines.extend(
        [
            "",
            (
                f"Output check: **{'PASS' if len(digests) == 1 else 'FAIL'}** — "
                f"{messages:,} normalized records per version, digest "
                f"`{results[0]['digest']}`."
            ),
            "",
            "Samples (seconds):",
            "",
        ]
    )
    for result in results:
        sample_text = ", ".join(f"{sample:.3f}" for sample in result["samples"])
        lines.append(f"- {result['label']}: {sample_text}")
    return "\n".join(lines) + "\n"


def _parent(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="pymodes-pipe-benchmark-") as tmp:
        temp_dir = Path(tmp)
        corpus = temp_dir / "corpus.csv"
        wheels = temp_dir / "wheels"
        wheels.mkdir()
        _write_corpus(
            corpus,
            aircraft=args.aircraft,
            messages=args.messages,
            duration=args.duration,
        )

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
            (BASELINE_LABEL, "v3", f"pyModeS=={BASELINE_VERSION}"),
            (f"v{working_version}", "v3", str(wheel_files[0])),
        ]
        results: list[dict[str, Any]] = []
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

        counts = {result["messages"] for result in results}
        digests = {result["digest"] for result in results}
        if counts != {args.messages}:
            raise RuntimeError(f"message-count mismatch: {counts}")
        if len(digests) != 1:
            details = {result["label"]: result["digest"] for result in results}
            raise RuntimeError(f"normalized output mismatch: {details}")

        report = _format_report(
            results,
            aircraft=args.aircraft,
            messages=args.messages,
            duration=args.duration,
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
    parser.add_argument("--aircraft", type=int, default=2000)
    parser.add_argument("--messages", type=int, default=30000)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT,
        help=f"markdown report path (default: {DEFAULT_REPORT})",
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--api", choices=("v2", "v3"), help=argparse.SUPPRESS)
    parser.add_argument("--label", help=argparse.SUPPRESS)
    parser.add_argument("--corpus", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds must be >= 1")
    if args.warmups < 0:
        parser.error("--warmups must be >= 0")
    if args.worker and (args.api is None or args.label is None or args.corpus is None):
        parser.error("worker mode requires --api, --label, and --corpus")
    return args


def main() -> int:
    args = _parse_args()
    return _worker(args) if args.worker else _parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
