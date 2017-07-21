from __future__ import absolute_import, print_function, division
from . import util, modes_common

def icao(msg):
    return modes_common.icao(msg)


def df4alt(msg):
    """Computes the altitude from DF4 message, bit 20-32

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: altitude in ft
    """

    if util.df(msg) != 4:
        raise RuntimeError("Message must be Downlink Format 4.")

    return modes_common.altcode(msg)


def df5id(msg):
    """Computes identity (squawk code) from DF5 message, bit 20-32

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        string: squawk code
    """

    if util.df(msg) != 5:
        raise RuntimeError("Message must be Downlink Format 5.")

    return modes_common.idcode(msg)
