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
# BDS 4,4
# Meteorological routine air report
# ------------------------------------------

def is44(msg, rev=False):
    """Check if a message is likely to be BDS code 4,4
    Meteorological routine air report

    Args:
        msg (String): 28 bytes hexadecimal message string
        rev (bool): using revised version

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = hex2bin(data(msg))


    if not rev:
        # status bit 5, 35, 47, 50
        if wrongstatus(d, 5, 6, 23):
            return False

        if wrongstatus(d, 35, 36, 46):
            return False

        if wrongstatus(d, 47, 48, 49):
            return False

        if wrongstatus(d, 50, 51, 56):
            return False

        # Bits 1-4 indicate source, values > 4 reserved and should not occur
        if bin2int(d[0:4]) > 4:
            return False
    else:
        # status bit 5, 15, 24, 36, 49
        if wrongstatus(d, 5, 6, 14):
            return False

        if wrongstatus(d, 15, 16, 23):
            return False

        if wrongstatus(d, 24, 25, 35):
            return False

        if wrongstatus(d, 36, 37, 47):
            return False

        if wrongstatus(d, 49, 50, 56):
            return False

        # Bits 1-4 are reserved and should be zero
        if bin2int(d[0:4]) != 0:
            return False

    vw = wind44(msg, rev=rev)
    if vw is not None and vw[0] > 250:
        return False

    if temp44(msg):
        if temp44(msg) > 60 or temp44(msg) < -80:
            return False

    elif temp44(msg) == 0:
        return False

    return True


def wind44(msg, rev=False):
    """reported wind speed and direction

    Args:
        msg (String): 28 bytes hexadecimal message (BDS44) string
        rev (bool): using revised version

    Returns:
        (int, float): speed (kt), direction (degree)
    """
    d = hex2bin(data(msg))

    if not rev:
        status = int(d[4])
        if not status:
            return None

        speed = bin2int(d[5:14])   # knots
        direction = bin2int(d[14:23]) * 180.0 / 256.0  # degree

    else:
        spd_status = int(d[4])
        dir_status = int(d[14])

        if (not spd_status) or (not dir_status):
            return None

        speed = bin2int(d[5:14])   # knots
        direction = bin2int(d[15:23]) * 180.0 / 128.0  # degree

    return round(speed, 0), round(direction, 1)


def temp44(msg, rev=False):
    """reported air temperature

    Args:
        msg (String): 28 bytes hexadecimal message (BDS44) string
        rev (bool): using revised version

    Returns:
        float: tmeperature in Celsius degree
    """
    d = hex2bin(data(msg))

    if not rev:
        # if d[22] == '0':
        #     return None

        sign = int(d[23])
        value = bin2int(d[24:34])

        if sign:
            value = value - 1024

        temp = value * 0.125   # celsius
        temp = round(temp, 1)
    else:
        # if d[23] == '0':
        #     return None

        sign = int(d[24])
        value = bin2int(d[25:35])

        if sign:
            value = value - 1024

        temp = value * 0.125   # celsius
        temp = round(temp, 1)

    return temp


def p44(msg, rev=False):
    """reported average static pressure

    Args:
        msg (String): 28 bytes hexadecimal message (BDS44) string
        rev (bool): using revised version

    Returns:
        int: static pressure in hPa
    """
    d = hex2bin(data(msg))

    if not rev:
        if d[34] == '0':
            return None

        p = bin2int(d[35:46])    # hPa

    else:
        if d[35] == '0':
            return None

        p = bin2int(d[36:47])    # hPa

    return p


def hum44(msg, rev=False):
    """reported humidity

    Args:
        msg (String): 28 bytes hexadecimal message (BDS44) string
        rev (bool): using revised version

    Returns:
        float: percentage of humidity, [0 - 100] %
    """
    d = hex2bin(data(msg))

    if not rev:
        if d[49] == '0':
            return None

        hm = bin2int(d[50:56]) * 100.0 / 64    # %

    else:
        if d[48] == '0':
            return None

        hm = bin2int(d[49:56])    # %

    return round(hm, 1)
