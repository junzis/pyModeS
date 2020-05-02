import os
import warnings

try:
    from .decoder import c_common as common
    from .decoder.c_common import *
except:
    from .decoder import common
    from .decoder.common import *

from .decoder import tell
from .decoder import adsb
from .decoder import commb
from .decoder import bds
from .extra import aero
from .extra import tcpclient

warnings.simplefilter("once", DeprecationWarning)

dirpath = os.path.dirname(os.path.realpath(__file__))
