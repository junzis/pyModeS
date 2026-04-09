"""pymodes — Python decoder for Mode-S and ADS-B messages.

Version 3.0: ground-up rewrite of pyModeS.
"""

from importlib.metadata import version as _version

from pymodes.core import decode
from pymodes.errors import (
    DecodeError,
    InvalidHexError,
    InvalidLengthError,
    UnknownDFError,
)
from pymodes.message import DecodedMessage, Message

__version__ = _version("pymodes")

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
