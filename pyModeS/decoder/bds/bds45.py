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

    Meteorological harzard report

    Args:
        msg (String): 28 bytes hexadecimal message string
        rev (bool): using revised version

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

    if wrongstatus(d, 17, 28, 38):
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


def temp45(msg):
    """Static air temperature.

    Args:
        msg (String): 28 bytes hexadecimal message (BDS44) string
        rev (bool): using revised version

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


def p44(msg, rev=False):
    """Average static pressure.

    Args:
        msg (String): 28 bytes hexadecimal message (BDS44) string
        rev (bool): using revised version

    Returns:
        int: static pressure in hPa

    """
    d = hex2bin(data(msg))
    p = bin2int(d[27:38])    # hPa
    return p
