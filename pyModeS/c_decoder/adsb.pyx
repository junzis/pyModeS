# cython: language_level=3

"""ADS-B Wrapper.

The ADS-B wrapper also imports functions from the following modules:

- pyModeS.decoder.bds.bds05
    Functions: ``airborne_position``, ``airborne_position_with_ref``, ``altitude``
- pyModeS.decoder.bds.bds06
    Functions: ``surface_position``, ``surface_position_with_ref``, ``surface_velocity``
- pyModeS.decoder.bds.bds08
    Functions: ``category``, ``callsign``
- pyModeS.decoder.bds.bds09
    Functions: ``airborne_velocity``, ``altitude_diff``

"""

from libc.math cimport NAN as nan

from . cimport common

from .bds.bds05 import (
    airborne_position,
    airborne_position_with_ref,
    altitude,
)
from .bds.bds06 import (
    surface_position,
    surface_position_with_ref,
    surface_velocity,
)
from .bds.bds08 import category, callsign
from .bds.bds09 import airborne_velocity, altitude_diff

def icao(bytes msg):
    return common.icao(msg)

def typecode(bytes msg):
    return common.typecode(msg)

def position(bytes msg0 not None, bytes msg1 not None, double t0, double t1, double lat_ref=nan, double lon_ref=nan):
    """Decode position from a pair of even and odd position message
    (works with both airborne and surface position messages)

    Args:
        msg0 (string): even message (28 bytes hexadecimal string)
        msg1 (string): odd message (28 bytes hexadecimal string)
        t0 (double): timestamps for the even message
        t1 (double): timestamps for the odd message

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """
    cdef int tc0 = typecode(msg0)
    cdef int tc1 = typecode(msg1)

    if 5 <= tc0 <= 8 and 5 <= tc1 <= 8:
        if (lat_ref != lat_ref) or (lon_ref != lon_ref):
            raise RuntimeError(
                "Surface position encountered, a reference \
                               position lat/lon required. Location of \
                               receiver can be used."
            )
        else:
            return surface_position(msg0, msg1, t0, t1, lat_ref, lon_ref)

    elif 9 <= tc0 <= 18 and 9 <= tc1 <= 18:
        # Airborne position with barometric height
        return airborne_position(msg0, msg1, t0, t1)

    elif 20 <= tc0 <= 22 and 20 <= tc1 <= 22:
        # Airborne position with GNSS height
        return airborne_position(msg0, msg1, t0, t1)

    else:
        raise RuntimeError("incorrect or inconsistant message types")


def position_with_ref(bytes msg not None, double lat_ref, double lon_ref):
    """Decode position with only one message,
    knowing reference nearby location, such as previously
    calculated location, ground station, or airport location, etc.
    Works with both airborne and surface position messages.
    The reference position shall be with in 180NM (airborne) or 45NM (surface)
    of the true position.

    Args:
        msg (string): even message (28 bytes hexadecimal string)
        lat_ref: previous known latitude
        lon_ref: previous known longitude

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """

    cdef int tc = typecode(msg)

    if 5 <= tc <= 8:
        return surface_position_with_ref(msg, lat_ref, lon_ref)

    elif 9 <= tc <= 18 or 20 <= tc <= 22:
        return airborne_position_with_ref(msg, lat_ref, lon_ref)

    else:
        raise RuntimeError("incorrect or inconsistant message types")


def altitude(bytes msg):
    """Decode aircraft altitude

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: altitude in feet
    """

    cdef int tc = typecode(msg)

    if tc < 5 or tc == 19 or tc > 22:
        raise RuntimeError("%s: Not a position message" % msg)

    if tc >= 5 and tc <= 8:
        # surface position, altitude 0
        return 0

    cdef bytearray msgbin = common.hex2bin(msg)
    cdef int q = common.char_to_int(msgbin[47])
    cdef int n
    cdef double alt
    if q:
        n = common.bin2int(msgbin[40:47] + msgbin[48:52])
        alt = n * 25 - 1000
        return alt
    else:
        return nan


def velocity(bytes msg, bint rtn_sources=False):
    """Calculate the speed, heading, and vertical rate
    (handles both airborne or surface message)

    Args:
        msg (string): 28 bytes hexadecimal message string
        rtn_source (boolean): If the function will return
            the sources for direction of travel and vertical
            rate. This will change the return value from a four
            element array to a six element array.

    Returns:
        (int, float, int, string, string, string): speed (kt),
            ground track or heading (degree),
            rate of climb/descent (ft/min), speed type
            ('GS' for ground speed, 'AS' for airspeed),
            direction source ('true_north' for ground track / true north
            as refrence, 'mag_north' for magnetic north as reference),
            rate of climb/descent source ('Baro' for barometer, 'GNSS'
            for GNSS constellation).

            In the case of surface messages, None will be put in place
            for vertical rate and its respective sources.
    """

    cdef int tc = typecode(msg)

    if 5 <= tc <= 8:
        return surface_velocity(msg, rtn_sources)

    elif tc == 19:
        return airborne_velocity(msg, rtn_sources)

    else:
        raise RuntimeError(
            "incorrect or inconsistant message types, expecting 4<TC<9 or TC=19"
        )


def speed_heading(bytes msg):
    """Get speed and ground track (or heading) from the velocity message
    (handles both airborne or surface message)

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        (int, float): speed (kt), ground track or heading (degree)
    """
    spd, trk_or_hdg, rocd, tag = velocity(msg)
    return spd, trk_or_hdg


def oe_flag(bytes msg):
    """Check the odd/even flag. Bit 54, 0 for even, 1 for odd.
    Args:
        msg (string): 28 bytes hexadecimal message string
    Returns:
        int: 0 or 1, for even or odd frame
    """
    cdef bytearray msgbin = common.hex2bin(msg)
    return common.char_to_int(msgbin[53])


def version(bytes msg):
    """ADS-B Version

    Args:
        msg (string): 28 bytes hexadecimal message string, TC = 31

    Returns:
        int: version number
    """
    cdef int tc = typecode(msg)

    if tc != 31:
        raise RuntimeError(
            "%s: Not a status operation message, expecting TC = 31" % msg
        )

    cdef bytearray msgbin = common.hex2bin(msg)
    cdef int version = common.bin2int(msgbin[72:75])

    return version
