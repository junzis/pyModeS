"""CPR position decoding primitives.

Ported verbatim from pyModeS v2 (git 70cb484^:
src/pyModeS/decoder/bds/bds05.py, bds06.py, py_common.py).
Numerical logic is unchanged; performance is improved by
using stdlib math instead of numpy and precomputing the
NL(lat) boundary table at import time.
"""

from bisect import bisect_right
from math import acos, cos, pi


def _build_nl_boundaries() -> tuple[float, ...]:
    """Compute the latitude boundaries where NL() steps down.

    For each NL value k in 2..59, solve for the latitude at which
    the v2 trig formula equals k exactly. The result is a tuple of
    58 floats in ascending order, suitable for bisect lookup.
    """
    nz = 15
    a = 1 - cos(pi / (2 * nz))
    boundaries: list[float] = []
    # NL=k transitions at the latitude where:
    #   2π / acos(1 - a / cos²(πlat/180)) == k
    # Solving: cos²(πlat/180) = a / (1 - cos(2π/k))
    for k in range(59, 1, -1):
        cos_sq = a / (1 - cos(2 * pi / k))
        lat_boundary = (180 / pi) * acos(cos_sq**0.5)
        boundaries.append(lat_boundary)
    return tuple(boundaries)


# 58 ascending boundaries: boundaries[0] is the NL=59→58 transition,
# boundaries[57] is the NL=2→1 transition (exactly 87°).
_NL_BOUNDARIES: tuple[float, ...] = _build_nl_boundaries()


def cprNL(lat: float) -> int:
    """Return the number of longitude zones (NL) for latitude `lat`.

    Per DO-260B §A.1.7.2. NL is 1..59, monotone non-increasing in
    |lat|. At the equator NL=59; at ±87° NL=2; above ±87° NL=1.

    This implementation uses a precomputed boundary table for an
    O(log n) bisect lookup. Output matches v2's trig implementation
    to within the float-equality test pyModeS v2 used (±1e-8 at the
    equator, ±1e-5*87 at ±87°).
    """
    abs_lat = abs(lat)
    # Pole caps: exactly at or above ±87° is the NL=1 region, but
    # "exactly ±87°" is conventionally NL=2 per the v2 reference.
    if abs_lat > 87.0:
        return 1
    if abs_lat == 87.0:
        return 2
    # bisect_right returns the first index where abs_lat < boundary,
    # so NL = 59 - that index.
    idx = bisect_right(_NL_BOUNDARIES, abs_lat)
    return 59 - idx
