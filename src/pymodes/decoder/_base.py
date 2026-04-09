"""Base class for all pymodes decoder classes.

Each decoder is a small class that takes the raw message int and
the DF value at construction time, then exposes a `decode()` method
returning a DecodedMessage dict of DF-specific fields.
"""

from __future__ import annotations

from pymodes.message import DecodedMessage


class DecoderBase:
    """Abstract base for all decoder classes.

    Subclasses store the message int and DF and implement `decode()`.
    """

    __slots__ = ("_df", "_icao", "_n")

    def __init__(self, n: int, *, df: int, icao: str) -> None:
        self._n = n
        self._df = df
        self._icao = icao

    def decode(self) -> DecodedMessage:  # pragma: no cover - abstract
        """Return a DecodedMessage with DF-specific fields.

        Subclasses override this. The returned dict should contain
        only fields specific to this decoder — df, icao, and crc_valid
        are added by Message.decode() in the caller.
        """
        raise NotImplementedError
