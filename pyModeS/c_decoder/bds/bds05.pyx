# ------------------------------------------
#   BDS 0,5
#   ADS-B TC=9-18
#   Airborn position
# ------------------------------------------

# cython: language_level=3

cimport cython

from .. cimport common
from libc.math cimport NAN as nan


@cython.cdivision(True)
def airborne_position(bytes msg0 not None, bytes msg1 not None, long t0, long t1):
    """Decode airborn position from a pair of even and odd position message

    Args:
        msg0 (string): even message (28 bytes hexadecimal string)
        msg1 (string): odd message (28 bytes hexadecimal string)
        t0 (int): timestamps for the even message
        t1 (int): timestamps for the odd message

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """

    cdef bytearray mb0 = common.hex2bin(msg0)[32:]
    cdef bytearray mb1 = common.hex2bin(msg1)[32:]

    cdef unsigned char oe0 = common.char_to_int(mb0[21])
    cdef unsigned char oe1 = common.char_to_int(mb1[21])

    if oe0 == 0 and oe1 == 1:
        pass
    elif oe0 == 1 and oe1 == 0:
        mb0, mb1 = mb1, mb0
        t0, t1 = t1, t0
    else:
        raise RuntimeError("Both even and odd CPR frames are required.")

    # 131072 is 2^17, since CPR lat and lon are 17 bits each.
    cdef double cprlat_even = common.bin2int(mb0[22:39]) / 131072.0
    cdef double cprlon_even = common.bin2int(mb0[39:56]) / 131072.0
    cdef double cprlat_odd = common.bin2int(mb1[22:39]) / 131072.0
    cdef double cprlon_odd = common.bin2int(mb1[39:56]) / 131072.0

    cdef double air_d_lat_even = 360.0 / 60
    cdef double air_d_lat_odd = 360.0 / 59

    # compute latitude index 'j'
    cdef long j = common.floor(59 * cprlat_even - 60 * cprlat_odd + 0.5)

    cdef double lat_even = (air_d_lat_even * (j % 60 + cprlat_even))
    cdef double lat_odd = (air_d_lat_odd * (j % 59 + cprlat_odd))

    if lat_even >= 270:
        lat_even = lat_even - 360

    if lat_odd >= 270:
        lat_odd = lat_odd - 360

    # check if both are in the same latidude zone, exit if not
    if common.cprNL(lat_even) != common.cprNL(lat_odd):
        return nan

    cdef int nl, ni, m
    cdef double lat, lon

    # compute ni, longitude index m, and longitude
    if t0 > t1:
        lat = lat_even
        nl = common.cprNL(lat)
        # ni = max(common.cprNL(lat) - 0, 1)
        ni = common.cprNL(lat)
        if ni < 1:
            ni = 1
        m = common.floor(cprlon_even * (nl - 1) - cprlon_odd * nl + 0.5)
        lon = (360.0 / ni) * (m % ni + cprlon_even)
    else:
        lat = lat_odd
        nl = common.cprNL(lat)
        # ni = max(common.cprNL(lat) - 1, 1)
        ni = common.cprNL(lat) - 1
        if ni < 1:
            ni = 1
        m = common.floor(cprlon_even * (nl - 1) - cprlon_odd * nl + 0.5)
        lon = (360.0 / ni) * (m % ni + cprlon_odd)

    if lon > 180:
        lon = lon - 360

    return round(lat, 5), round(lon, 5)


@cython.cdivision(True)
def airborne_position_with_ref(bytes msg not None, double lat_ref, double lon_ref):
    """Decode airborne position with only one message,
    knowing reference nearby location, such as previously calculated location,
    ground station, or airport location, etc. The reference position shall
    be with in 180NM of the true position.

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
    cdef double d_lat = 360.0 / 59 if i else 360.0 / 60

    # https://docs.python.org/3/library/math.html#math.fmod
    cdef double mod_lat = lat_ref % d_lat if lat_ref >= 0 else (lat_ref % d_lat + d_lat)
    cdef long j = common.floor(lat_ref / d_lat) + common.floor(
        0.5 + (mod_lat / d_lat) - cprlat
    )

    cdef double lat = d_lat * (j + cprlat)
    cdef double d_lon, lon

    cdef int ni = common.cprNL(lat) - i

    if ni > 0:
        d_lon = 360.0 / ni
    else:
        d_lon = 360.0

    # https://docs.python.org/3/library/math.html#math.fmod
    cdef double mod_lon = lon_ref % d_lon if lon_ref >= 0 else (lon_ref % d_lon + d_lon)
    cdef int m = common.floor(lon_ref / d_lon) + common.floor(
        0.5 + (mod_lon / d_lon) - cprlon
    )

    lon = d_lon * (m + cprlon)

    return round(lat, 5), round(lon, 5)


cpdef double altitude(bytes msg):
    """Decode aircraft altitude

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: altitude in feet
    """

    cdef int tc = common.typecode(msg)

    if tc < 9 or tc == 19 or tc > 22:
        raise RuntimeError("%s: Not a airborn position message" % msg)

    cdef bytearray mb = common.hex2bin(msg)[32:]
    cdef unsigned char q
    cdef int n
    cdef double alt

    if tc < 19:
        # barometric altitude
        q = mb[15]
        if q:
            n = common.bin2int(mb[8:15] + mb[16:20])
            alt = n * 25 - 1000
        else:
            alt = nan
    else:
        # GNSS altitude, meters -> feet
        alt = common.bin2int(mb[8:20]) * 3.28084

    return alt
