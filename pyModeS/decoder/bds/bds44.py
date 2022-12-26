# ------------------------------------------
# BDS 4,4
# Meteorological routine air report
# ------------------------------------------

from typing import Optional, Tuple

from ... import common


def is44(msg: str) -> bool:
    """Check if a message is likely to be BDS code 4,4.

    Meteorological routine air report

    Args:
        msg (str): 28 hexdigits string

    Returns:
        bool: True or False

    """
    if common.allzeros(msg):
        return False

    d = common.hex2bin(common.data(msg))

    # status bit 5, 35, 47, 50
    if common.wrongstatus(d, 5, 6, 23):
        return False

    if common.wrongstatus(d, 35, 36, 46):
        return False

    if common.wrongstatus(d, 47, 48, 49):
        return False

    if common.wrongstatus(d, 50, 51, 56):
        return False

    # Bits 1-4 indicate source, values > 4 reserved and should not occur
    if common.bin2int(d[0:4]) > 4:
        return False

    vw, dw = wind44(msg)
    if vw is not None and vw > 250:
        return False

    temp, temp2 = temp44(msg)
    if min(temp, temp2) > 60 or max(temp, temp2) < -80:
        return False

    return True


def wind44(msg: str) -> Tuple[Optional[int], Optional[float]]:
    """Wind speed and direction.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        (int, float): speed (kt), direction (degree)

    """
    d = common.hex2bin(common.data(msg))

    status = int(d[4])
    if not status:
        return None, None

    speed = common.bin2int(d[5:14])  # knots
    direction = common.bin2int(d[14:23]) * 180 / 256  # degree

    return round(speed, 0), round(direction, 1)


def temp44(msg: str) -> Tuple[float, float]:
    """Static air temperature.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        float, float: temperature and alternative temperature in Celsius degree.
            Note: Two values returns due to what seems to be an inconsistency
            error in ICAO 9871 (2008) Appendix A-67.

    """
    d = common.hex2bin(common.data(msg))

    sign = int(d[23])
    value = common.bin2int(d[24:34])

    if sign:
        value = value - 1024

    temp = value * 0.25  # celsius
    temp = round(temp, 2)

    temp_alternative = value * 0.125  # celsius
    temp_alternative = round(temp_alternative, 3)

    return temp, temp_alternative


def p44(msg: str) -> Optional[int]:
    """Static pressure.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: static pressure in hPa

    """
    d = common.hex2bin(common.data(msg))

    if d[34] == "0":
        return None

    p = common.bin2int(d[35:46])  # hPa

    return p


def hum44(msg: str) -> Optional[float]:
    """humidity

    Args:
        msg (str): 28 hexdigits string

    Returns:
        float: percentage of humidity, [0 - 100] %
    """
    d = common.hex2bin(common.data(msg))

    if d[49] == "0":
        return None

    hm = common.bin2int(d[50:56]) * 100 / 64  # %

    return round(hm, 1)


def turb44(msg: str) -> Optional[int]:
    """Turbulence.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: turbulence level. 0=NIL, 1=Light, 2=Moderate, 3=Severe

    """
    d = common.hex2bin(common.data(msg))

    if d[46] == "0":
        return None

    turb = common.bin2int(d[47:49])

    return turb
