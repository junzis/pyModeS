import os
import warnings

try:
    from . import c_common as common
    from .c_common import *
except Exception:
    from . import py_common as common  # type: ignore
    from .py_common import *  # type: ignore

from .decoder import tell
from .decoder import adsb
from .decoder import commb
from .decoder import allcall
from .decoder import surv
from .decoder import bds
from .extra import aero
from .extra import tcpclient

__all__ = [
    "common",
    "tell",
    "adsb",
    "commb",
    "allcall",
    "surv",
    "bds",
    "aero",
    "tcpclient",
]


warnings.simplefilter("once", DeprecationWarning)

dirpath = os.path.dirname(os.path.realpath(__file__))
