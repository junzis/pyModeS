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
# BDS 6,0
# Heading and speed report
# ------------------------------------------

def is60(msg):
    """Check if a message is likely to be BDS code 6,0

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = hex2bin(data(msg))

    # status bit 1, 13, 24, 35, 46

    if wrongstatus(d, 1, 2, 12):
        return False

    if wrongstatus(d, 13, 14, 23):
        return False

    if wrongstatus(d, 24, 25, 34):
        return False

    if wrongstatus(d, 35, 36, 45):
        return False

    if wrongstatus(d, 46, 47, 56):
        return False

    ias = ias60(msg)
    if ias is not None and ias > 500:
        return False

    mach = mach60(msg)
    if mach is not None and mach > 1:
        return False

    vr_baro = vr60baro(msg)
    if vr_baro is not None and abs(vr_baro) > 6000:
        return False

    vr_ins = vr60ins(msg)
    if vr_ins is not None and abs(vr_ins) > 6000:
        return False

    return True


def hdg60(msg):
    """Megnetic heading of aircraft

    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string

    Returns:
        float: heading in degrees to megnetic north (from 0 to 360)
    """
    d = hex2bin(data(msg))

    if d[0] == '0':
        return None

    sign = int(d[1])    # 1 -> west
    value = bin2int(d[2:12])

    if sign:
        value = value - 1024

    hdg = value * 90 / 512.0  # degree

    # convert from [-180, 180] to [0, 360]
    if hdg < 0:
        hdg = 360 + hdg

    return round(hdg, 3)


def ias60(msg):
    """Indicated airspeed

    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string

    Returns:
        int: indicated airspeed in knots
    """
    d = hex2bin(data(msg))

    if d[12] == '0':
        return None

    ias = bin2int(d[13:23])    # kts
    return ias


def mach60(msg):
    """Aircraft MACH number

    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string

    Returns:
        float: MACH number
    """
    d = hex2bin(data(msg))

    if d[23] == '0':
        return None

    mach = bin2int(d[24:34]) * 2.048 / 512.0
    return round(mach, 3)


def vr60baro(msg):
    """Vertical rate from barometric measurement, this value may be very noisy.

    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string

    Returns:
        int: vertical rate in feet/minutes
    """
    d = hex2bin(data(msg))

    if d[34] == '0':
        return None

    sign = int(d[35])    # 1 -> negative value, two's complement
    value = bin2int(d[36:45])

    if value == 0 or value == 511:  # all zeros or all ones
        return 0

    value = value - 512 if sign else value

    roc = value * 32   # feet/min
    return roc


def vr60ins(msg):
    """Vertical rate messured by onbard equiments (IRS, AHRS)

    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string

    Returns:
        int: vertical rate in feet/minutes
    """
    d = hex2bin(data(msg))

    if d[45] == '0':
        return None

    sign = int(d[46])    # 1 -> negative value, two's complement
    value = bin2int(d[47:56])

    if value == 0 or value == 511:  # all zeros or all ones
        return 0

    value = value - 512 if sign else value

    roc = value * 32   # feet/min
    return roc
