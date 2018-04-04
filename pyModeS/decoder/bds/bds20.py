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
from pyModeS.decoder.common import hex2bin, bin2int, data, allzeros

# ------------------------------------------
# BDS 2,0
# Aircraft identification
# ------------------------------------------

def is20(msg):
    """Check if a message is likely to be BDS code 2,0

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = hex2bin(data(msg))

    if d[0:8] != '00100000':
        return False

    cs = cs20(msg)

    if '#' in cs:
        return False

    return True


def cs20(msg):
    """Aircraft callsign

    Args:
        msg (String): 28 bytes hexadecimal message (BDS40) string

    Returns:
        string: callsign, max. 8 chars
    """
    chars = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ#####_###############0123456789######'

    d = hex2bin(data(msg))

    cs = ''
    cs += chars[bin2int(d[8:14])]
    cs += chars[bin2int(d[14:20])]
    cs += chars[bin2int(d[20:26])]
    cs += chars[bin2int(d[26:32])]
    cs += chars[bin2int(d[32:38])]
    cs += chars[bin2int(d[38:44])]
    cs += chars[bin2int(d[44:50])]
    cs += chars[bin2int(d[50:56])]

    return cs
