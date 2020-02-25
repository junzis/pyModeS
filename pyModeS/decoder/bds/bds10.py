# ------------------------------------------
# BDS 1,0
# Data link capability report
# ------------------------------------------

from __future__ import absolute_import, print_function, division

from pyModeS import common


def is10(msg):
    """Check if a message is likely to be BDS code 1,0

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if common.allzeros(msg):
        return False

    d = common.hex2bin(common.data(msg))

    # first 8 bits must be 0x10
    if d[0:8] != "00010000":
        return False

    # bit 10 to 14 are reserved
    if common.bin2int(d[9:14]) != 0:
        return False

    # overlay capability conflict
    if d[14] == "1" and common.bin2int(d[16:23]) < 5:
        return False
    if d[14] == "0" and common.bin2int(d[16:23]) > 4:
        return False

    return True


def ovc10(msg):
    """Return the overlay control capability

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: Whether the transponder is OVC capable
    """
    d = common.hex2bin(common.data(msg))

    return int(d[14])
