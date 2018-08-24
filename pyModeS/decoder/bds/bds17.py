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

"""
------------------------------------------
  BDS 1,7
  Common usage GICB capability report
------------------------------------------
"""

def is17(msg):
    """Check if a message is likely to be BDS code 1,7

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = hex2bin(data(msg))

    if bin2int(d[28:56]) != 0:
        return False

    caps = cap17(msg)

    # basic BDS codes for ADS-B shall be supported
    #   assuming ADS-B out is installed (2017EU/2020US mandate)
    # if not set(['BDS05', 'BDS06', 'BDS08', 'BDS09', 'BDS20']).issubset(caps):
    #     return False

    # at least you can respond who you are
    if 'BDS20' not in caps:
        return False

    return True

def cap17(msg):
    """Extract capacities from BDS 1,7 message

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        list: list of suport BDS codes
    """
    allbds = ['05', '06', '07', '08', '09', '0A', '20', '21', '40', '41',
              '42', '43', '44', '45', '48', '50', '51', '52', '53', '54',
              '55', '56', '5F', '60', 'NA', 'NA', 'E1', 'E2']

    d = hex2bin(data(msg))
    idx = [i for i, v in enumerate(d[:28]) if v=='1']
    capacity = ['BDS'+allbds[i] for i in idx if allbds[i] is not 'NA']

    return capacity
