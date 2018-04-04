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
# BDS 5,0
# Track and turn report
# ------------------------------------------

def is50(msg):
    """Check if a message is likely to be BDS code 5,0
    (Track and turn report)

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = hex2bin(data(msg))

    # status bit 1, 12, 24, 35, 46

    if wrongstatus(d, 1, 3, 11):
        return False

    if wrongstatus(d, 12, 13, 23):
        return False

    if wrongstatus(d, 24, 25, 34):
        return False

    if wrongstatus(d, 35, 36, 45):
        return False

    if wrongstatus(d, 46, 47, 56):
        return False

    roll = roll50(msg)
    if (roll is not None) and abs(roll) > 60:
        return False

    gs = gs50(msg)
    if gs is not None and gs > 600:
        return False

    tas = tas50(msg)
    if tas is not None and tas > 500:
        return False

    if (gs is not None) and (tas is not None) and (abs(tas - gs) > 200):
        return False

    return True


def roll50(msg):
    """Roll angle, BDS 5,0 message

    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string

    Returns:
        float: angle in degrees,
               negative->left wing down, positive->right wing down
    """
    d = hex2bin(data(msg))

    if d[0] == '0':
        return None

    sign = int(d[1])    # 1 -> left wing down
    value = bin2int(d[2:11])

    if sign:
        value = value - 512

    angle = value * 45.0 / 256.0    # degree
    return round(angle, 1)


def trk50(msg):
    """True track angle, BDS 5,0 message

    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string

    Returns:
        float: angle in degrees to true north (from 0 to 360)
    """
    d = hex2bin(data(msg))

    if d[11] == '0':
        return None

    sign = int(d[12])   # 1 -> west
    value = bin2int(d[13:23])

    if sign:
        value = value - 1024

    trk = value * 90.0 / 512.0

    # convert from [-180, 180] to [0, 360]
    if trk < 0:
        trk = 360 + trk

    return round(trk, 3)


def gs50(msg):
    """Ground speed, BDS 5,0 message

    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string

    Returns:
        int: ground speed in knots
    """
    d = hex2bin(data(msg))

    if d[23] == '0':
        return None

    spd = bin2int(d[24:34]) * 2    # kts
    return spd


def rtrk50(msg):
    """Track angle rate, BDS 5,0 message

    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string

    Returns:
        float: angle rate in degrees/second
    """
    d = hex2bin(data(msg))

    if d[34] == '0':
        return None

    if d[36:45] == "111111111":
        return None

    sign = int(d[35])    # 1 -> negative value, two's complement
    value = bin2int(d[36:45])
    if sign:
        value = value - 512

    angle = value * 8.0 / 256.0    # degree / sec
    return round(angle, 3)


def tas50(msg):
    """Aircraft true airspeed, BDS 5,0 message

    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string

    Returns:
        int: true airspeed in knots
    """
    d = hex2bin(data(msg))

    if d[45] == '0':
        return None

    tas = bin2int(d[46:56]) * 2   # kts
    return tas
