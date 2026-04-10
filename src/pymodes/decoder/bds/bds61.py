"""BDS 6,1 -- ADS-B aircraft status (TC=28).

Two subtypes:
- Subtype 1: emergency / priority status + squawk
- Subtype 2: ACAS RA broadcast (uses the BDS 3,0 decoder)

ME field layout (56 bits, 0-indexed from MSB of ME):

Subtype 1:
    bits 0- 4 : TC (= 28)
    bits 5- 7 : subtype (= 1)
    bits 8-10 : emergency state (3 bits)
    bits 11-23: identity code (13 bits, squawk)
    bits 24-55: reserved

Subtype 2:
    bits 0- 4 : TC (= 28)
    bits 5- 7 : subtype (= 2)
    bits 8-55 : ACAS RA payload (identical bit layout to BDS 3,0
                MB bits 8-55)

The subtype-2 branch builds a synthetic BDS 3,0 MB by prepending
the 0x30 BDS identifier byte and copying the ACAS RA bits verbatim,
then delegates to decode_bds30.
"""

from typing import Any

from pymodes._idcode import idcode_to_squawk
from pymodes.decoder.bds.bds30 import decode_bds30


def decode_bds61(me: int) -> dict[str, Any]:
    """Decode a BDS 6,1 ME field (ADS-B aircraft status)."""
    subtype = (me >> 48) & 0x7  # bits 5-7

    if subtype == 1:
        emergency_state = (me >> 45) & 0x7  # bits 8-10
        idcode = (me >> 32) & 0x1FFF  # bits 11-23
        return {
            "subtype": subtype,
            "emergency_state": emergency_state,
            "squawk": idcode_to_squawk(idcode),
        }

    if subtype == 2:
        # Build a synthetic BDS 3,0 MB: 0x30 in bits 0-7, ACAS RA
        # payload in bits 8-55 (copied verbatim from ME bits 8-55).
        ra_payload = me & ((1 << 48) - 1)
        synthetic_mb = (0x30 << 48) | ra_payload
        result: dict[str, Any] = {"subtype": subtype}
        result.update(decode_bds30(synthetic_mb))
        return result

    return {"subtype": subtype}
