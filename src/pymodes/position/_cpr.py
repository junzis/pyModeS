"""CPR position decoding primitives.

Ported verbatim from pyModeS v2 (git 70cb484^:
src/pyModeS/decoder/bds/bds05.py, bds06.py, py_common.py).
Numerical logic is unchanged; performance is improved by
using stdlib math instead of numpy and a hardcoded NL(lat)
boundary table for O(log n) bisect lookup.
"""

from bisect import bisect_right

# Latitude boundaries where NL() steps down, in ascending order.
# Entry i is the latitude at which NL transitions from (59 - i) to
# (59 - i - 1). Derived once from the v2 trig formula (see the
# `if __name__ == "__main__"` block at the bottom of this file for
# the regeneration recipe). Stable across releases: the formula has
# no free parameters beyond nz=15, which is fixed by DO-260B.
_NL_BOUNDARIES: tuple[float, ...] = (
    10.47047129996848,  # NL=59→58
    14.828174368686794,  # NL=58→57
    18.186263570713354,  # NL=57→56
    21.029394926028463,  # NL=56→55
    23.545044865570706,  # NL=55→54
    25.829247070587755,  # NL=54→53
    27.938987101219045,  # NL=53→52
    29.911356857318083,  # NL=52→51
    31.77209707681077,  # NL=51→50
    33.53993436298484,  # NL=50→49
    35.22899597796385,  # NL=49→48
    36.85025107593526,  # NL=48→47
    38.41241892412256,  # NL=47→46
    39.922566843338615,  # NL=46→45
    41.38651832260239,  # NL=45→44
    42.80914012243555,  # NL=44→43
    44.194549514192744,  # NL=43→42
    45.546267226602346,  # NL=42→41
    46.867332524987454,  # NL=41→40
    48.160391280966216,  # NL=40→39
    49.42776439255687,  # NL=39→38
    50.67150165553835,  # NL=38→37
    51.893424691687684,  # NL=37→36
    53.09516152796003,  # NL=36→35
    54.278174722729,  # NL=35→34
    55.44378444495043,  # NL=34→33
    56.59318756205918,  # NL=33→32
    57.72747353866114,  # NL=32→31
    58.84763776148457,  # NL=31→30
    59.954592766940294,  # NL=30→29
    61.04917774246351,  # NL=29→28
    62.13216659210329,  # NL=28→27
    63.20427479381928,  # NL=27→26
    64.2661652256744,  # NL=26→25
    65.31845309682089,  # NL=25→24
    66.36171008382617,  # NL=24→23
    67.39646774084667,  # NL=23→22
    68.4232202208333,  # NL=22→21
    69.44242631144024,  # NL=21→20
    70.454510749876,  # NL=20→19
    71.45986473028982,  # NL=19→18
    72.45884544728945,  # NL=18→17
    73.45177441667865,  # NL=17→16
    74.43893415725137,  # NL=16→15
    75.42056256653356,  # NL=15→14
    76.39684390794469,  # NL=14→13
    77.36789461328188,  # NL=13→12
    78.33374082922747,  # NL=12→11
    79.29428225456925,  # NL=11→10
    80.24923213280512,  # NL=10→9
    81.19801349271948,  # NL=9→8
    82.13956980510606,  # NL=8→7
    83.07199444719814,  # NL=7→6
    83.99173562980565,  # NL=6→5
    84.89166190702085,  # NL=5→4
    85.75541620944418,  # NL=4→3
    86.535369975121,  # NL=3→2
    87.0,  # NL=2→1
)


def cprNL(lat: float) -> int:
    """Return the number of longitude zones (NL) for latitude `lat`.

    Per DO-260B §A.1.7.2. NL is 1..59, monotone non-increasing in
    |lat|. At the equator NL=59; at ±87° NL=2; above ±87° NL=1.

    Uses a hardcoded boundary table for an O(log n) bisect lookup.
    Output matches v2's trig implementation exactly across ±87° at
    0.1° resolution (verified offline).
    """
    abs_lat = abs(lat)
    if abs_lat > 87.0:
        return 1
    if abs_lat == 87.0:
        return 2
    # bisect_right: first index where abs_lat < boundary, so NL = 59 - idx.
    idx = bisect_right(_NL_BOUNDARIES, abs_lat)
    return 59 - idx


if __name__ == "__main__":
    # Regeneration recipe — run this file directly to reprint the
    # _NL_BOUNDARIES table. Formula per DO-260B §A.1.7.2 with nz=15:
    #
    #     NL(lat) = floor(2π / acos(1 - a / cos²(πlat/180)))
    #     where a = 1 - cos(π/(2·nz))
    #
    # Inverting for the latitude at which NL = k:
    #     cos²(πlat/180) = a / (1 - cos(2π/k))
    from math import acos, cos, pi

    nz = 15
    a = 1 - cos(pi / (2 * nz))
    print("_NL_BOUNDARIES = (")
    for k in range(59, 1, -1):
        cos_sq = a / (1 - cos(2 * pi / k))
        lat_boundary = (180 / pi) * acos(cos_sq**0.5)
        print(f"    {lat_boundary!r},  # NL={k}→{k - 1}")
    print(")")
