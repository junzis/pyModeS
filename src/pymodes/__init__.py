"""pymodes — Python decoder for Mode-S and ADS-B messages.

Version 3.0: ground-up rewrite of pyModeS with a class-based API,
int-shift internals, and no Cython extension.
"""

from pymodes.core import decode
from pymodes.errors import (
    DecodeError,
    InvalidHexError,
    InvalidLengthError,
    UnknownDFError,
)
from pymodes.message import DecodedMessage, Message

__version__ = "3.0.0.dev0"

__all__ = [
    "DecodeError",
    "DecodedMessage",
    "InvalidHexError",
    "InvalidLengthError",
    "Message",
    "UnknownDFError",
    "__version__",
    "decode",
]
