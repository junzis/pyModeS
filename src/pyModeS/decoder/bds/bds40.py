# ------------------------------------------
# BDS 4,0
# Selected vertical intention
# ------------------------------------------

import warnings
from typing import Optional

from ... import common


def is40(msg: str) -> bool:
    """Check if a message is likely to be BDS code 4,0

    Args:
        msg (str): 28 hexdigits string

    Returns:
        bool: True or False
    """

    if common.allzeros(msg):
        return False

    d = common.hex2bin(common.data(msg))

    # status bit 1, 14, and 27

    if common.wrongstatus(d, 1, 2, 13):
        return False

    if common.wrongstatus(d, 14, 15, 26):
        return False

    if common.wrongstatus(d, 27, 28, 39):
        return False

    if common.wrongstatus(d, 48, 49, 51):
        return False

    if common.wrongstatus(d, 54, 55, 56):
        return False

    # bits 40-47 and 52-53 shall all be zero

    if common.bin2int(d[39:47]) != 0:
        return False

    if common.bin2int(d[51:53]) != 0:
        return False

    return True


def selalt40mcp(msg: str) -> Optional[int]:
    """Selected altitude, MCP/FCU

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: altitude in feet
    """
    d = common.hex2bin(common.data(msg))

    if d[0] == "0":
        return None

    alt = common.bin2int(d[1:13]) * 16  # ft
    return alt


def selalt40fms(msg: str) -> Optional[int]:
    """Selected altitude, FMS

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: altitude in feet
    """
    d = common.hex2bin(common.data(msg))

    if d[13] == "0":
        return None

    alt = common.bin2int(d[14:26]) * 16  # ft
    return alt


def p40baro(msg: str) -> Optional[float]:
    """Barometric pressure setting

    Args:
        msg (str): 28 hexdigits string

    Returns:
        float: pressure in millibar
    """
    d = common.hex2bin(common.data(msg))

    if d[26] == "0":
        return None

    p = common.bin2int(d[27:39]) * 0.1 + 800  # millibar
    return p


def alt40mcp(msg: str) -> Optional[int]:
    warnings.warn(
        """alt40mcp() has been renamed to selalt40mcp().
        It will be removed in the future.""",
        DeprecationWarning,
    )
    return selalt40mcp(msg)


def alt40fms(msg: str) -> Optional[int]:
    warnings.warn(
        """alt40fms() has been renamed to selalt40fms().
        It will be removed in the future.""",
        DeprecationWarning,
    )
    return selalt40fms(msg)
