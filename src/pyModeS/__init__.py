"""pyModeS — Python decoder for Mode-S and ADS-B messages.

Version 3.0: ground-up rewrite of pyModeS.

Position reference kwargs
-------------------------
Two distinct reference kwargs exist for single-message CPR resolution
and are NOT interchangeable:

- ``reference=(lat, lon)`` — airborne CPR (BDS 0,5). Accepts a
  ``(lat, lon)`` tuple only. The reference must lie within 180 NM
  of the true aircraft position.

- ``surface_ref=<airport|tuple>`` — surface CPR (BDS 0,6). Accepts
  either an ICAO airport code looked up in the shipped airport
  database (e.g. ``"EHAM"``) or an explicit ``(lat, lon)`` tuple
  (typically the receiver location). The reference must lie within
  45 NM of the true position — tighter than the airborne tolerance.

For streaming workflows where references aren't known ahead of time,
use :class:`PipeDecoder` which resolves airborne positions from
even/odd CPR pairs without any reference and still accepts
``surface_ref`` for surface messages.
"""

from importlib.metadata import version as _version
from typing import Any

from pyModeS._pipe import PipeDecoder
from pyModeS._v2_removed import v2_removed_error
from pyModeS.core import decode
from pyModeS.errors import (
    DecodeError,
    InvalidHexError,
    InvalidLengthError,
    UnknownDFError,
)
from pyModeS.message import Decoded, Message

__version__ = _version("pyModeS")

__all__ = [
    "DecodeError",
    "Decoded",
    "InvalidHexError",
    "InvalidLengthError",
    "Message",
    "PipeDecoder",
    "UnknownDFError",
    "__version__",
    "decode",
]

# Names that used to live directly under pyModeS in the v2 API.
# Any attribute access like ``pyModeS.adsb`` or the equivalent
# ``from pyModeS import adsb`` (after PEP 562) is caught below
# and turned into a :class:`V2APIRemovedError` that points at
# :func:`pyModeS.decode` and the migration guide. The stub files
# at ``pyModeS/adsb.py`` etc. handle the ``from pyModeS.adsb
# import X`` pattern; this hook handles the bare attribute path.
_V2_REMOVED_NAMES: frozenset[str] = frozenset(
    {
        "adsb",
        "commb",
        "ehs",
        "els",
        "common",
        "util",
        "bds",
        "streamer",
        "extra",
    }
)


def __getattr__(name: str) -> Any:
    if name in _V2_REMOVED_NAMES:
        raise v2_removed_error(f"pyModeS.{name}")
    raise AttributeError(f"module 'pyModeS' has no attribute {name!r}")
