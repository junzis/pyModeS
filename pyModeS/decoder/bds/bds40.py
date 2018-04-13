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
# BDS 4,0
# Selected vertical intention
# ------------------------------------------

def is40(msg):
    """Check if a message is likely to be BDS code 4,0

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = hex2bin(data(msg))

    # status bit 1, 14, and 27

    if wrongstatus(d, 1, 2, 13):
        return False

    if wrongstatus(d, 14, 15, 26):
        return False

    if wrongstatus(d, 27, 28, 39):
        return False
    
    if wrongstatus(d, 48, 49, 51):
        return False
    
    if wrongstatus(d, 54, 55, 56):
        return False

    # bits 40-47 and 52-53 shall all be zero

    if bin2int(d[39:47]) != 0:
        return False

    if bin2int(d[51:53]) != 0:
        return False

    return True


def alt40mcp(msg):
    """Selected altitude, MCP/FCU

    Args:
        msg (String): 28 bytes hexadecimal message (BDS40) string

    Returns:
        int: altitude in feet
    """
    d = hex2bin(data(msg))

    if d[0] == '0':
        return None

    alt = bin2int(d[1:13]) * 16    # ft
    return alt


def alt40fms(msg):
    """Selected altitude, FMS

    Args:
        msg (String): 28 bytes hexadecimal message (BDS40) string

    Returns:
        int: altitude in feet
    """
    d = hex2bin(data(msg))

    if d[13] == '0':
        return None

    alt = bin2int(d[14:26]) * 16    # ft
    return alt


def p40baro(msg):
    """Barometric pressure setting

    Args:
        msg (String): 28 bytes hexadecimal message (BDS40) string

    Returns:
        float: pressure in millibar
    """
    d = hex2bin(data(msg))

    if d[26] == '0':
        return None

    p = bin2int(d[27:39]) * 0.1 + 800    # millibar
    return p
