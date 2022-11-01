"""
Decode all-call reply messages, with downlink format 11
"""


from __future__ import annotations
from typing import Callable, TypeVar

from .. import common

T = TypeVar("T")
F = Callable[[str], T]


def _checkdf(func: F[T]) -> F[T]:

    """Ensure downlink format is 11."""

    def wrapper(msg: str) -> T:
        df = common.df(msg)
        if df != 11:
            raise RuntimeError(
                "Incorrect downlink format, expect 11, got {}".format(df)
            )
        return func(msg)

    return wrapper


@_checkdf
def icao(msg: str) -> None | str:
    """Decode transponder code (ICAO address).

    Args:
        msg (str): 14 hexdigits string
    Returns:
        string: ICAO address

    """
    return common.icao(msg)


@_checkdf
def interrogator(msg: str) -> str:
    """Decode interrogator identifier code.

    Args:
        msg (str): 14 hexdigits string
    Returns:
        int: interrogator identifier code

    """
    # the CRC remainder contains the CL and IC field.
    # the top three bits are CL field and last four bits are IC field.
    remainder = common.crc(msg)
    if remainder > 79:
        IC = "corrupt IC"
    elif remainder < 16:
        IC = "II" + str(remainder)
    else:
        IC = "SI" + str(remainder - 16)
    return IC


@_checkdf
def capability(msg: str) -> tuple[int, None | str]:
    """Decode transponder capability.

    Args:
        msg (str): 14 hexdigits string
    Returns:
        int, str: transponder capability, description

    """
    msgbin = common.hex2bin(msg)
    ca = common.bin2int(msgbin[5:8])

    if ca == 0:
        text = "level 1 transponder"
    elif ca == 4:
        text = "level 2 transponder, ability to set CA to 7, on ground"
    elif ca == 5:
        text = "level 2 transponder, ability to set CA to 7, airborne"
    elif ca == 6:
        text = (
            "evel 2 transponder, ability to set CA to 7, "
            "either airborne or ground"
        )
    elif ca == 7:
        text = (
            "Downlink Request value is 0, "
            "or the Flight Status is 2, 3, 4 or 5, "
            "either airborne or on the ground"
        )
    else:
        text = None

    return ca, text
