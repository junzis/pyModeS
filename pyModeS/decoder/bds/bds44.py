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
# BDS 4,4
# Meteorological routine air report
# ------------------------------------------

from __future__ import absolute_import, print_function, division
from pyModeS.decoder.common import hex2bin, bin2int, data, allzeros, wrongstatus


def is44(msg):
    """Check if a message is likely to be BDS code 4,4.

    Meteorological routine air report

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False

    """
    if allzeros(msg):
        return False

    d = hex2bin(data(msg))

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

    vw = wind44(msg)
    if vw is not None and vw[0] > 250:
        return False

    temp, temp2 = temp44(msg)
    if min(temp, temp2) > 60 or max(temp, temp2) < -80:
        return False

    return True


def wind44(msg):
    """Wind speed and direction.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        (int, float): speed (kt), direction (degree)

    """
    d = hex2bin(data(msg))

    status = int(d[4])
    if not status:
        return None

    speed = bin2int(d[5:14])   # knots
    direction = bin2int(d[14:23]) * 180.0 / 256.0  # degree

    return round(speed, 0), round(direction, 1)


def temp44(msg):
    """Static air temperature.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        float, float: temperature and alternative temperature in Celsius degree.
            Note: Two values returns due to what seems to be an inconsistancy
            error in ICAO 9871 (2008) Appendix A-67.

    """
    d = hex2bin(data(msg))

    sign = int(d[23])
    value = bin2int(d[24:34])

    if sign:
        value = value - 1024

    temp = value * 0.25   # celsius
    temp = round(temp, 2)

    temp_alternative = value * 0.125   # celsius
    temp_alternative = round(temp, 3)

    return temp, temp_alternative


def p44(msg):
    """Static pressure.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: static pressure in hPa

    """
    d = hex2bin(data(msg))

    if d[34] == '0':
        return None

    p = bin2int(d[35:46])    # hPa

    return p


def hum44(msg):
    """humidity

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        float: percentage of humidity, [0 - 100] %
    """
    d = hex2bin(data(msg))

    if d[49] == '0':
        return None

    hm = bin2int(d[50:56]) * 100.0 / 64    # %

    return round(hm, 1)


def turb44(msg):
    """Turblence.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: turbulence level. 0=NIL, 1=Light, 2=Moderate, 3=Severe

    """
    d = hex2bin(data(msg))

    if d[46] == '0':
        return None

    turb = bin2int(d[47:49])

    return turb
