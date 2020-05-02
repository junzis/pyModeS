"""ELS Wrapper.

``pyModeS.els`` is deprecated, please use ``pyModeS.commb`` instead.

The ELS wrapper imports all functions from the following modules:
    - pyModeS.decoder.bds.bds10
    - pyModeS.decoder.bds.bds17
    - pyModeS.decoder.bds.bds20
    - pyModeS.decoder.bds.bds30

"""

from pyModeS.decoder.bds.bds10 import *
from pyModeS.decoder.bds.bds17 import *
from pyModeS.decoder.bds.bds20 import *
from pyModeS.decoder.bds.bds30 import *

import warnings

warnings.simplefilter("once", DeprecationWarning)
warnings.warn(
    "pms.els module is deprecated. Please use pms.commb instead.", DeprecationWarning
)
