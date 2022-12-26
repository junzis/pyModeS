# ------------------------------------------
#   BDS 0,5
#   ADS-B TC=9-18
#   Airborne position
# ------------------------------------------

from __future__ import annotations

from datetime import datetime

from ... import common


def airborne_position(
    msg0: str, msg1: str, t0: int | datetime, t1: int | datetime
) -> None | tuple[float, float]:
    """Decode airborne position from a pair of even and odd position message

    Args:
        msg0 (string): even message (28 hexdigits)
        msg1 (string): odd message (28 hexdigits)
        t0 (int): timestamps for the even message
        t1 (int): timestamps for the odd message

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """

    mb0 = common.hex2bin(msg0)[32:]
    mb1 = common.hex2bin(msg1)[32:]

    oe0 = int(mb0[21])
    oe1 = int(mb1[21])
    if oe0 == 0 and oe1 == 1:
        pass
    elif oe0 == 1 and oe1 == 0:
        mb0, mb1 = mb1, mb0
        t0, t1 = t1, t0
    else:
        raise RuntimeError("Both even and odd CPR frames are required.")

    # 131072 is 2^17, since CPR lat and lon are 17 bits each.
    cprlat_even = common.bin2int(mb0[22:39]) / 131072
    cprlon_even = common.bin2int(mb0[39:56]) / 131072
    cprlat_odd = common.bin2int(mb1[22:39]) / 131072
    cprlon_odd = common.bin2int(mb1[39:56]) / 131072

    air_d_lat_even = 360 / 60
    air_d_lat_odd = 360 / 59

    # compute latitude index 'j'
    j = common.floor(59 * cprlat_even - 60 * cprlat_odd + 0.5)

    lat_even = float(air_d_lat_even * (j % 60 + cprlat_even))
    lat_odd = float(air_d_lat_odd * (j % 59 + cprlat_odd))

    if lat_even >= 270:
        lat_even = lat_even - 360

    if lat_odd >= 270:
        lat_odd = lat_odd - 360

    # check if both are in the same latidude zone, exit if not
    if common.cprNL(lat_even) != common.cprNL(lat_odd):
        return None

    # compute ni, longitude index m, and longitude
    # (people pass int+int or datetime+datetime)
    if t0 > t1:  # type: ignore
        lat = lat_even
        nl = common.cprNL(lat)
        ni = max(common.cprNL(lat) - 0, 1)
        m = common.floor(cprlon_even * (nl - 1) - cprlon_odd * nl + 0.5)
        lon = (360 / ni) * (m % ni + cprlon_even)
    else:
        lat = lat_odd
        nl = common.cprNL(lat)
        ni = max(common.cprNL(lat) - 1, 1)
        m = common.floor(cprlon_even * (nl - 1) - cprlon_odd * nl + 0.5)
        lon = (360 / ni) * (m % ni + cprlon_odd)

    if lon > 180:
        lon = lon - 360

    return round(lat, 5), round(lon, 5)


def airborne_position_with_ref(
    msg: str, lat_ref: float, lon_ref: float
) -> tuple[float, float]:
    """Decode airborne position with only one message,
    knowing reference nearby location, such as previously calculated location,
    ground station, or airport location, etc. The reference position shall
    be within 180NM of the true position.

    Args:
        msg (str): even message (28 hexdigits)
        lat_ref: previous known latitude
        lon_ref: previous known longitude

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """

    mb = common.hex2bin(msg)[32:]

    cprlat = common.bin2int(mb[22:39]) / 131072
    cprlon = common.bin2int(mb[39:56]) / 131072

    i = int(mb[21])
    d_lat = 360 / 59 if i else 360 / 60

    j = common.floor(lat_ref / d_lat) + common.floor(
        0.5 + ((lat_ref % d_lat) / d_lat) - cprlat
    )

    lat = d_lat * (j + cprlat)

    ni = common.cprNL(lat) - i

    if ni > 0:
        d_lon = 360 / ni
    else:
        d_lon = 360

    m = common.floor(lon_ref / d_lon) + common.floor(
        0.5 + ((lon_ref % d_lon) / d_lon) - cprlon
    )

    lon = d_lon * (m + cprlon)

    return round(lat, 5), round(lon, 5)


def altitude(msg: str) -> None | int:
    """Decode aircraft altitude

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: altitude in feet
    """

    tc = common.typecode(msg)

    if tc is None or tc < 9 or tc == 19 or tc > 22:
        raise RuntimeError("%s: Not an airborne position message" % msg)

    mb = common.hex2bin(msg)[32:]
    altbin = mb[8:20]

    if tc < 19:
        altcode = altbin[0:6] + "0" + altbin[6:]
        return common.altitude(altcode)
    else:
        return common.bin2int(altbin) * 3.28084  # type: ignore
