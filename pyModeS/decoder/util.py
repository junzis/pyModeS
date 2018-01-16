# Copyright (C) 2015 Junzi Sun (TU Delft)

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
Common functions for ADS-B and Mode-S EHS decoder
"""


import numpy as np


def hex2bin(hexstr):
    """Convert a hexdecimal string to binary string, with zero fillings. """
    num_of_bits = len(hexstr) * 4
    binstr = bin(int(hexstr, 16))[2:].zfill(int(num_of_bits))
    return binstr


def bin2int(binstr):
    """Convert a binary string to integer. """
    return int(binstr, 2)


def hex2int(hexstr):
    """Convert a hexdecimal string to integer. """
    return int(hexstr, 16)


def bin2np(binstr):
    """Convert a binary string to numpy array. """
    return np.fromstring(binstr, 'u1') - ord('0')


def np2bin(npbin):
    """Convert a binary numpy array to string. """
    return np.array2string(npbin, separator='')[1:-1]


def df(msg):
    """Decode Downlink Format vaule, bits 1 to 5."""
    msgbin = hex2bin(msg)
    return bin2int(msgbin[0:5])


def crc(msg, encode=False):
    """Mode-S Cyclic Redundancy Check
    Detect if bit error occurs in the Mode-S message
    Args:
        msg (string): 28 bytes hexadecimal message string
        encode (bool): True to encode the date only and return the checksum
    Returns:
        string: message checksum, or partity bits (encoder)
    """

    # the polynominal generattor code for CRC [1111111111111010000001001]
    generator = np.array([1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,0,0,0,0,0,0,1,0,0,1])
    ng = len(generator)

    msgnpbin = bin2np(hex2bin(msg))

    if encode:
        msgnpbin[-24:] = [0] * 24

    # loop all bits, except last 24 piraty bits
    for i in range(len(msgnpbin)-24):
        if msgnpbin[i] == 0:
            continue

        # perform XOR, when 1
        msgnpbin[i:i+ng] = np.bitwise_xor(msgnpbin[i:i+ng], generator)

    # last 24 bits
    reminder = np2bin(msgnpbin[-24:])
    return reminder


def floor(x):
    """ Mode-S floor function

        Defined as the greatest integer value k, such that k <= x

        eg.: floor(3.6) = 3, while floor(-3.6) = -4
    """
    return int(np.floor(x))


def gray2int(graystr):
    """Convert greycode to binary (DF4, 20 altitude coding)"""
    num = bin2int(graystr)
    num ^= (num >> 8)
    num ^= (num >> 4)
    num ^= (num >> 2)
    num ^= (num >> 1)
    return num
