# ------------------------------------------
#   BDS 0,8
#   ADS-B TC=1-4
#   Aircraft identification and category
# ------------------------------------------

from ... import common


def category(msg: str) -> int:
    """Aircraft category number

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: category number
    """

    tc = common.typecode(msg)
    if tc is None or tc < 1 or tc > 4:
        raise RuntimeError("%s: Not a identification message" % msg)

    msgbin = common.hex2bin(msg)
    mebin = msgbin[32:87]
    return common.bin2int(mebin[5:8])


def callsign(msg: str) -> str:
    """Aircraft callsign

    Args:
        msg (str): 28 hexdigits string

    Returns:
        string: callsign
    """
    tc = common.typecode(msg)

    if tc is None or tc < 1 or tc > 4:
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
