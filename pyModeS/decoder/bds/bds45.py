# ------------------------------------------
# BDS 4,5
# Meteorological hazard report
# ------------------------------------------

from typing import Optional

from ... import common


def is45(msg: str) -> bool:
    """Check if a message is likely to be BDS code 4,5.

    Meteorological hazard report

    Args:
        msg (str): 28 hexdigits string

    Returns:
        bool: True or False

    """
    if common.allzeros(msg):
        return False

    d = common.hex2bin(common.data(msg))

    # status bit 1, 4, 7, 10, 13, 16, 27, 39
    if common.wrongstatus(d, 1, 2, 3):
        return False

    if common.wrongstatus(d, 4, 5, 6):
        return False

    if common.wrongstatus(d, 7, 8, 9):
        return False

    if common.wrongstatus(d, 10, 11, 12):
        return False

    if common.wrongstatus(d, 13, 14, 15):
        return False

    if common.wrongstatus(d, 16, 17, 26):
        return False

    if common.wrongstatus(d, 27, 28, 38):
        return False

    if common.wrongstatus(d, 39, 40, 51):
        return False

    # reserved
    if common.bin2int(d[51:56]) != 0:
        return False

    temp = temp45(msg)
    if temp:
        if temp > 60 or temp < -80:
            return False

    return True


def turb45(msg: str) -> Optional[int]:
    """Turbulence.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: Turbulence level. 0=NIL, 1=Light, 2=Moderate, 3=Severe

    """
    d = common.hex2bin(common.data(msg))
    if d[0] == "0":
        return None

    turb = common.bin2int(d[1:3])
    return turb


def ws45(msg: str) -> Optional[int]:
    """Wind shear.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: Wind shear level. 0=NIL, 1=Light, 2=Moderate, 3=Severe

    """
    d = common.hex2bin(common.data(msg))
    if d[3] == "0":
        return None

    ws = common.bin2int(d[4:6])
    return ws


def mb45(msg: str) -> Optional[int]:
    """Microburst.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: Microburst level. 0=NIL, 1=Light, 2=Moderate, 3=Severe

    """
    d = common.hex2bin(common.data(msg))
    if d[6] == "0":
        return None

    mb = common.bin2int(d[7:9])
    return mb


def ic45(msg: str) -> Optional[int]:
    """Icing.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: Icing level. 0=NIL, 1=Light, 2=Moderate, 3=Severe

    """
    d = common.hex2bin(common.data(msg))
    if d[9] == "0":
        return None

    ic = common.bin2int(d[10:12])
    return ic


def wv45(msg: str) -> Optional[int]:
    """Wake vortex.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: Wake vortex level. 0=NIL, 1=Light, 2=Moderate, 3=Severe

    """
    d = common.hex2bin(common.data(msg))
    if d[12] == "0":
        return None

    ws = common.bin2int(d[13:15])
    return ws


def temp45(msg: str) -> Optional[float]:
    """Static air temperature.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        float: tmeperature in Celsius degree

    """
    d = common.hex2bin(common.data(msg))

    sign = int(d[16])
    value = common.bin2int(d[17:26])

    if sign:
        value = value - 512

    temp = value * 0.25  # celsius
    temp = round(temp, 1)

    return temp


def p45(msg: str) -> Optional[int]:
    """Average static pressure.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: static pressure in hPa

    """
    d = common.hex2bin(common.data(msg))
    if d[26] == "0":
        return None
    p = common.bin2int(d[27:38])  # hPa
    return p


def rh45(msg: str) -> Optional[int]:
    """Radio height.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: radio height in ft

    """
    d = common.hex2bin(common.data(msg))
    if d[38] == "0":
        return None
    rh = common.bin2int(d[39:51]) * 16
    return rh
