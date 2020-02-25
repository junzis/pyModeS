# ------------------------------------------
# BDS 3,0
# ACAS active resolution advisory
# ------------------------------------------

from __future__ import absolute_import, print_function, division
from pyModeS.decoder.common import hex2bin, bin2int, data, allzeros


def is30(msg):
    """Check if a message is likely to be BDS code 2,0

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = hex2bin(data(msg))

    if d[0:8] != "00110000":
        return False

    # threat type 3 not assigned
    if d[28:30] == "11":
        return False

    # reserved for ACAS III, in far future
    if bin2int(d[15:22]) >= 48:
        return False

    return True
