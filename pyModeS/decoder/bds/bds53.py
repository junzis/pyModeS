# ------------------------------------------
# BDS 5,3
# Air-referenced state vector
# ------------------------------------------

from typing import Optional

from ... import common


def is53(msg: str) -> bool:
    """Check if a message is likely to be BDS code 5,3
    (Air-referenced state vector)

    Args:
        msg (str): 28 hexdigits string

    Returns:
        bool: True or False
    """

    if common.allzeros(msg):
        return False

    d = common.hex2bin(common.data(msg))

    # status bit 1, 13, 24, 34, 47

    if common.wrongstatus(d, 1, 3, 12):
        return False

    if common.wrongstatus(d, 13, 14, 23):
        return False

    if common.wrongstatus(d, 24, 25, 33):
        return False

    if common.wrongstatus(d, 34, 35, 46):
        return False

    if common.wrongstatus(d, 47, 49, 56):
        return False

    ias = ias53(msg)
    if ias is not None and ias > 500:
        return False

    mach = mach53(msg)
    if mach is not None and mach > 1:
        return False

    tas = tas53(msg)
    if tas is not None and tas > 500:
        return False

    vr = vr53(msg)
    if vr is not None and abs(vr) > 8000:
        return False

    return True


def hdg53(msg: str) -> Optional[float]:
    """Magnetic heading, BDS 5,3 message

    Args:
        msg (str): 28 hexdigits string

    Returns:
        float: angle in degrees to true north (from 0 to 360)
    """
    d = common.hex2bin(common.data(msg))

    if d[0] == "0":
        return None

    sign = int(d[1])  # 1 -> west
    value = common.bin2int(d[2:12])

    if sign:
        value = value - 1024

    hdg = value * 90 / 512  # degree

    # convert from [-180, 180] to [0, 360]
    if hdg < 0:
        hdg = 360 + hdg

    return round(hdg, 3)


def ias53(msg: str) -> Optional[float]:
    """Indicated airspeed, DBS 5,3 message

    Args:
        msg (str): 28 hexdigits

    Returns:
        int: indicated arispeed in knots
    """
    d = common.hex2bin(common.data(msg))

    if d[12] == "0":
        return None

    ias = common.bin2int(d[13:23])  # knots
    return ias


def mach53(msg: str) -> Optional[float]:
    """MACH number, DBS 5,3 message

    Args:
        msg (str): 28 hexdigits

    Returns:
        float: MACH number
    """
    d = common.hex2bin(common.data(msg))

    if d[23] == "0":
        return None

    mach = common.bin2int(d[24:33]) * 0.008
    return round(mach, 3)


def tas53(msg: str) -> Optional[float]:
    """Aircraft true airspeed, BDS 5,3 message

    Args:
        msg (str): 28 hexdigits

    Returns:
        float: true airspeed in knots
    """
    d = common.hex2bin(common.data(msg))

    if d[33] == "0":
        return None

    tas = common.bin2int(d[34:46]) * 0.5  # kts
    return round(tas, 1)


def vr53(msg: str) -> Optional[int]:
    """Vertical rate

    Args:
        msg (str): 28 hexdigits (BDS60) string

    Returns:
        int: vertical rate in feet/minutes
    """
    d = common.hex2bin(common.data(msg))

    if d[46] == "0":
        return None

    sign = int(d[47])  # 1 -> negative value, two's complement
    value = common.bin2int(d[48:56])

    if value == 0 or value == 255:  # all zeros or all ones
        return 0

    value = value - 256 if sign else value
    roc = value * 64  # feet/min

    return roc
