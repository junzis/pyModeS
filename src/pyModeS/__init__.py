import os
import warnings

try:
    from . import c_common as common
    from .c_common import *
except Exception:
    from . import py_common as common  # type: ignore
    from .py_common import *  # type: ignore

from .decoder import adsb, allcall, bds, commb, surv, tell
from .extra import aero, tcpclient

__all__ = [
    "adsb",
    "aero",
    "allcall",
    "bds",
    "commb",
    "common",
    "surv",
    "tcpclient",
    "tell",
]


warnings.simplefilter("once", DeprecationWarning)

dirpath = os.path.dirname(os.path.realpath(__file__))
