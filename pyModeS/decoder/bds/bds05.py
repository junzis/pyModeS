# Copyright (C) 2018 Junzi Sun (TU Delft)

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
------------------------------------------
  BDS 0,5
  ADS-B TC=9-18
  Airborn position
------------------------------------------
"""

from __future__ import absolute_import, print_function, division
from pyModeS.decoder import common

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

    mb0 = common.hex2bin(msg0)[32:]
    mb1 = common.hex2bin(msg1)[32:]

    # 131072 is 2^17, since CPR lat and lon are 17 bits each.
    cprlat_even = common.bin2int(mb0[22:39]) / 131072.0
    cprlon_even = common.bin2int(mb0[39:56]) / 131072.0
    cprlat_odd = common.bin2int(mb1[22:39]) / 131072.0
    cprlon_odd = common.bin2int(mb1[39:56]) / 131072.0

    air_d_lat_even = 360.0 / 60
    air_d_lat_odd = 360.0 / 59

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
    if (t0 > t1):
        lat = lat_even
        nl = common.cprNL(lat)
        ni = max(common.cprNL(lat)- 0, 1)
        m = common.floor(cprlon_even * (nl-1) - cprlon_odd * nl + 0.5)
        lon = (360.0 / ni) * (m % ni + cprlon_even)
    else:
        lat = lat_odd
        nl = common.cprNL(lat)
        ni = max(common.cprNL(lat) - 1, 1)
        m = common.floor(cprlon_even * (nl-1) - cprlon_odd * nl + 0.5)
        lon = (360.0 / ni) * (m % ni + cprlon_odd)

    if lon > 180:
        lon = lon - 360

    return round(lat, 5), round(lon, 5)


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


    mb = common.hex2bin(msg)[32:]

    cprlat = common.bin2int(mb[22:39]) / 131072.0
    cprlon = common.bin2int(mb[39:56]) / 131072.0

    i = int(mb[21])
    d_lat = 360.0/59 if i else 360.0/60

    j = common.floor(lat_ref / d_lat) \
        + common.floor(0.5 + ((lat_ref % d_lat) / d_lat) - cprlat)

    lat = d_lat * (j + cprlat)

    ni = common.cprNL(lat) - i

    if ni > 0:
        d_lon = 360.0 / ni
    else:
        d_lon = 360.0

    m = common.floor(lon_ref / d_lon) \
        + common.floor(0.5 + ((lon_ref % d_lon) / d_lon) - cprlon)

    lon = d_lon * (m + cprlon)

    return round(lat, 5), round(lon, 5)


def altitude(msg):
    """Decode aircraft altitude

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: altitude in feet
    """

    tc = common.typecode(msg)

    if tc<9 or tc==19 or tc>22:
        raise RuntimeError("%s: Not a airborn position message" % msg)

    mb = common.hex2bin(msg)[32:]

    if tc < 19:
        # barometric altitude
        q = mb[15]
        if q:
            n = common.bin2int(mb[8:15]+mb[16:20])
            alt = n * 25 - 1000
        else:
            alt = None
    else:
        # GNSS altitude, meters -> feet
        alt = common.bin2int(mb[8:20]) * 3.28084

    return alt
