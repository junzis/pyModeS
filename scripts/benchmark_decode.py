# ruff: noqa: RUF001
"""Single-core decode benchmark mirroring jet1090 examples/benchmark.py.

Corpus: jet1090 crates/rs1090/data/long_flight.csv (172,432 Beast-
format messages; hex extracted via ``data.rawmsg.str[18:]``, matching
jet1090's loader shape so pandas Series iteration overhead is
consistent across decoders).

Four single-core decode paths are measured, no parallel rs1090
(``batch=n`` forces single-core on rs1090 side):

1. rs1090 Rust bindings, single-core: ``rs1090.decode(msgs, batch=n)``
2. pyModeS 2.21.1 via ``[bench_pms_v2.decode(m, c_common) for m in msgs]``
3. pyModeS 2.21.1 via ``[bench_pms_v2.decode(m, py_common) for m in msgs]``
4. pymodes v3 via ``[pymodes.decode(m) for m in msgs]``

Methodology matches jet1090's ``%%timeit`` usage: 7 runs of 1 loop
each, report mean ± stdev. That mirrors jet1090's published chart
directly — so the numbers are directly comparable to
``jet1090/python/examples/benchmark.py`` lines with the same
commented-out %%timeit results.

Run from the repo root:

    uv run --no-project \
        --with 'pyModeS==2.21.1' \
        --with rs1090 \
        --with pandas \
        python scripts/benchmark_decode.py

Writes a markdown report to stdout and ``scripts/.last_benchmark.md``
for the CHANGELOG task to consume.
"""

from __future__ import annotations

import os
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bench_pms_v2  # noqa: E402
import pandas as pd  # noqa: E402  # type: ignore[import-not-found]
import rs1090  # noqa: E402  # type: ignore[import-not-found]

# v2
from pyModeS import c_common, py_common  # noqa: E402  # type: ignore[import-not-found]

# v3
import pymodes  # noqa: E402


def _pymodes_v3_version() -> str:
    """Resolve pymodes v3 version from pyproject.toml.

    Needed because ``pymodes.__version__`` goes through
    ``importlib.metadata.version("pymodes")``, which in the v2-vs-v3
    benchmark env collides with the installed ``pyModeS`` 2.21.1
    distribution (both normalize to ``pymodes``) and returns 2.21.1
    instead of the v3 working-copy version.
    """
    pyproject = REPO_ROOT / "pyproject.toml"
    try:
        import tomllib

        data = tomllib.loads(pyproject.read_text())
        return str(data["project"]["version"])
    except Exception:
        return pymodes.__version__


TIMED_ROUNDS = 7  # matches jet1090's %%timeit default (7 runs)

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


def _time(fn, label: str) -> tuple[float, float]:
    """Run fn() once to warm up, then TIMED_ROUNDS times; return (mean, stdev)."""
    fn()  # warmup, discarded (matches %%timeit implicit behavior)
    samples: list[float] = []
    for i in range(TIMED_ROUNDS):
        t0 = time.perf_counter()
        fn()
        elapsed = time.perf_counter() - t0
        samples.append(elapsed)
        print(f"  {label} run {i + 1}/{TIMED_ROUNDS}: {elapsed:.3f}s", file=sys.stderr)
    mean = statistics.mean(samples)
    stdev = statistics.stdev(samples) if len(samples) > 1 else 0.0
    return mean, stdev


def main() -> None:
    corpus_path = _resolve_corpus()
    print(f"Loading corpus: {corpus_path}", file=sys.stderr)

    # Load with pandas to match jet1090/python/examples/benchmark.py shape
    data = pd.read_csv(corpus_path, names=["timestamp", "rawmsg"])
    msgs = data.rawmsg.str[18:]  # pandas Series of stripped hex strings
    n = int(data.shape[0])
    print(f"Loaded {n} messages", file=sys.stderr)

    def run_rs1090_single_core() -> None:
        rs1090.decode(msgs, batch=n)

    def run_v2_c() -> None:
        [bench_pms_v2.decode(m, c_common) for m in msgs]

    def run_v2_py() -> None:
        [bench_pms_v2.decode(m, py_common) for m in msgs]

    def run_v3() -> None:
        [pymodes.decode(m) for m in msgs]

    print("Benchmarking rs1090 single-core (batch=n)...", file=sys.stderr)
    t_rs, s_rs = _time(run_rs1090_single_core, "rs1090")
    print("Benchmarking pyModeS 2.21.1 (c_common)...", file=sys.stderr)
    t_c, s_c = _time(run_v2_c, "v2 c_common")
    print("Benchmarking pyModeS 2.21.1 (py_common)...", file=sys.stderr)
    t_py, s_py = _time(run_v2_py, "v2 py_common")
    print("Benchmarking pymodes v3...", file=sys.stderr)
    t_v3, s_v3 = _time(run_v3, "v3")

    def rate(t: float) -> int:
        return int(n / t)

    def ratio(base: float, other: float) -> float:
        return base / other

    # Baseline for the "vs v3" column: pymodes v3 single-message
    lines = [
        f"# Single-core decode benchmark — {n} messages from long_flight.csv",
        "",
        "Procedure mirrors `jet1090/python/examples/benchmark.py`: pandas-loaded",
        "corpus, `data.rawmsg.str[18:]` iteration, 7 runs of 1 loop each,",
        "mean ± stdev. Only single-core paths measured (rs1090 invoked with",
        "`batch=n` to force single-core).",
        "",
        f"Corpus: `{corpus_path}`",
        f"pymodes version: `{_pymodes_v3_version()}`",
        "",
        "| Decoder | Wall time (mean) | Throughput | vs pymodes v3 |",
        "|---|---|---|---|",
        (
            f"| rs1090 (single-core) | {t_rs:.2f}s ± {s_rs:.2f} "
            f"| {rate(t_rs):,} msg/s | {ratio(t_v3, t_rs):.2f}× |"
        ),
        (
            f"| pyModeS 2.21.1 (c_common, C) | {t_c:.2f}s ± {s_c:.2f} "
            f"| {rate(t_c):,} msg/s | {ratio(t_v3, t_c):.2f}× |"
        ),
        (
            f"| pyModeS 2.21.1 (py_common, pure Python) | {t_py:.2f}s ± {s_py:.2f} "
            f"| {rate(t_py):,} msg/s | {ratio(t_v3, t_py):.2f}× |"
        ),
        (
            f"| **pymodes v3 (pure Python)** | **{t_v3:.2f}s ± {s_v3:.2f}** "
            f"| **{rate(t_v3):,} msg/s** | **1.00×** |"
        ),
        "",
        (
            f"**Headline:** pymodes v3 is {ratio(t_py, t_v3):.2f}× faster than "
            f"pyModeS 2.21.1 py_common, {ratio(t_c, t_v3):.2f}× vs pyModeS "
            f"2.21.1 c_common (compiled C), and {ratio(t_rs, t_v3):.2f}× vs "
            "rs1090 single-core Rust."
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
