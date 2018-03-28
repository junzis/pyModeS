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
  BDS 0,8
  ADS-B TC=1-4
  Aircraft identitification and category
------------------------------------------
"""

from __future__ import absolute_import, print_function, division
from pyModeS.decoder import common

def category(msg):
    """Aircraft category number

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: category number
    """

    if common.typecode(msg) < 1 or common.typecode(msg) > 4:
        raise RuntimeError("%s: Not a identification message" % msg)

    msgbin = common.hex2bin(msg)
    return common.bin2int(msgbin[5:8])


def callsign(msg):
    """Aircraft callsign

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        string: callsign
    """

    if common.typecode(msg) < 1 or common.typecode(msg) > 4:
        raise RuntimeError("%s: Not a identification message" % msg)

    chars = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ#####_###############0123456789######'
    msgbin = common.hex2bin(msg)
    csbin = msgbin[40:96]

    cs = ''
    cs += chars[common.bin2int(csbin[0:6])]
    cs += chars[common.bin2int(csbin[6:12])]
    cs += chars[common.bin2int(csbin[12:18])]
    cs += chars[common.bin2int(csbin[18:24])]
    cs += chars[common.bin2int(csbin[24:30])]
    cs += chars[common.bin2int(csbin[30:36])]
    cs += chars[common.bin2int(csbin[36:42])]
    cs += chars[common.bin2int(csbin[42:48])]

    # clean string, remove spaces and marks, if any.
    # cs = cs.replace('_', '')
    cs = cs.replace('#', '')
    return cs
