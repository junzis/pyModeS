"""
Decode short roll call surveillance replies, with downlink format 4 or 5
"""

from pyModeS import common
from pyModeS.py_common import fs, dr, um


def _checkdf(func):
    """Ensure downlink format is 4 or 5."""

    def wrapper(msg):
        df = common.df(msg)
        if df not in [4, 5]:
            raise RuntimeError(
                "Incorrect downlink format, expect 4 or 5, got {}".format(df)
            )
        return func(msg)

    return wrapper


@_checkdf
def altitude(msg):
    """Decode altitude.

    Args:
        msg (String): 14 hexdigits string

    Returns:
        int: altitude in ft

    """
    return common.altcode(msg)


@_checkdf
def identity(msg):
    """Decode squawk code.

    Args:
        msg (String): 14 hexdigits string

    Returns:
        string: squawk code

    """
    return common.idcode(msg)
