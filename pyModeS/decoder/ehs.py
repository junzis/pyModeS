"""EHS Wrapper.

``pyModeS.ehs`` is deprecated, please use ``pyModeS.commb`` instead.

The EHS wrapper imports all functions from the following modules:
    - pyModeS.decoder.bds.bds40
    - pyModeS.decoder.bds.bds50
    - pyModeS.decoder.bds.bds60

"""

import warnings

from .bds.bds40 import (
    is40,
    selalt40fms,
    selalt40mcp,
    p40baro,
    alt40fms,
    alt40mcp,
)
from .bds.bds50 import is50, roll50, trk50, gs50, rtrk50, tas50
from .bds.bds60 import is60, hdg60, ias60, mach60, vr60baro, vr60ins
from .bds import infer

__all__ = [
    "is40",
    "selalt40fms",
    "selalt40mcp",
    "p40baro",
    "alt40fms",
    "alt40mcp",
    "is50",
    "roll50",
    "trk50",
    "gs50",
    "rtrk50",
    "tas50",
    "is60",
    "hdg60",
    "ias60",
    "mach60",
    "vr60baro",
    "vr60ins",
    "infer",
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
