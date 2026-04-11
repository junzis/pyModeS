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
from pyModeS._v2_removed import (
    _V2_REMOVED_NAMES,
    install_v2_removed_finder,
    raise_v2_removed,
)
from pyModeS.core import decode
from pyModeS.errors import (
    DecodeError,
    InvalidHexError,
    InvalidLengthError,
    UnknownDFError,
)
from pyModeS.message import Decoded, Message

# Intercept every `import pyModeS.<v2_removed>` at the import-
# system level with a single meta-path finder — see
# pyModeS/_v2_removed.py for the full list and the loader that
# raises on exec.
install_v2_removed_finder()

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


# ``pyModeS.adsb`` bare attribute access (after ``import pyModeS``)
# doesn't trip the import system, so the meta-path finder never
# sees it. PEP 562 gives us this package-level hook as the fallback:
# anything in ``_V2_REMOVED_NAMES`` (defined in _v2_removed.py) is
# routed through the same ``raise_v2_removed`` helper the loader
# uses, so the error text stays uniform.
def __getattr__(name: str) -> Any:
    if name in _V2_REMOVED_NAMES:
        raise_v2_removed(f"pyModeS.{name}")
    raise AttributeError(f"module 'pyModeS' has no attribute {name!r}")
