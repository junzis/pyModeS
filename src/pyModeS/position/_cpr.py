"""CPR position decoding primitives.

Three helpers live here:

- ``cprNL(lat)`` returns the CPR longitude-zone count. Implemented
  as a bisect over a precomputed NL(lat) boundary table, giving
  O(log n) lookup without numpy or per-call trig evaluation.
- ``airborne_position_*`` resolves DF17/18 BDS 0,5 lat/lon from an
  even/odd CPR pair or a known reference position.
- ``surface_position_*`` is the same for BDS 0,6, with a tighter
  45 NM reference-tolerance window.
"""

from bisect import bisect_right
from math import floor

# Latitude boundaries where NL() steps down, in ascending order.
# Entry i is the latitude at which NL transitions from (59 - i) to
# (59 - i - 1). Derived once from the closed-form NL(lat) trig
# expression (see the ``if __name__ == "__main__"`` block at the
# bottom of this file for the regeneration recipe). Stable across
# releases: the formula has no free parameters beyond nz=15, which
# is fixed by DO-260B.
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


_CPR_DENOM = 131072.0  # 2**17


def airborne_position_with_ref(
    cpr_format: int,
    cpr_lat_raw: int,
    cpr_lon_raw: int,
    lat_ref: float,
    lon_ref: float,
) -> tuple[float, float]:
    """Resolve an airborne CPR frame against a nearby reference.

    Per DO-260B §A.1.7.5. The reference must lie within 180 NM of
    the true position. Returns (lat, lon) in decimal degrees.

    Args:
        cpr_format: 0 = even, 1 = odd.
        cpr_lat_raw: raw 17-bit CPR latitude field.
        cpr_lon_raw: raw 17-bit CPR longitude field.
        lat_ref: reference latitude in degrees.
        lon_ref: reference longitude in degrees.
    """
    cpr_lat = cpr_lat_raw / _CPR_DENOM
    cpr_lon = cpr_lon_raw / _CPR_DENOM
    d_lat = 360.0 / 59 if cpr_format else 360.0 / 60

    j = floor(0.5 + lat_ref / d_lat - cpr_lat)
    lat = d_lat * (j + cpr_lat)

    ni = cprNL(lat) - cpr_format
    d_lon = 360.0 / ni if ni > 0 else 360.0

    m = floor(0.5 + lon_ref / d_lon - cpr_lon)
    lon = d_lon * (m + cpr_lon)

    return lat, lon


def airborne_position_pair(
    cpr_lat_even_raw: int,
    cpr_lon_even_raw: int,
    cpr_lat_odd_raw: int,
    cpr_lon_odd_raw: int,
    *,
    even_is_newer: bool,
) -> tuple[float, float] | None:
    """Resolve absolute lat/lon from an even/odd CPR pair.

    Per DO-260B §A.1.7.3. Caller must pass the even CPR fields in
    the even_* parameters and the odd CPR fields in the odd_*
    parameters. `even_is_newer` selects which frame's latitude zone
    to use (the newer message defines the reported position).

    Preconditions:
        The two frames must be close enough in time for the aircraft
        to have stayed in the same latitude zone. In practice, the
        pair must be ≤ 10 seconds apart — ADS-B airborne position
        messages broadcast at ~2 Hz, and a pair older than that may
        straddle a cprNL boundary even for slow-moving aircraft. The
        caller is responsible for enforcing this window; this function
        performs a cprNL-equality check as a lightweight sanity guard
        but cannot detect same-zone false positives caused by wide
        time gaps.

    Returns (lat, lon) if both frames fall in the same latitude
    zone (cprNL equal), otherwise None.
    """
    cprlat_even = cpr_lat_even_raw / _CPR_DENOM
    cprlon_even = cpr_lon_even_raw / _CPR_DENOM
    cprlat_odd = cpr_lat_odd_raw / _CPR_DENOM
    cprlon_odd = cpr_lon_odd_raw / _CPR_DENOM

    j = floor(59 * cprlat_even - 60 * cprlat_odd + 0.5)

    lat_even = (360.0 / 60) * (j % 60 + cprlat_even)
    lat_odd = (360.0 / 59) * (j % 59 + cprlat_odd)

    if lat_even >= 270:
        lat_even -= 360
    if lat_odd >= 270:
        lat_odd -= 360

    if cprNL(lat_even) != cprNL(lat_odd):
        return None

    if even_is_newer:
        lat = lat_even
        nl = cprNL(lat)
        ni = max(nl, 1)
        m = floor(cprlon_even * (nl - 1) - cprlon_odd * nl + 0.5)
        lon = (360.0 / ni) * (m % ni + cprlon_even)
    else:
        lat = lat_odd
        nl = cprNL(lat)
        ni = max(nl - 1, 1)
        m = floor(cprlon_even * (nl - 1) - cprlon_odd * nl + 0.5)
        lon = (360.0 / ni) * (m % ni + cprlon_odd)

    if lon > 180:
        lon -= 360

    # Final sanity guard. The normalization above only folds results in
    # [270, 360) back to [-90, 0); pairs that produce latitudes in
    # [90, 270) are physically impossible (outside the poles) and
    # typically come from frames straddling a cprNL zone where the
    # accidental equality fooled the cprNL check — reject them.
    if abs(lat) > 90 or abs(lon) > 180:
        return None

    return lat, lon


def surface_position_with_ref(
    cpr_format: int,
    cpr_lat_raw: int,
    cpr_lon_raw: int,
    lat_ref: float,
    lon_ref: float,
) -> tuple[float, float]:
    """Resolve a surface CPR frame against a nearby reference.

    Per DO-260B §A.1.7.6. Reference must lie within 45 NM.
    Surface CPR uses a 90° latitude zone span (versus 360° for
    airborne), so resolution is per-quadrant — callers must ensure
    the reference is close enough to the true position.
    """
    cpr_lat = cpr_lat_raw / _CPR_DENOM
    cpr_lon = cpr_lon_raw / _CPR_DENOM
    d_lat = 90.0 / 59 if cpr_format else 90.0 / 60

    j = floor(0.5 + lat_ref / d_lat - cpr_lat)
    lat = d_lat * (j + cpr_lat)

    ni = cprNL(lat) - cpr_format
    d_lon = 90.0 / ni if ni > 0 else 90.0

    m = floor(0.5 + lon_ref / d_lon - cpr_lon)
    lon = d_lon * (m + cpr_lon)

    return lat, lon


def surface_position_pair(
    cpr_lat_even_raw: int,
    cpr_lon_even_raw: int,
    cpr_lat_odd_raw: int,
    cpr_lon_odd_raw: int,
    *,
    lat_ref: float,
    lon_ref: float,
    even_is_newer: bool,
) -> tuple[float, float] | None:
    """Resolve an even/odd surface CPR pair against a receiver location.

    Per DO-260B §A.1.7.4. The receiver reference is required because
    surface CPR has a 90° latitude zone and four longitude quadrants;
    without a reference we cannot choose among them.

    Returns (lat, lon) if both frames fall in the same latitude zone,
    otherwise None.
    """
    cprlat_even = cpr_lat_even_raw / _CPR_DENOM
    cprlon_even = cpr_lon_even_raw / _CPR_DENOM
    cprlat_odd = cpr_lat_odd_raw / _CPR_DENOM
    cprlon_odd = cpr_lon_odd_raw / _CPR_DENOM

    j = floor(59 * cprlat_even - 60 * cprlat_odd + 0.5)

    # Surface CPR is ambiguous over two 90-degree latitude zones. Resolve
    # that ambiguity from the actual distance to the reference, rather than
    # from the reference's hemisphere: a receiver and aircraft can be on
    # opposite sides of the equator while still satisfying the 45 NM limit.
    lat_even_n = (90.0 / 60) * (j % 60 + cprlat_even)
    lat_odd_n = (90.0 / 59) * (j % 59 + cprlat_odd)
    lat_even_s = lat_even_n - 90
    lat_odd_s = lat_odd_n - 90

    latitude_pairs = (
        (lat_even_n, lat_odd_n),
        (lat_even_s, lat_odd_s),
    )
    newer_index = 0 if even_is_newer else 1
    lat_even, lat_odd = min(
        latitude_pairs,
        key=lambda pair: abs(lat_ref - pair[newer_index]),
    )

    if cprNL(lat_even) != cprNL(lat_odd):
        return None

    if even_is_newer:
        lat = lat_even
        nl = cprNL(lat)
        ni = max(nl, 1)
        m = floor(cprlon_even * (nl - 1) - cprlon_odd * nl + 0.5)
        lon_base = (90.0 / ni) * (m % ni + cprlon_even)
    else:
        lat = lat_odd
        nl = cprNL(lat)
        ni = max(nl - 1, 1)
        m = floor(cprlon_even * (nl - 1) - cprlon_odd * nl + 0.5)
        lon_base = (90.0 / ni) * (m % ni + cprlon_odd)

    # Four candidate longitudes (one per 90° quadrant), each wrapped
    # to [-180, 180]. Longitude is circular: around the date line, -180°
    # is one degree from a +179° reference, not 359 degrees away.
    candidates = [((lon_base + q + 180) % 360) - 180 for q in (0, 90, 180, 270)]
    lon = min(candidates, key=lambda c: abs((c - lon_ref + 180) % 360 - 180))
    return lat, lon


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
