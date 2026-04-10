# ruff: noqa: E501, RUF001
"""Decode benchmark: pymodes v3 vs pyModeS 2.21.1, apples-to-apples.

Corpus: jet1090 crates/rs1090/data/long_flight.csv (172,432 Beast-
format messages; hex extracted via rawmsg[18:] per jet1090 conventions).

Measures four paths, prints a markdown report, and writes
scripts/.last_benchmark.md for the CHANGELOG task to consume:

1. pyModeS 2.21.1 via scripts/bench_pms_v2.decode(msg, c_common)
2. pyModeS 2.21.1 via scripts/bench_pms_v2.decode(msg, py_common)
3. pymodes v3 via pymodes.decode(msg) single-message
4. pymodes v3 via pymodes.decode([...]) batch

Methodology: 1 warm-up pass (discarded) + 5 timed runs, median
reported. Full corpus per run. Requires:

    uv run --no-project --with 'pyModeS==2.21.1' python scripts/benchmark_decode.py

The pyModeS 2.21.1 env is provided by uv's --with flag; pymodes v3
is available from the editable install in the working copy.
"""

from __future__ import annotations

import csv
import os
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bench_pms_v2  # noqa: E402

# v2
from pyModeS import c_common, py_common  # noqa: E402  # type: ignore[import-not-found]

# v3
import pymodes  # noqa: E402

WARMUP_ROUNDS = 1
TIMED_ROUNDS = 5

DEFAULT_CORPUS_PATH = Path(
    "/home/junzi/arc/code/4-fork/jet1090/crates/rs1090/data/long_flight.csv"
)


def _resolve_corpus() -> Path:
    env = os.environ.get("JET1090_LONG_FLIGHT_CSV")
    if env:
        p = Path(env)
        if p.exists():
            return p
        print(f"WARNING: JET1090_LONG_FLIGHT_CSV={env} does not exist", file=sys.stderr)
    if DEFAULT_CORPUS_PATH.exists():
        return DEFAULT_CORPUS_PATH
    print(
        "ERROR: long_flight.csv not found. Set JET1090_LONG_FLIGHT_CSV or "
        "clone jet1090 at " + str(DEFAULT_CORPUS_PATH.parent),
        file=sys.stderr,
    )
    sys.exit(1)


def _load_hex(path: Path) -> list[str]:
    """Load the Beast-format CSV and strip the 18-char header off each row."""
    msgs: list[str] = []
    with path.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            raw = row[1].strip()
            if len(raw) > 18:
                msgs.append(raw[18:])
    return msgs


def _time(fn, label: str) -> tuple[float, float]:
    """Run fn() WARMUP_ROUNDS + TIMED_ROUNDS times; return (median, stdev)."""
    for _ in range(WARMUP_ROUNDS):
        fn()
    samples: list[float] = []
    for i in range(TIMED_ROUNDS):
        t0 = time.perf_counter()
        fn()
        elapsed = time.perf_counter() - t0
        samples.append(elapsed)
        print(f"  {label} run {i + 1}/{TIMED_ROUNDS}: {elapsed:.3f}s", file=sys.stderr)
    return statistics.median(samples), statistics.stdev(samples) if len(
        samples
    ) > 1 else 0.0


def main() -> None:
    corpus_path = _resolve_corpus()
    print(f"Loading corpus: {corpus_path}", file=sys.stderr)
    msgs = _load_hex(corpus_path)
    n = len(msgs)
    print(f"Loaded {n} messages", file=sys.stderr)

    def run_v2_c() -> None:
        for msg in msgs:
            bench_pms_v2.decode(msg, c_common)

    def run_v2_py() -> None:
        for msg in msgs:
            bench_pms_v2.decode(msg, py_common)

    def run_v3_single() -> None:
        for msg in msgs:
            pymodes.decode(msg)

    def run_v3_batch() -> None:
        pymodes.decode(msgs, timestamps=[float(i) for i in range(n)])

    print("Benchmarking v2 c_common...", file=sys.stderr)
    t_c, s_c = _time(run_v2_c, "v2 c_common")
    print("Benchmarking v2 py_common...", file=sys.stderr)
    t_py, s_py = _time(run_v2_py, "v2 py_common")
    print("Benchmarking v3 single...", file=sys.stderr)
    t_v3, s_v3 = _time(run_v3_single, "v3 single")
    print("Benchmarking v3 batch...", file=sys.stderr)
    t_v3b, s_v3b = _time(run_v3_batch, "v3 batch")

    def rate(t: float) -> int:
        return int(n / t)

    def ratio(base: float, other: float) -> float:
        return base / other

    lines = [
        f"# Benchmark — {n} messages from long_flight.csv",
        "",
        f"Corpus: `{corpus_path}`",
        f"pymodes version: `{pymodes.__version__}`",
        "",
        "| Decoder | Wall time (median) | Throughput | vs v2 c_common | vs v2 py_common |",
        "|---|---|---|---|---|",
        (
            f"| pyModeS 2.21.1 (c_common) | {t_c:.2f}s ± {s_c:.2f} "
            f"| {rate(t_c):,} msg/s | 1.00× | {ratio(t_py, t_c):.2f}× |"
        ),
        (
            f"| pyModeS 2.21.1 (py_common) | {t_py:.2f}s ± {s_py:.2f} "
            f"| {rate(t_py):,} msg/s | {ratio(t_c, t_py):.2f}× | 1.00× |"
        ),
        (
            f"| pymodes v3 (single) | {t_v3:.2f}s ± {s_v3:.2f} "
            f"| {rate(t_v3):,} msg/s | {ratio(t_c, t_v3):.2f}× | {ratio(t_py, t_v3):.2f}× |"
        ),
        (
            f"| pymodes v3 (batch) | {t_v3b:.2f}s ± {s_v3b:.2f} "
            f"| {rate(t_v3b):,} msg/s | {ratio(t_c, t_v3b):.2f}× | {ratio(t_py, t_v3b):.2f}× |"
        ),
        "",
        (
            f"**Headline:** pymodes v3 is {ratio(t_py, t_v3):.2f}× faster than "
            f"pyModeS 2.21.1 (pure Python) and {ratio(t_c, t_v3):.2f}× "
            "vs pyModeS 2.21.1 c_common."
        ),
        "",
    ]

    report = "\n".join(lines)
    print(report)

    output = REPO_ROOT / "scripts" / ".last_benchmark.md"
    output.write_text(report)
    print(f"\nReport written to {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
