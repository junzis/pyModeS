"""
Decode short roll call surveillance replies, with downlink format 4 or 5
"""

from __future__ import annotations
from typing import Callable, TypeVar

from .. import common

T = TypeVar("T")
F = Callable[[str], T]


def _checkdf(func: F[T]) -> F[T]:
    """Ensure downlink format is 4 or 5."""

    def wrapper(msg: str) -> T:
        df = common.df(msg)
        if df not in [4, 5]:
            raise RuntimeError(
                "Incorrect downlink format, expect 4 or 5, got {}".format(df)
            )
        return func(msg)

    return wrapper


@_checkdf
def fs(msg: str) -> tuple[int, str]:
    """Decode flight status.

    Args:
        msg (str): 14 hexdigits string
    Returns:
        int, str: flight status, description

    """
    msgbin = common.hex2bin(msg)
    fs = common.bin2int(msgbin[5:8])
    text = ""

    if fs == 0:
        text = "no alert, no SPI, aircraft is airborne"
    elif fs == 1:
        text = "no alert, no SPI, aircraft is on-ground"
    elif fs == 2:
        text = "alert, no SPI, aircraft is airborne"
    elif fs == 3:
        text = "alert, no SPI, aircraft is on-ground"
    elif fs == 4:
        text = "alert, SPI, aircraft is airborne or on-ground"
    elif fs == 5:
        text = "no alert, SPI, aircraft is airborne or on-ground"

    return fs, text


@_checkdf
def dr(msg: str) -> tuple[int, str]:
    """Decode downlink request.

    Args:
        msg (str): 14 hexdigits string
    Returns:
        int, str: downlink request, description

    """
    msgbin = common.hex2bin(msg)
    dr = common.bin2int(msgbin[8:13])

    text = ""

    if dr == 0:
        text = "no downlink request"
    elif dr == 1:
        text = "request to send Comm-B message"
    elif dr == 4:
        text = "Comm-B broadcast 1 available"
    elif dr == 5:
        text = "Comm-B broadcast 2 available"
    elif dr >= 16:
        text = "ELM downlink segments available: {}".format(dr - 15)

    return dr, text


@_checkdf
def um(msg: str) -> tuple[int, int, None | str]:
    """Decode utility message.

    Utility message contains interrogator identifier and reservation type.

    Args:
        msg (str): 14 hexdigits string
    Returns:
        int, str: interrogator identifier code that triggered the reply, and
        reservation type made by the interrogator
    """
    msgbin = common.hex2bin(msg)
    iis = common.bin2int(msgbin[13:17])
    ids = common.bin2int(msgbin[17:19])
    if ids == 0:
        ids_text = None
    if ids == 1:
        ids_text = "Comm-B interrogator identifier code"
    if ids == 2:
        ids_text = "Comm-C interrogator identifier code"
    if ids == 3:
        ids_text = "Comm-D interrogator identifier code"
    return iis, ids, ids_text


@_checkdf
def altitude(msg: str) -> None | int:
    """Decode altitude.

    Args:
        msg (String): 14 hexdigits string

    Returns:
        int: altitude in ft

    """
    return common.altcode(msg)


@_checkdf
def identity(msg: str) -> str:
    """Decode squawk code.

    Args:
        msg (String): 14 hexdigits string

    Returns:
        string: squawk code

    """
    return common.idcode(msg)
