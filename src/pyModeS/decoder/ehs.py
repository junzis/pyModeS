"""EHS Wrapper.

``pyModeS.ehs`` is deprecated, please use ``pyModeS.commb`` instead.

The EHS wrapper imports all functions from the following modules:
    - pyModeS.decoder.bds.bds40
    - pyModeS.decoder.bds.bds50
    - pyModeS.decoder.bds.bds60

"""

import warnings

from .bds import infer
from .bds.bds40 import (
    alt40fms,
    alt40mcp,
    is40,
    p40baro,
    selalt40fms,
    selalt40mcp,
)
from .bds.bds50 import gs50, is50, roll50, rtrk50, tas50, trk50
from .bds.bds60 import hdg60, ias60, is60, mach60, vr60baro, vr60ins

__all__ = [
    "alt40fms",
    "alt40mcp",
    "gs50",
    "hdg60",
    "ias60",
    "infer",
    "is40",
    "is50",
    "is60",
    "mach60",
    "p40baro",
    "roll50",
    "rtrk50",
    "selalt40fms",
    "selalt40mcp",
    "tas50",
    "trk50",
    "vr60baro",
    "vr60ins",
]

warnings.simplefilter("once", DeprecationWarning)
warnings.warn(
    "pms.ehs module is deprecated. Please use pms.commb instead.",
    DeprecationWarning,
)


def BDS(msg):
    warnings.warn(
        "pms.ehs.BDS() is deprecated, use pms.bds.infer() instead.",
        DeprecationWarning,
    )
    return infer(msg)


def icao(msg):
    from . import common

    return common.icao(msg)
