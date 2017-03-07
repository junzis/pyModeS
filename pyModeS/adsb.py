# Copyright (C) 2015 Junzi Sun (TU Delft)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
A python package for decoding ABS-D messages.
"""

import math
from . import util


def df(msg):
    """Get the downlink format (DF) number

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: DF number
    """
    return util.df(msg)


def icao(msg):
    """Get the ICAO 24 bits address, bytes 3 to 8.

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        String: ICAO address in 6 bytes hexadecimal string
    """
    return msg[2:8]


def data(msg):
    """Return the data frame in the message, bytes 9 to 22"""
    return msg[8:22]


def typecode(msg):
    """Type code of ADS-B message

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: type code number
    """
    msgbin = util.hex2bin(msg)
    return util.bin2int(msgbin[32:37])


# ---------------------------------------------
# Aircraft Identification
# ---------------------------------------------
def category(msg):
    """Aircraft category number

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: category number
    """

    if typecode(msg) < 1 or typecode(msg) > 4:
        raise RuntimeError("%s: Not a identification message" % msg)
    msgbin = util.hex2bin(msg)
    return util.bin2int(msgbin[5:8])


def callsign(msg):
    """Aircraft callsign

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        string: callsign
    """

    if typecode(msg) < 1 or typecode(msg) > 4:
        raise RuntimeError("%s: Not a identification message" % msg)

    chars = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ#####_###############0123456789######'
    msgbin = util.hex2bin(msg)
    csbin = msgbin[40:96]

    cs = ''
    cs += chars[util.bin2int(csbin[0:6])]
    cs += chars[util.bin2int(csbin[6:12])]
    cs += chars[util.bin2int(csbin[12:18])]
    cs += chars[util.bin2int(csbin[18:24])]
    cs += chars[util.bin2int(csbin[24:30])]
    cs += chars[util.bin2int(csbin[30:36])]
    cs += chars[util.bin2int(csbin[36:42])]
    cs += chars[util.bin2int(csbin[42:48])]

    # clean string, remove spaces and marks, if any.
    # cs = cs.replace('_', '')
    cs = cs.replace('#', '')
    return cs


# ---------------------------------------------
# Positions
# ---------------------------------------------

def oe_flag(msg):
    """Check the odd/even flag. Bit 54, 0 for even, 1 for odd.

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: 0 or 1, for even or odd frame
    """
    if typecode(msg) < 5 or typecode(msg) > 18:
        raise RuntimeError("%s: Not a position message" % msg)

    msgbin = util.hex2bin(msg)
    return int(msgbin[53])


def cprlat(msg):
    """CPR encoded latitude

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: encoded latitude
    """
    if typecode(msg) < 5 or typecode(msg) > 18:
        raise RuntimeError("%s: Not a position message" % msg)

    msgbin = util.hex2bin(msg)
    return util.bin2int(msgbin[54:71])


def cprlon(msg):
    """CPR encoded longitude

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: encoded longitude
    """
    if typecode(msg) < 5 or typecode(msg) > 18:
        raise RuntimeError("%s: Not a position message" % msg)

    msgbin = util.hex2bin(msg)
    return util.bin2int(msgbin[71:88])


def position(msg0, msg1, t0, t1, lat_ref=None, lon_ref=None):
    """Decode position from a pair of even and odd position message
    (works with both airborne and surface position messages)

    Args:
        msg0 (string): even message (28 bytes hexadecimal string)
        msg1 (string): odd message (28 bytes hexadecimal string)
        t0 (int): timestamps for the even message
        t1 (int): timestamps for the odd message

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """
    if (5 <= typecode(msg0) <= 8 and 5 <= typecode(msg1) <= 8):
        if (not lat_ref) or (not lon_ref):
            raise RuntimeError("Surface position encountered, a reference \
                               position lat/lon required. Location of \
                               receiver can be used.")
        else:
            return surface_position(msg0, msg1, t0, t1, lat_ref, lon_ref)

    elif (9 <= typecode(msg0) <= 18 and 9 <= typecode(msg1) <= 18):
        return airborne_position(msg0, msg1, t0, t1)

    else:
        raise RuntimeError("incorrect or inconsistant message types")


def airborne_position(msg0, msg1, t0, t1):
    """Decode airborn position from a pair of even and odd position message

    Args:
        msg0 (string): even message (28 bytes hexadecimal string)
        msg1 (string): odd message (28 bytes hexadecimal string)
        t0 (int): timestamps for the even message
        t1 (int): timestamps for the odd message

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """

    msgbin0 = util.hex2bin(msg0)
    msgbin1 = util.hex2bin(msg1)

    # 131072 is 2^17, since CPR lat and lon are 17 bits each.
    cprlat_even = util.bin2int(msgbin0[54:71]) / 131072.0
    cprlon_even = util.bin2int(msgbin0[71:88]) / 131072.0
    cprlat_odd = util.bin2int(msgbin1[54:71]) / 131072.0
    cprlon_odd = util.bin2int(msgbin1[71:88]) / 131072.0

    air_d_lat_even = 360.0 / 60
    air_d_lat_odd = 360.0 / 59

    # compute latitude index 'j'
    j = util.floor(59 * cprlat_even - 60 * cprlat_odd + 0.5)

    lat_even = float(air_d_lat_even * (j % 60 + cprlat_even))
    lat_odd = float(air_d_lat_odd * (j % 59 + cprlat_odd))

    if lat_even >= 270:
        lat_even = lat_even - 360

    if lat_odd >= 270:
        lat_odd = lat_odd - 360

    # check if both are in the same latidude zone, exit if not
    if _cprNL(lat_even) != _cprNL(lat_odd):
        return None

    # compute ni, longitude index m, and longitude
    if (t0 > t1):
        lat = lat_even
        nl = _cprNL(lat)
        ni = max(_cprNL(lat)- 0, 1)
        m = util.floor(cprlon_even * (nl-1) - cprlon_odd * nl + 0.5)
        lon = (360.0 / ni) * (m % ni + cprlon_even)
    else:
        lat = lat_odd
        nl = _cprNL(lat)
        ni = max(_cprNL(lat) - 1, 1)
        m = util.floor(cprlon_even * (nl-1) - cprlon_odd * nl + 0.5)
        lon = (360.0 / ni) * (m % ni + cprlon_odd)

    if lon > 180:
        lon = lon - 360

    return round(lat, 5), round(lon, 5)


def position_with_ref(msg, lat_ref, lon_ref):
    """Decode position with only one message,
    knowing reference nearby location, such as previously
    calculated location, ground station, or airport location, etc.
    Works with both airborne and surface position messages.
    The reference position shall be with in 180NM (airborne) or 45NM (surface)
    of the true position.

    Args:
        msg0 (string): even message (28 bytes hexadecimal string)
        msg1 (string): odd message (28 bytes hexadecimal string)
        t0 (int): timestamps for the even message
        t1 (int): timestamps for the odd message

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """
    if 5 <= typecode(msg) <= 8:
        return surface_position_with_ref(msg, lat_ref, lon_ref)

    elif 9 <= typecode(msg) <= 18:
        return airborne_position_with_ref(msg, lat_ref, lon_ref)

    else:
        raise RuntimeError("incorrect or inconsistant message types")


def airborne_position_with_ref(msg, lat_ref, lon_ref):
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

    i = oe_flag(msg)
    d_lat = 360.0/59 if i else 360.0/60

    msgbin = util.hex2bin(msg)
    cprlat = util.bin2int(msgbin[54:71]) / 131072.0
    cprlon = util.bin2int(msgbin[71:88]) / 131072.0

    j = util.floor(lat_ref / d_lat) \
        + util.floor(0.5 + ((lat_ref % d_lat) / d_lat) - cprlat)

    lat = d_lat * (j + cprlat)

    ni = _cprNL(lat) - i

    if ni > 0:
        d_lon = 360.0 / ni
    else:
        d_lon = 360.0

    m = util.floor(lon_ref / d_lon) \
        + util.floor(0.5 + ((lon_ref % d_lon) / d_lon) - cprlon)

    lon = d_lon * (m + cprlon)

    return round(lat, 5), round(lon, 5)


def surface_position(msg0, msg1, t0, t1, lat_ref, lon_ref):
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

    msgbin0 = util.hex2bin(msg0)
    msgbin1 = util.hex2bin(msg1)

    # 131072 is 2^17, since CPR lat and lon are 17 bits each.
    cprlat_even = util.bin2int(msgbin0[54:71]) / 131072.0
    cprlon_even = util.bin2int(msgbin0[71:88]) / 131072.0
    cprlat_odd = util.bin2int(msgbin1[54:71]) / 131072.0
    cprlon_odd = util.bin2int(msgbin1[71:88]) / 131072.0

    air_d_lat_even = 90.0 / 60
    air_d_lat_odd = 90.0 / 59

    # compute latitude index 'j'
    j = util.floor(59 * cprlat_even - 60 * cprlat_odd + 0.5)

    # solution for north hemisphere
    lat_even_n = float(air_d_lat_even * (j % 60 + cprlat_even))
    lat_odd_n = float(air_d_lat_odd * (j % 59 + cprlat_odd))

    # solution for north hemisphere
    lat_even_s = lat_even_n - 90.0
    lat_odd_s = lat_odd_n - 90.0

    # chose which solution corrispondes to receiver location
    lat_even = lat_even_n if lat_ref > 0 else lat_even_s
    lat_odd = lat_odd_n if lat_ref > 0 else lat_odd_s

    # check if both are in the same latidude zone, rare but possible
    if _cprNL(lat_even) != _cprNL(lat_odd):
        return None

    # compute ni, longitude index m, and longitude
    if (t0 > t1):
        lat = lat_even
        nl = _cprNL(lat_even)
        ni = max(_cprNL(lat_even) - 0, 1)
        m = util.floor(cprlon_even * (nl-1) - cprlon_odd * nl + 0.5)
        lon = (90.0 / ni) * (m % ni + cprlon_even)
    else:
        lat = lat_odd
        nl = _cprNL(lat_odd)
        ni = max(_cprNL(lat_odd) - 1, 1)
        m = util.floor(cprlon_even * (nl-1) - cprlon_odd * nl + 0.5)
        lon = (90.0 / ni) * (m % ni + cprlon_odd)

    # four possible longitude solutions
    lons = [lon, lon + 90.0, lon + 180.0, lon + 270.0]

    # the closest solution to receiver is the correct one
    dls = [abs(lon_ref - l) for l in lons]
    imin = min(range(4), key=dls.__getitem__)
    lon = lons[imin]

    return round(lat, 5), round(lon, 5)


def surface_position_with_ref(msg, lat_ref, lon_ref):
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

    i = oe_flag(msg)
    d_lat = 90.0/59 if i else 90.0/60

    msgbin = util.hex2bin(msg)
    cprlat = util.bin2int(msgbin[54:71]) / 131072.0
    cprlon = util.bin2int(msgbin[71:88]) / 131072.0

    j = util.floor(lat_ref / d_lat) \
        + util.floor(0.5 + ((lat_ref % d_lat) / d_lat) - cprlat)

    lat = d_lat * (j + cprlat)

    ni = _cprNL(lat) - i

    if ni > 0:
        d_lon = 90.0 / ni
    else:
        d_lon = 90.0

    m = util.floor(lon_ref / d_lon) \
        + util.floor(0.5 + ((lon_ref % d_lon) / d_lon) - cprlon)

    lon = d_lon * (m + cprlon)

    return round(lat, 5), round(lon, 5)


def _cprNL(lat):
    """NL() function in CPR decoding
    """
    if lat == 0:
        return 59

    if lat == 87 or lat == -87:
        return 2

    if lat > 87 or lat < -87:
        return 1

    nz = 15
    a = 1 - math.cos(math.pi / (2 * nz))
    b = math.cos(math.pi / 180.0 * abs(lat)) ** 2
    nl = 2 * math.pi / (math.acos(1 - a/b))
    NL = util.floor(nl)
    return NL


def altitude(msg):
    """Decode aircraft altitude

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: altitude in feet
    """
    if typecode(msg) < 9 or typecode(msg) > 18:
        raise RuntimeError("%s: Not a position message" % msg)

    msgbin = util.hex2bin(msg)
    q = msgbin[47]
    if q:
        n = util.bin2int(msgbin[40:47]+msgbin[48:52])
        alt = n * 25 - 1000
        return alt
    else:
        return None


def nic(msg):
    """Calculate NIC, navigation integrity category

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: NIC number (from 0 to 11), -1 if not applicable
    """
    if typecode(msg) < 9 or typecode(msg) > 18:
        raise RuntimeError("%s: Not a airborne position message" % msg)

    msgbin = util.hex2bin(msg)
    tc = typecode(msg)
    nic_sup_b = util.bin2int(msgbin[39])

    if tc in [0, 18, 22]:
        nic = 0
    elif tc == 17:
        nic = 1
    elif tc == 16:
        if nic_sup_b:
            nic = 3
        else:
            nic = 2
    elif tc == 15:
        nic = 4
    elif tc == 14:
        nic = 5
    elif tc == 13:
        nic = 6
    elif tc == 12:
        nic = 7
    elif tc == 11:
        if nic_sup_b:
            nic = 9
        else:
            nic = 8
    elif tc in [10, 21]:
        nic = 10
    elif tc in [9, 20]:
        nic = 11
    else:
        nic = -1
    return nic


# ---------------------------------------------
# Velocity
# ---------------------------------------------

def velocity(msg):
    """Calculate the speed, heading, and vertical rate

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        (int, float, int, string): speed (kt), heading (degree),
            rate of climb/descend (ft/min), and speed type
            ('GS' for ground speed, 'AS' for airspeed)
    """

    if typecode(msg) != 19:
        raise RuntimeError("%s: Not a airborne velocity message" % msg)

    msgbin = util.hex2bin(msg)

    subtype = util.bin2int(msgbin[37:40])

    if subtype in (1, 2):
        v_ew_sign = util.bin2int(msgbin[45])
        v_ew = util.bin2int(msgbin[46:56]) - 1       # east-west velocity

        v_ns_sign = util.bin2int(msgbin[56])
        v_ns = util.bin2int(msgbin[57:67]) - 1       # north-south velocity

        v_we = -1*v_ew if v_ew_sign else v_ew
        v_sn = -1*v_ns if v_ns_sign else v_ns

        spd = math.sqrt(v_sn*v_sn + v_we*v_we)  # unit in kts

        hdg = math.atan2(v_we, v_sn)
        hdg = math.degrees(hdg)                 # convert to degrees
        hdg = hdg if hdg >= 0 else hdg + 360    # no negative val

        tag = 'GS'

    else:
        hdg = util.bin2int(msgbin[46:56]) / 1024.0 * 360.0
        spd = util.bin2int(msgbin[57:67])

        tag = 'AS'

    vr_sign = util.bin2int(msgbin[68])
    vr = (util.bin2int(msgbin[69:78]) - 1) * 64     # vertical rate, fpm
    rocd = -1*vr if vr_sign else vr                 # rate of climb/descend

    return int(spd), round(hdg, 1), int(rocd), tag


def speed_heading(msg):
    """Get speed and heading only from the velocity message

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        (int, float): speed (kt), heading (degree)
    """
    spd, hdg, rocd, tag = velocity(msg)
    return spd, hdg
