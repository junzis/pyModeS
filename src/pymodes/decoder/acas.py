"""ACAS — decoder for DF0 and DF16 air-air surveillance (TCAS/ACAS replies).

Both messages are TCAS/ACAS collision-avoidance replies. DF0 is 56 bits;
DF16 extends DF0 with a 56-bit MV (ACAS RA / broadcast) payload, making
the full message 112 bits.

Phase 1 handles the shared header fields (VS, CC, SL, RI, AC) and exposes
the MV field as a raw 14-char hex string for DF16. Full MV / BDS 3,0
decoding (ACAS Resolution Advisory semantics) is deferred to phase 6.

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

from __future__ import annotations

from pymodes._altcode import altcode_to_altitude
from pymodes._bits import extract_field
from pymodes.decoder import register
from pymodes.decoder._base import DecoderBase
from pymodes.message import DecodedMessage


@register(0, 16)
class ACAS(DecoderBase):
    """Decoder for DF0 and DF16 air-air surveillance messages."""

    def decode(self) -> DecodedMessage:
        result: DecodedMessage = DecodedMessage()

        # Determine length based on DF
        length = 56 if self._df == 0 else 112

        # Shared header fields
        vs = extract_field(self._n, 5, 1, length)
        result["vertical_status"] = "on-ground" if vs == 1 else "airborne"

        result["cross_link_capability"] = extract_field(self._n, 6, 1, length)
        result["sensitivity_level"] = extract_field(self._n, 8, 3, length)
        result["reply_information"] = extract_field(self._n, 13, 4, length)

        # Altitude code at bits 19-31
        ac = extract_field(self._n, 19, 13, length)
        result["altitude"] = altcode_to_altitude(ac)

        # DF16-specific: expose the MV field as raw hex
        if self._df == 16:
            mv = extract_field(self._n, 32, 56, 112)
            result["mv"] = f"{mv:014X}"

        return result
