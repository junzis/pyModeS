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
from .bds.bds17 import is17, cap17
from .bds.bds20 import is20, cs20
from .bds.bds30 import is30

# ELS - enhanced surveillance
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

# MRAR and MHR
from .bds.bds44 import is44, wind44, temp44, p44, hum44, turb44
from .bds.bds45 import is45, turb45, ws45, mb45, ic45, wv45, temp45, p45, rh45

__all__ = [
    "is10",
    "ovc10",
    "is17",
    "cap17",
    "is20",
    "cs20",
    "is30",
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
    "is44",
    "wind44",
    "temp44",
    "p44",
    "hum44",
    "turb44",
    "is45",
    "turb45",
    "ws45",
    "mb45",
    "ic45",
    "wv45",
    "temp45",
    "p45",
    "rh45",
]
