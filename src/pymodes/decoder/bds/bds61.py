"""BDS 6,1 -- ADS-B aircraft status (TC=28).

Two subtypes:
- Subtype 1: emergency / priority status + squawk
- Subtype 2: ACAS RA broadcast (decoded by BDS 3,0 in Plan 3)

ME field layout for subtype 1 (56 bits, 0-indexed from MSB):
    bits 0-4:    TC (= 28)
    bits 5-7:    subtype
    bits 8-10:   emergency state (3 bits)
    bits 11-23:  identity code (13 bits, squawk)
    bits 24-55:  reserved
"""

from typing import Any

from pymodes._idcode import idcode_to_squawk


def decode_bds61(me: int) -> dict[str, Any]:
    """Decode a BDS 6,1 ME field (ADS-B aircraft status).

    Args:
        me: The 56-bit ME field as an integer.

    Returns:
        Dict with subtype plus subtype-specific fields. For subtype 1:
        emergency_state and squawk. For subtype 2: acas_ra_broadcast=True
        as a placeholder; full decoding is deferred to BDS 3,0 in Plan 3.
    """
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
        # ACAS RA broadcast -- payload lives in BDS 3,0. Plan 3 will
        # decode the full RA; for now expose a flag.
        return {
            "subtype": subtype,
            "acas_ra_broadcast": True,
        }

    return {"subtype": subtype}
