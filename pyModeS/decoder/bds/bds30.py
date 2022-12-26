# ------------------------------------------
# BDS 3,0
# ACAS active resolution advisory
# ------------------------------------------

from ... import common


def is30(msg: str) -> bool:
    """Check if a message is likely to be BDS code 3,0

    Args:
        msg (str): 28 hexdigits string

    Returns:
        bool: True or False
    """

    if common.allzeros(msg):
        return False

    d = common.hex2bin(common.data(msg))

    if d[0:8] != "00110000":
        return False

    # threat type 3 not assigned
    if d[28:30] == "11":
        return False

    # reserved for ACAS III, in far future
    if common.bin2int(d[15:22]) >= 48:
        return False

    return True
