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

from __future__ import absolute_import, print_function, division
from pyModeS.decoder.common import hex2bin, bin2int, data, allzeros, wrongstatus

# ------------------------------------------
# BDS 5,3
# Air-referenced state vector
# ------------------------------------------

def is53(msg):
    """Check if a message is likely to be BDS code 5,3
    (Air-referenced state vector)

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = hex2bin(data(msg))

    # status bit 1, 13, 24, 34, 47

    if wrongstatus(d, 1, 3, 12):
        return False

    if wrongstatus(d, 13, 14, 23):
        return False

    if wrongstatus(d, 24, 25, 33):
        return False

    if wrongstatus(d, 34, 35, 46):
        return False

    if wrongstatus(d, 47, 49, 56):
        return False

    ias = ias53(msg)
    if ias is not None and ias > 500:
        return False

    mach = mach53(msg)
    if mach is not None and mach > 1:
        return False

    tas = tas53(msg)
    if tas is not None and tas > 500:
        return False

    vr = vr53(msg)
    if vr is not None and abs(vr) > 8000:
        return False

    return True


def hdg53(msg):
    """Magnetic heading, BDS 5,3 message

    Args:
        msg (String): 28 bytes hexadecimal message (BDS53) string

    Returns:
        float: angle in degrees to true north (from 0 to 360)
    """
    d = hex2bin(data(msg))

    if d[0] == '0':
        return None

    sign = int(d[1])    # 1 -> west
    value = bin2int(d[2:12])

    if sign:
        value = value - 1024

    hdg = value * 90.0 / 512.0   # degree

    # convert from [-180, 180] to [0, 360]
    if hdg < 0:
        hdg = 360 + hdg

    return round(hdg, 3)


def ias53(msg):
    """Indicated airspeed, DBS 5,3 message

    Args:
        msg (String): 28 bytes hexadecimal message

    Returns:
        int: indicated arispeed in knots
    """
    d = hex2bin(data(msg))

    if d[12] == '0':
        return None

    ias = bin2int(d[13:23])    # knots
    return ias


def mach53(msg):
    """MACH number, DBS 5,3 message

    Args:
        msg (String): 28 bytes hexadecimal message

    Returns:
        float: MACH number
    """
    d = hex2bin(data(msg))

    if d[23] == '0':
        return None

    mach = bin2int(d[24:33]) * 0.008
    return round(mach, 3)


def tas53(msg):
    """Aircraft true airspeed, BDS 5,3 message

    Args:
        msg (String): 28 bytes hexadecimal message

    Returns:
        float: true airspeed in knots
    """
    d = hex2bin(data(msg))

    if d[33] == '0':
        return None

    tas = bin2int(d[34:46]) * 0.5   # kts
    return round(tas, 1)

def vr53(msg):
    """Vertical rate

    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string

    Returns:
        int: vertical rate in feet/minutes
    """
    d = hex2bin(data(msg))

    if d[46] == '0':
        return None

    sign = int(d[47])    # 1 -> negative value, two's complement
    value = bin2int(d[48:56])

    if value == 0 or value == 255:  # all zeros or all ones
        return 0

    value = value - 256 if sign else value
    roc = value * 64     # feet/min

    return roc
