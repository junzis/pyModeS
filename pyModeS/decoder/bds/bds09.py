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


# ------------------------------------------
#   BDS 0,9
#   ADS-B TC=19
#   Aircraft Airborn velocity
# ------------------------------------------

from __future__ import absolute_import, print_function, division
from pyModeS.decoder import common
import math


def airborne_velocity(msg, rtn_sources=False):
    """Calculate the speed, track (or heading), and vertical rate

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
            as reference, 'mag_north' for magnetic north as reference),
            rate of climb/descent source ('Baro' for barometer, 'GNSS'
            for GNSS constellation).
    """

    if common.typecode(msg) != 19:
        raise RuntimeError("%s: Not a airborne velocity message, expecting TC=19" % msg)

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:8])

    if common.bin2int(mb[14:24]) == 0 or common.bin2int(mb[25:35]) == 0:
        return None

    if subtype in (1, 2):
        v_ew_sign = -1 if mb[13] == "1" else 1
        v_ew = common.bin2int(mb[14:24]) - 1  # east-west velocity
        if subtype == 2:  # Supersonic
            v_ew *= 4

        v_ns_sign = -1 if mb[24] == "1" else 1
        v_ns = common.bin2int(mb[25:35]) - 1  # north-south velocity
        if subtype == 2:  # Supersonic
            v_ns *= 4

        v_we = v_ew_sign * v_ew
        v_sn = v_ns_sign * v_ns

        spd = math.sqrt(v_sn * v_sn + v_we * v_we)  # unit in kts
        spd = int(spd)

        trk = math.atan2(v_we, v_sn)
        trk = math.degrees(trk)  # convert to degrees
        trk = trk if trk >= 0 else trk + 360  # no negative val

        tag = "GS"
        trk_or_hdg = round(trk, 2)
        dir_type = "true_north"

    else:
        if mb[13] == "0":
            hdg = None
        else:
            hdg = common.bin2int(mb[14:24]) / 1024.0 * 360.0
            hdg = round(hdg, 2)

        trk_or_hdg = hdg

        spd = common.bin2int(mb[25:35])
        spd = None if spd == 0 else spd - 1
        if subtype == 4:  # Supersonic
            spd *= 4

        if mb[24] == "0":
            tag = "IAS"
        else:
            tag = "TAS"

        dir_type = "mag_north"

    vr_source = "GNSS" if mb[35] == "0" else "Baro"
    vr_sign = -1 if mb[36] == "1" else 1
    vr = common.bin2int(mb[37:46])
    rocd = None if vr == 0 else int(vr_sign * (vr - 1) * 64)

    if rtn_sources:
        return spd, trk_or_hdg, rocd, tag, dir_type, vr_source
    else:
        return spd, trk_or_hdg, rocd, tag


def altitude_diff(msg):
    """Decode the differece between GNSS and barometric altitude

    Args:
        msg (string): 28 bytes hexadecimal message string, TC=19

    Returns:
        int: Altitude difference in ft. Negative value indicates GNSS altitude
            below barometric altitude.
    """
    tc = common.typecode(msg)

    if tc != 19:
        raise RuntimeError("%s: Not a airborne velocity message, expecting TC=19" % msg)

    msgbin = common.hex2bin(msg)
    sign = -1 if int(msgbin[80]) else 1
    value = common.bin2int(msgbin[81:88])

    if value == 0 or value == 127:
        return None
    else:
        return sign * (value - 1) * 25  # in ft.
