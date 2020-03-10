# ------------------------------------------
#   BDS 0,8
#   ADS-B TC=1-4
#   Aircraft identitification and category
# ------------------------------------------

from __future__ import absolute_import, print_function, division

from binascii import hexlify
from functools import singledispatch

from pyModeS import common


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
    mebin = msgbin[32:87]
    return common.bin2int(mebin[5:8])


@singledispatch
def callsign(msg):
    """Aircraft callsign

    Args:
        msg (string or bytes): 28 bytes hexadecimal message string or 14 bytes

    Returns:
        string: callsign
    """
    raise ValueError('Unknown message type: {}'.format(type(msg)))

@callsign.register
def _callsign_str(msg: bytes):
    return _callsign_str(hexlify(msg))

@callsign.register
def _callsign_str(msg: str):
    if common.typecode(msg) < 1 or common.typecode(msg) > 4:
        raise RuntimeError("%s: Not a identification message" % msg)

    chars = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ#####_###############0123456789######"
    msgbin = common.hex2bin(msg)
    csbin = msgbin[40:96]

    cs = ""
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
    cs = cs.replace("#", "")
    return cs
