"""Comm-B module.

The Comm-B module imports all functions from the following modules:

ELS - elementary surveillance

- pyModeS.decoder.bds.bds10
- pyModeS.decoder.bds.bds17
- pyModeS.decoder.bds.bds20
- pyModeS.decoder.bds.bds30

EHS - enhanced surveillance

- pyModeS.decoder.bds.bds40
- pyModeS.decoder.bds.bds50
- pyModeS.decoder.bds.bds60

MRAR and MHR

- pyModeS.decoder.bds.bds44
- pyModeS.decoder.bds.bds45

"""

# ELS - elementary surveillance
from .bds.bds10 import is10, ovc10
from .bds.bds17 import cap17, is17
from .bds.bds20 import cs20, is20
from .bds.bds30 import is30

# ELS - enhanced surveillance
from .bds.bds40 import (
    alt40fms,
    alt40mcp,
    is40,
    p40baro,
    selalt40fms,
    selalt40mcp,
)

# MRAR and MHR
from .bds.bds44 import hum44, is44, p44, temp44, turb44, wind44
from .bds.bds45 import ic45, is45, mb45, p45, rh45, temp45, turb45, ws45, wv45
from .bds.bds50 import gs50, is50, roll50, rtrk50, tas50, trk50
from .bds.bds60 import hdg60, ias60, is60, mach60, vr60baro, vr60ins

__all__ = [
    "alt40fms",
    "alt40mcp",
    "cap17",
    "cs20",
    "gs50",
    "hdg60",
    "hum44",
    "ias60",
    "ic45",
    "is10",
    "is17",
    "is20",
    "is30",
    "is40",
    "is44",
    "is45",
    "is50",
    "is60",
    "mach60",
    "mb45",
    "ovc10",
    "p40baro",
    "p44",
    "p45",
    "rh45",
    "roll50",
    "rtrk50",
    "selalt40fms",
    "selalt40mcp",
    "tas50",
    "temp44",
    "temp45",
    "trk50",
    "turb44",
    "turb45",
    "vr60baro",
    "vr60ins",
    "wind44",
    "ws45",
    "wv45",
]
