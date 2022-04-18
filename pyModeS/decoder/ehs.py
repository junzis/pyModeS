"""EHS Wrapper.

``pyModeS.ehs`` is deprecated, please use ``pyModeS.commb`` instead.

The EHS wrapper imports all functions from the following modules:
    - pyModeS.decoder.bds.bds40
    - pyModeS.decoder.bds.bds50
    - pyModeS.decoder.bds.bds60

"""

import warnings

from pyModeS.decoder.bds.bds40 import *
from pyModeS.decoder.bds.bds50 import *
from pyModeS.decoder.bds.bds60 import *
from pyModeS.decoder.bds import infer

warnings.simplefilter("once", DeprecationWarning)
warnings.warn(
    "pms.ehs module is deprecated. Please use pms.commb instead.", DeprecationWarning
)


def BDS(msg):
    warnings.warn(
        "pms.ehs.BDS() is deprecated, use pms.bds.infer() instead.", DeprecationWarning
    )
    return infer(msg)


def icao(msg):
    from . import common

    return common.icao(msg)
