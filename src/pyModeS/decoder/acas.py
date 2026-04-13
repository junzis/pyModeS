"""ACAS — decoder for DF0 and DF16 air-air surveillance (TCAS/ACAS replies).

Both messages are TCAS/ACAS collision-avoidance replies. DF0 is 56 bits;
DF16 extends DF0 with a 56-bit MV (ACAS RA / broadcast) payload, making
the full message 112 bits.

This decoder handles the shared header fields (VS, CC, SL, RI, AC) and
exposes the MV field as a raw 14-char hex string for DF16. Full
MV / BDS 3,0 decoding (ACAS Resolution Advisory semantics) is
handled separately in :mod:`pyModeS.decoder.bds.bds30`.

Layout shared:
    bits 0-4:   DF (5)
    bit 5:      VS — vertical status (0=airborne, 1=on-ground)
    bit 6:      CC — cross-link capability
    bit 7:      reserved (1)
    bits 8-10:  SL — sensitivity level (3)
    bits 11-12: reserved (2)
    bits 13-16: RI — reply information (4)
    bits 17-18: reserved (2)
    bits 19-31: AC — altitude code (13)

DF0 only:   bits 32-55: AP (24) — address/parity
DF16 only:  bits 32-87: MV (56) — ACAS RA message
            bits 88-111: AP (24)
"""

from typing import Any

from pyModeS._altcode import altcode_to_altitude
from pyModeS.decoder import register
from pyModeS.decoder._base import DecoderBase
from pyModeS.message import Decoded


@register(0, 16)
class ACAS(DecoderBase):
    """Decoder for DF0 and DF16 air-air surveillance messages."""

    def decode(self, *, known: dict[str, Any] | None = None) -> Decoded:
        _ = known  # accepted for signature uniformity; ACAS never needs it
        result: Decoded = Decoded()

        # Shared header fields (positions are identical for DF0 and DF16)
        vs = self._extract(5, 1)
        result["vertical_status"] = "on-ground" if vs == 1 else "airborne"

        result["cross_link_capability"] = self._extract(6, 1)
        result["sensitivity_level"] = self._extract(8, 3)
        result["reply_information"] = self._extract(13, 4)

        # Altitude code at bits 19-31
        result["altitude"] = altcode_to_altitude(self._extract(19, 13))

        # DF16-specific: expose the 56-bit MV field (bits 32-87) as raw hex.
        # DecoderBase populates self._payload for all 112-bit messages.
        if self._df == 16:
            result["mv"] = f"{self._payload:014X}"

        return result
