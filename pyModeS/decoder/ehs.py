from __future__ import absolute_import, print_function, division
import warnings
warnings.simplefilter('once', DeprecationWarning)

from pyModeS.decoder.bds.bds10 import *
from pyModeS.decoder.bds.bds17 import *
from pyModeS.decoder.bds.bds20 import *
from pyModeS.decoder.bds.bds40 import *
from pyModeS.decoder.bds.bds44 import *
from pyModeS.decoder.bds.bds50 import *
from pyModeS.decoder.bds.bds53 import *
from pyModeS.decoder.bds.bds60 import *
from pyModeS.decoder.bds import infer

def BDS(msg):
    warnings.warn("pms.ehs.BDS() is deprecated, use pms.bds.infer() instead.", DeprecationWarning)
    return infer(msg)

def icao(msg):
    from pyModeS.decoder.common import icao
    return icao(msg)
