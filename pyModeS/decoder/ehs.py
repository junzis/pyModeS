from __future__ import absolute_import, print_function, division

from pyModeS.decoder.bds.bds40 import *
from pyModeS.decoder.bds.bds44 import *
from pyModeS.decoder.bds.bds50 import *
from pyModeS.decoder.bds.bds53 import *
from pyModeS.decoder.bds.bds60 import *

def BDS(msg):
    import warnings
    from pyModeS.decoder.bds import infer
    warnings.simplefilter('always', DeprecationWarning)
    warnings.warn("pms.ehs.BDS() is deprecated, use pms.bds.infer() instead", DeprecationWarning)
    return infer(msg)

def icao(msg):
    import warnings
    from pyModeS.decoder.modes import icao
    warnings.simplefilter('always', DeprecationWarning)
    warnings.warn("pms.ehs.icao() deprecated, please use pms.modes.icao() instead", DeprecationWarning)
    return icao(msg)
