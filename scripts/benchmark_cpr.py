"""Benchmark v3 CPR against a verbatim port of v2's numpy implementation.

Not a pytest unit test — run directly:
    uv run --with numpy scripts/benchmark_cpr.py

Fails with exit code 1 if v3 is slower than v2 on the hot path.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable

import numpy as np


# v2 reference — inline copy of the pyModeS 2.22.0 cprNL (git 70cb484^)
def v2_cprNL(lat: float) -> int:
    if np.isclose(lat, 0):
        return 59
    if np.isclose(abs(lat), 87):
        return 2
    if lat > 87 or lat < -87:
        return 1
    nz = 15
    a = 1 - np.cos(np.pi / (2 * nz))
    b = np.cos(np.pi / 180 * abs(lat)) ** 2
    nl = 2 * np.pi / (np.arccos(1 - a / b))
    return int(np.floor(nl))


def v2_airborne_with_ref(
    cpr_format: int,
    cpr_lat_raw: int,
    cpr_lon_raw: int,
    lat_ref: float,
    lon_ref: float,
) -> tuple[float, float]:
    cprlat = cpr_lat_raw / 131072
    cprlon = cpr_lon_raw / 131072
    d_lat = 360 / 59 if cpr_format else 360 / 60
    j = int(np.floor(0.5 + lat_ref / d_lat - cprlat))
    lat = d_lat * (j + cprlat)
    ni = v2_cprNL(lat) - cpr_format
    d_lon = 360 / ni if ni > 0 else 360
    m = int(np.floor(0.5 + lon_ref / d_lon - cprlon))
    lon = d_lon * (m + cprlon)
    return lat, lon


def bench(name: str, fn: Callable[[], None], n: int) -> float:
    t0 = time.perf_counter_ns()
    for _ in range(n):
        fn()
    elapsed = (time.perf_counter_ns() - t0) / 1e9
    print(f"  {name}: {elapsed:.3f}s ({n / elapsed:,.0f} ops/sec)")
    return elapsed


def main() -> int:
    from pymodes.position._cpr import (
        airborne_position_with_ref,
        cprNL,
    )

    # cprNL benchmark: many lats per iteration, amortizing function call overhead
    lats = [i * 0.1 for i in range(-870, 871)]
    iters_nl = 500_000 // len(lats)
    print(f"Benchmarking cprNL ({iters_nl * len(lats):,} calls)")
    t_v2_nl = bench(
        "  v2 (numpy trig)",
        lambda: [v2_cprNL(lat) for lat in lats],
        iters_nl,
    )
    t_v3_nl = bench(
        "  v3 (bisect table)",
        lambda: [cprNL(lat) for lat in lats],
        iters_nl,
    )
    speedup_nl = t_v2_nl / t_v3_nl
    print(f"  speedup: {speedup_nl:.2f}x\n")

    # airborne_with_ref benchmark: includes one cprNL call per iter
    iters_ar = 100_000
    args = (0, 93000, 51372, 49.0, 6.0)
    print(f"Benchmarking airborne_with_ref ({iters_ar:,} calls)")
    t_v2_ar = bench("  v2", lambda: v2_airborne_with_ref(*args), iters_ar)
    t_v3_ar = bench("  v3", lambda: airborne_position_with_ref(*args), iters_ar)
    speedup_ar = t_v2_ar / t_v3_ar
    print(f"  speedup: {speedup_ar:.2f}x\n")

    if t_v3_nl >= t_v2_nl:
        print("FAIL: v3 cprNL is not faster than v2", file=sys.stderr)
        return 1
    if t_v3_ar >= t_v2_ar:
        print("FAIL: v3 airborne_with_ref is not faster than v2", file=sys.stderr)
        return 1
    print("OK: v3 faster on both benchmarks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
