"""Base class for all pymodes decoder classes.

Each decoder stores the raw message int plus its length (56 or 112)
and, for long messages, the 56-bit payload (ME/MV/MB) extracted from
bits 32-87. Subclasses call `self._extract(start, width)` to pull
unsigned bit fields from the full message, or use `self._payload`
directly for payload-level positions.
"""

from typing import Any

from pymodes._bits import extract_unsigned
from pymodes.message import Decoded


class DecoderBase:
    """Abstract base for all decoder classes.

    Subclasses receive the full message int, the DF, the ICAO string,
    and the bit length at construction. They implement `decode()` to
    return DF-specific fields.

    Attributes:
        _n: the full message int (56 or 112 bits wide).
        _df: downlink format (for branching inside decoders that
            handle multiple DFs).
        _icao: the ICAO address as an uppercase hex string.
        _length: 56 or 112, the bit width of the message.
        _payload: the 56-bit payload (ME/MV/MB, bits 32-87) for
            112-bit messages, or 0 for short messages. Used by
            ADS-B and Comm-B decoders that address fields relative
            to the payload MSB.
    """

    __slots__ = ("_df", "_icao", "_length", "_n", "_payload")

    def __init__(self, n: int, *, df: int, icao: str, length: int) -> None:
        self._n = n
        self._df = df
        self._icao = icao
        self._length = length
        # For 112-bit messages, extract the 56-bit payload at bits
        # 32-87. Short messages have no such field; set to 0.
        self._payload = extract_unsigned(n, 32, 56, 112) if length == 112 else 0

    def _extract(self, start: int, width: int) -> int:
        """Extract an unsigned bit field from the full message int.

        Positions are 0-indexed from the message MSB.
        """
        return extract_unsigned(self._n, start, width, self._length)

    def decode(
        self, *, known: dict[str, Any] | None = None
    ) -> Decoded:  # pragma: no cover - abstract
        """Return a Decoded dict with DF-specific fields.

        Subclasses override this. The returned dict should contain
        only fields specific to this decoder — df, icao, and crc_valid
        are added by Message.decode() in the caller.

        Args:
            known: Optional aircraft state for Comm-B BDS 5,0/6,0
                disambiguation. Only CommB consumes this; other
                decoder classes accept and ignore it for signature
                uniformity.
        """
        raise NotImplementedError
