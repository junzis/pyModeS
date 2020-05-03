import os
import warnings

try:
    from . import c_common as common
    from .c_common import *
except:
    from . import common
    from .common import *

from .decoder import tell
from .decoder import adsb
from .decoder import commb
from .decoder import bds
from .extra import aero
from .extra import tcpclient

from .encoder import encode_adsb


warnings.simplefilter("once", DeprecationWarning)

dirpath = os.path.dirname(os.path.realpath(__file__))
