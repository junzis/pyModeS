# ------------------------------------------
#   BDS 0,6
#   ADS-B TC=5-8
#   Surface position
# ------------------------------------------

# cython: language_level=3

cimport cython

from .. cimport common
from cpython cimport array
from libc.math cimport NAN as nan

import math


@cython.cdivision(True)
def surface_position(bytes msg0 not None, bytes msg1 not None, long t0, long t1, double lat_ref, double lon_ref):
    """Decode surface position from a pair of even and odd position message,
    the lat/lon of receiver must be provided to yield the correct solution.

    Args:
        msg0 (string): even message (28 bytes hexadecimal string)
        msg1 (string): odd message (28 bytes hexadecimal string)
        t0 (int): timestamps for the even message
        t1 (int): timestamps for the odd message
        lat_ref (float): latitude of the receiver
        lon_ref (float): longitude of the receiver

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """

    cdef bytearray msgbin0 = common.hex2bin(msg0)
    cdef bytearray msgbin1 = common.hex2bin(msg1)

    # 131072 is 2^17, since CPR lat and lon are 17 bits each.
    cdef double cprlat_even = common.bin2int(msgbin0[54:71]) / 131072.0
    cdef double cprlon_even = common.bin2int(msgbin0[71:88]) / 131072.0
    cdef double cprlat_odd = common.bin2int(msgbin1[54:71]) / 131072.0
    cdef double cprlon_odd = common.bin2int(msgbin1[71:88]) / 131072.0

    cdef double air_d_lat_even = 90.0 / 60
    cdef double air_d_lat_odd = 90.0 / 59

    # compute latitude index 'j'
    cdef long j = common.floor(59 * cprlat_even - 60 * cprlat_odd + 0.5)

    # solution for north hemisphere
    cdef int j_mod_60 = j % 60 if j > 0 else (j % 60) + 60
    cdef int j_mod_59 = j % 59 if j > 0 else (j % 59) + 59
    cdef double lat_even_n = (air_d_lat_even * ((j_mod_60) + cprlat_even))
    cdef double lat_odd_n = (air_d_lat_odd * ((j_mod_59) + cprlat_odd))

    # solution for north hemisphere
    cdef double lat_even_s = lat_even_n - 90.0
    cdef double lat_odd_s = lat_odd_n - 90.0

    # chose which solution corrispondes to receiver location
    cdef double lat_even = lat_even_n if lat_ref > 0 else lat_even_s
    cdef double lat_odd = lat_odd_n if lat_ref > 0 else lat_odd_s

    # check if both are in the same latidude zone, rare but possible
    if common.cprNL(lat_even) != common.cprNL(lat_odd):
        return nan

    cdef int nl, ni, m, m_mod_ni
    cdef double lat, lon

    # compute ni, longitude index m, and longitude
    if t0 > t1:
        lat = lat_even
        nl = common.cprNL(lat_even)
        # ni = max(common.cprNL(lat_even) - 0, 1)
        ni = common.cprNL(lat_even)
        if ni < 1:
            ni = 1
        m = common.floor(cprlon_even * (nl - 1) - cprlon_odd * nl + 0.5)
        # https://docs.python.org/3/library/math.html#math.fmod
        m_mod_ni = m % ni if ni > 0 else (m % ni) + ni
        lon = (90.0 / ni) * (m_mod_ni + cprlon_even)
    else:
        lat = lat_odd
        nl = common.cprNL(lat_odd)
        # ni = max(common.cprNL(lat_odd) - 1, 1)
        ni = common.cprNL(lat_odd) - 1
        if ni < 1:
            ni = 1
        m = common.floor(cprlon_even * (nl - 1) - cprlon_odd * nl + 0.5)
        # https://docs.python.org/3/library/math.html#math.fmod
        m_mod_ni = m % ni if ni > 0 else (m % ni) + ni
        lon = (90.0 / ni) * (m_mod_ni + cprlon_odd)

    # four possible longitude solutions
    # lons = [lon, lon + 90.0, lon + 180.0, lon + 270.0]
    cdef array.array _lons = array.array(
        'd', [lon, lon + 90.0, lon + 180.0, lon + 270.0]
    )
    cdef double[4] lons = _lons

    # make sure lons are between -180 and 180
    # lons = [(l + 180) % 360 - 180 for l in lons]
    cdef int idxmin = 0
    cdef float d_, delta = abs(lons[0] - lon_ref)

    for i in range(1, 4):
        lons[i] = (lons[i] + 180) % 360 - 180
        d_ = abs(lons[i] - lon_ref)
        if d_ < delta:
            idxmin = i
            delta = d_

    # the closest solution to receiver is the correct one
    # dls = [abs(lon_ref - l) for l in lons]
    # imin = min(range(4), key=dls.__getitem__)
    # lon = lons[imin]

    lon = lons[idxmin]
    return round(lat, 5), round(lon, 5)


@cython.cdivision(True)
def surface_position_with_ref(bytes msg not None, double lat_ref, double lon_ref):
    """Decode surface position with only one message,
    knowing reference nearby location, such as previously calculated location,
    ground station, or airport location, etc. The reference position shall
    be with in 45NM of the true position.

    Args:
        msg (string): even message (28 bytes hexadecimal string)
        lat_ref: previous known latitude
        lon_ref: previous known longitude

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """

    cdef bytearray mb = common.hex2bin(msg)[32:]

    cdef double cprlat = common.bin2int(mb[22:39]) / 131072.0
    cdef double cprlon = common.bin2int(mb[39:56]) / 131072.0

    cdef unsigned char i = common.char_to_int(mb[21])
    cdef double d_lat = 90.0 / 59 if i else 90.0 / 60

    # https://docs.python.org/3/library/math.html#math.fmod
    cdef double mod_lat = lat_ref % d_lat if lat_ref >= 0 else (lat_ref % d_lat + d_lat)
    cdef long j = common.floor(lat_ref / d_lat) + common.floor(
        0.5 + (mod_lat / d_lat) - cprlat
    )

    cdef double lat = d_lat * (j + cprlat)
    cdef double d_lon, lon

    cdef int ni = common.cprNL(lat) - i

    if ni > 0:
        d_lon = 90.0 / ni
    else:
        d_lon = 90.0

    # https://docs.python.org/3/library/math.html#math.fmod
    cdef double mod_lon = lon_ref % d_lon if lon_ref >= 0 else (lon_ref % d_lon + d_lon)
    cdef int m = common.floor(lon_ref / d_lon) + common.floor(
        0.5 + (mod_lon / d_lon) - cprlon
    )

    lon = d_lon * (m + cprlon)

    return round(lat, 5), round(lon, 5)

@cython.cdivision(True)
def surface_velocity(bytes msg, bint rtn_sources=False):
    """Decode surface velocity from from a surface position message
    Args:
        msg (string): 28 bytes hexadecimal message string
        rtn_source (boolean): If the function will return
            the sources for direction of travel and vertical
            rate. This will change the return value from a four
            element array to a six element array.

    Returns:
        (int, float, int, string, string, None): speed (kt),
            ground track (degree), None for rate of climb/descend (ft/min),
            and speed type ('GS' for ground speed), direction source
            ('true_north' for ground track / true north as reference),
            None rate of climb/descent source.
    """

    if common.typecode(msg) < 5 or common.typecode(msg) > 8:
        raise RuntimeError("%s: Not a surface message, expecting 5<TC<8" % msg)

    cdef bytearray mb = common.hex2bin(msg)[32:]

    cdef double trk
    # ground track
    cdef unsigned char trk_status = common.char_to_int(mb[12])
    if trk_status == 1:
        trk = common.bin2int(mb[13:20]) * 360.0 / 128.0
        trk = round(trk, 1)
    else:
        trk = nan

    # ground movment / speed
    cdef long mov = common.bin2int(mb[5:12])
    cdef double spd, step
    cdef array.array _movs, _kts
    cdef double[7] movs, kts
    cdef Py_ssize_t i = 0

    if mov == 0 or mov > 124:
        spd = nan
    elif mov == 1:
        spd = 0
    elif mov == 124:
        spd = 175
    else:
        _movs = array.array('d', [2, 9, 13, 39, 94, 109, 124])
        _kts = array.array('d', [0.125, 1, 2, 15, 70, 100, 175])
        movs = _movs
        kts = _kts

        # i = next(m[0] for m in enumerate(movs) if m[1] > mov)
        for i in range(7):
            if movs[i] > mov:
                break

        step = (kts[i] - kts[i - 1]) * 1.0 / (movs[i] - movs[i - 1])
        spd = kts[i - 1] + (mov - movs[i - 1]) * step
        spd = round(spd, 2)

    if rtn_sources:
        return spd, trk, 0, "GS", "true_north", None
    else:
        return spd, trk, 0, "GS"
