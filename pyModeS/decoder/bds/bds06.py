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
  BDS 0,6
  ADS-B TC=5-8
  Surface position
------------------------------------------
"""

from __future__ import absolute_import, print_function, division
from pyModeS.decoder import common
import math


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

    msgbin0 = common.hex2bin(msg0)
    msgbin1 = common.hex2bin(msg1)

    # 131072 is 2^17, since CPR lat and lon are 17 bits each.
    cprlat_even = common.bin2int(msgbin0[54:71]) / 131072.0
    cprlon_even = common.bin2int(msgbin0[71:88]) / 131072.0
    cprlat_odd = common.bin2int(msgbin1[54:71]) / 131072.0
    cprlon_odd = common.bin2int(msgbin1[71:88]) / 131072.0

    air_d_lat_even = 90.0 / 60
    air_d_lat_odd = 90.0 / 59

    # compute latitude index 'j'
    j = common.floor(59 * cprlat_even - 60 * cprlat_odd + 0.5)

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
    if common.cprNL(lat_even) != common.cprNL(lat_odd):
        return None

    # compute ni, longitude index m, and longitude
    if (t0 > t1):
        lat = lat_even
        nl = common.cprNL(lat_even)
        ni = max(common.cprNL(lat_even) - 0, 1)
        m = common.floor(cprlon_even * (nl-1) - cprlon_odd * nl + 0.5)
        lon = (90.0 / ni) * (m % ni + cprlon_even)
    else:
        lat = lat_odd
        nl = common.cprNL(lat_odd)
        ni = max(common.cprNL(lat_odd) - 1, 1)
        m = common.floor(cprlon_even * (nl-1) - cprlon_odd * nl + 0.5)
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


    mb = common.hex2bin(msg)[32:]

    cprlat = common.bin2int(mb[22:39]) / 131072.0
    cprlon = common.bin2int(mb[39:56]) / 131072.0

    i = int(mb[21])
    d_lat = 90.0/59 if i else 90.0/60

    j = common.floor(lat_ref / d_lat) \
        + common.floor(0.5 + ((lat_ref % d_lat) / d_lat) - cprlat)

    lat = d_lat * (j + cprlat)

    ni = common.cprNL(lat) - i

    if ni > 0:
        d_lon = 90.0 / ni
    else:
        d_lon = 90.0

    m = common.floor(lon_ref / d_lon) \
        + common.floor(0.5 + ((lon_ref % d_lon) / d_lon) - cprlon)

    lon = d_lon * (m + cprlon)

    return round(lat, 5), round(lon, 5)


def surface_velocity(msg):
    """Decode surface velocity from from a surface position message
    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        (int, float, int, string): speed (kt), ground track (degree),
            rate of climb/descend (ft/min), and speed type
            ('GS' for ground speed, 'AS' for airspeed)
    """

    if common.typecode(msg) < 5 or common.typecode(msg) > 8:
        raise RuntimeError("%s: Not a surface message, expecting 5<TC<8" % msg)

    mb = common.hex2bin(msg)[32:]

    # ground track
    trk_status = int(mb[12])
    if trk_status == 1:
        trk = common.bin2int(mb[13:20]) * 360.0 / 128.0
        trk = round(trk, 1)
    else:
        trk = None

    # ground movment / speed
    mov = common.bin2int(mb[5:12])

    if mov == 0 or mov > 124:
        spd = None
    elif mov == 1:
        spd = 0
    elif mov == 124:
        spd = 175
    else:
        movs = [2, 9, 13, 39, 94, 109, 124]
        kts = [0.125, 1, 2, 15, 70, 100, 175]
        i = next(m[0] for m in enumerate(movs) if m[1] > mov)
        step = (kts[i] - kts[i-1]) * 1.0 / (movs[i]-movs[i-1])
        spd = kts[i-1] + (mov-movs[i-1]) * step
        spd = round(spd, 2)

    return spd, trk, 0, 'GS'
