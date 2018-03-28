from __future__ import absolute_import, print_function, division

from pyModeS.decoder.bds.bds40 import *
from pyModeS.decoder.bds.bds50 import *
from pyModeS.decoder.bds.bds60 import *

def BDS(msg):
    import warnings
    from pyModeS.decoder.bds import infer
    warnings.simplefilter('always', DeprecationWarning)
    warnings.warn("pms.ehs.BDS() is deprecated, use pms.bds.infer() instead", DeprecationWarning)
    return infer(msg)

def icao(msg):
    from pyModeS.decoder.common import icao
    return icao(msg)
