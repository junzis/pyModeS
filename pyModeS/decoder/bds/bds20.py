# ------------------------------------------
# BDS 2,0
# Aircraft identification
# ------------------------------------------

from ... import common


def is20(msg: str) -> bool:
    """Check if a message is likely to be BDS code 2,0

    Args:
        msg (str): 28 hexdigits string

    Returns:
        bool: True or False
    """

    if common.allzeros(msg):
        return False

    d = common.hex2bin(common.data(msg))

    if d[0:8] != "00100000":
        return False

    # allow empty callsign
    if common.bin2int(d[8:56]) == 0:
        return True

    if "#" in cs20(msg):
        return False

    return True


def cs20(msg: str) -> str:
    """Aircraft callsign

    Args:
        msg (str): 28 hexdigits string

    Returns:
        string: callsign, max. 8 chars
    """
    chars = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ#####_###############0123456789######"

    d = common.hex2bin(common.data(msg))

    cs = ""
    cs += chars[common.bin2int(d[8:14])]
    cs += chars[common.bin2int(d[14:20])]
    cs += chars[common.bin2int(d[20:26])]
    cs += chars[common.bin2int(d[26:32])]
    cs += chars[common.bin2int(d[32:38])]
    cs += chars[common.bin2int(d[38:44])]
    cs += chars[common.bin2int(d[44:50])]
    cs += chars[common.bin2int(d[50:56])]

    return cs
