"""BDS 6,1 -- ADS-B aircraft status (TC=28).

Two subtypes:
- Subtype 1: emergency / priority status + squawk
- Subtype 2: ACAS RA broadcast (uses the BDS 3,0 decoder)

Payload layout (56 bits, 0-indexed from MSB of payload):

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
                payload bits 8-55)

The subtype-2 branch builds a synthetic BDS 3,0 payload by
prepending the 0x30 BDS identifier byte and copying the ACAS RA
bits verbatim, then delegates to decode_bds30.
"""

from typing import Any

from pyModeS._idcode import idcode_to_squawk
from pyModeS.decoder.bds.bds30 import decode_bds30


def decode_bds61(payload: int) -> dict[str, Any]:
    """Decode a BDS 6,1 payload (ADS-B aircraft status)."""
    subtype = (payload >> 48) & 0x7  # bits 5-7

    if subtype == 1:
        emergency_state = (payload >> 45) & 0x7  # bits 8-10
        idcode = (payload >> 32) & 0x1FFF  # bits 11-23
        return {
            "subtype": subtype,
            "emergency_state": emergency_state,
            "squawk": idcode_to_squawk(idcode),
        }

    if subtype == 2:
        # Build a synthetic BDS 3,0 payload: 0x30 in bits 0-7, ACAS
        # RA payload in bits 8-55 (copied verbatim from bits 8-55).
        ra_payload = payload & ((1 << 48) - 1)
        synthetic_bds30 = (0x30 << 48) | ra_payload
        result: dict[str, Any] = {"subtype": subtype}
        result.update(decode_bds30(synthetic_bds30))
        return result

    return {"subtype": subtype}
