"""ELS Wrapper.

``pyModeS.els`` is deprecated, please use ``pyModeS.commb`` instead.

The ELS wrapper imports all functions from the following modules:
    - pyModeS.decoder.bds.bds10
    - pyModeS.decoder.bds.bds17
    - pyModeS.decoder.bds.bds20
    - pyModeS.decoder.bds.bds30

"""

import warnings

from .bds.bds10 import is10, ovc10
from .bds.bds17 import cap17, is17
from .bds.bds20 import cs20, is20
from .bds.bds30 import is30

warnings.simplefilter("once", DeprecationWarning)
warnings.warn(
    "pms.els module is deprecated. Please use pms.commb instead.",
    DeprecationWarning,
)


__all__ = [
    "is10",
    "ovc10",
    "is17",
    "cap17",
    "is20",
    "cs20",
    "is30",
]
