"""AllCall — decoder for DF11 (All-Call Reply).

DF11 is the aircraft's response to a ground-station all-call
interrogation. It carries only the ICAO address and the transponder
capability field — no payload, no ME field.

Message layout (56 bits):
    [DF: 5][CA: 3][AA: 24][PI: 24]
"""

from typing import Any

from pymodes.decoder import register
from pymodes.decoder._base import DecoderBase
from pymodes.message import Decoded

# Capability descriptions per ICAO Annex 10 Volume IV
_CAPABILITY_TEXT = {
    0: "Level 1",
    1: "Reserved",
    2: "Reserved",
    3: "Reserved",
    4: "Level 2+, on-ground",
    5: "Level 2+, airborne",
    6: "Level 2+, airborne or on-ground",
    7: "DR != 0 or FS in (2,3,4,5), airborne or on-ground",
}


@register(11)
class AllCall(DecoderBase):
    """Decoder for DF11 all-call reply messages."""

    def decode(self, *, known: dict[str, Any] | None = None) -> Decoded:
        _ = known  # accepted for signature uniformity; AllCall never needs it
        ca = self._extract(5, 3)
        return Decoded(
            {
                "capability": ca,
                "capability_text": _CAPABILITY_TEXT.get(ca, "Unknown"),
            }
        )
