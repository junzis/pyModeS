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
# BDS 4,5
# Meteorological hazard report
# ------------------------------------------

from __future__ import absolute_import, print_function, division
from pyModeS.decoder.common import hex2bin, bin2int, data, allzeros, wrongstatus


def is45(msg):
    """Check if a message is likely to be BDS code 4,5.

    Meteorological hazard report

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False

    """
    if allzeros(msg):
        return False

    d = hex2bin(data(msg))

    # status bit 1, 4, 7, 10, 13, 16, 27, 39
    if wrongstatus(d, 1, 2, 3):
        return False

    if wrongstatus(d, 4, 5, 6):
        return False

    if wrongstatus(d, 7, 8, 9):
        return False

    if wrongstatus(d, 10, 11, 12):
        return False

    if wrongstatus(d, 13, 14, 15):
        return False

    if wrongstatus(d, 16, 17, 26):
        return False

    if wrongstatus(d, 27, 28, 38):
        return False

    if wrongstatus(d, 39, 40, 51):
        return False

    # reserved
    if bin2int(d[51:56]) != 0:
        return False

    temp = temp45(msg)
    if temp:
        if temp > 60 or temp < -80:
            return False

    return True


def turb45(msg):
    """Turbulence.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: Turbulence level. 0=NIL, 1=Light, 2=Moderate, 3=Severe

    """
    d = hex2bin(data(msg))
    if d[0] == '0':
        return None

    turb = bin2int(d[1:3])
    return turb


def ws45(msg):
    """Wind shear.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: Wind shear level. 0=NIL, 1=Light, 2=Moderate, 3=Severe

    """
    d = hex2bin(data(msg))
    if d[3] == '0':
        return None

    ws = bin2int(d[4:6])
    return ws


def mb45(msg):
    """Microburst.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: Microburst level. 0=NIL, 1=Light, 2=Moderate, 3=Severe

    """
    d = hex2bin(data(msg))
    if d[6] == '0':
        return None

    mb = bin2int(d[7:9])
    return mb


def ic45(msg):
    """Icing.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: Icing level. 0=NIL, 1=Light, 2=Moderate, 3=Severe

    """
    d = hex2bin(data(msg))
    if d[9] == '0':
        return None

    ic = bin2int(d[10:12])
    return ic


def wv45(msg):
    """Wake vortex.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: Wake vortex level. 0=NIL, 1=Light, 2=Moderate, 3=Severe

    """
    d = hex2bin(data(msg))
    if d[12] == '0':
        return None

    ws = bin2int(d[13:15])
    return ws


def temp45(msg):
    """Static air temperature.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        float: tmeperature in Celsius degree

    """
    d = hex2bin(data(msg))

    sign = int(d[16])
    value = bin2int(d[17:26])

    if sign:
        value = value - 512

    temp = value * 0.25   # celsius
    temp = round(temp, 1)

    return temp


def p45(msg):
    """Average static pressure.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: static pressure in hPa

    """
    d = hex2bin(data(msg))
    if d[26] == '0':
        return None
    p = bin2int(d[27:38])    # hPa
    return p


def rh45(msg):
    """Radio height.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: radio height in ft

    """
    d = hex2bin(data(msg))
    if d[38] == '0':
        return None
    rh = bin2int(d[39:51]) * 16
    return rh
