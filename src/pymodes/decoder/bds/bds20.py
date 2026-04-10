"""BDS 2,0 -- Aircraft Identification (Comm-B).

Payload layout (56 bits, 0-indexed from MSB of MB):
    bits  0- 7 : BDS identifier (fixed 0x20)
    bits  8-55 : 8 x 6-bit callsign characters (same encoding as BDS 0,8)

Reuses _callsign.decode_callsign which expects a 48-bit int. MB bits
8-55 are the bottom 48 bits of the 56-bit MB int, so we mask with
`(1 << 48) - 1` before calling the decoder.

Validator rejects all-zero MB, wrong BDS ID, and any 6-bit slot whose
index is not a valid callsign character (A-Z, space, 0-9). The
invalid-slot rejection is a v2 heuristic that improves inference
precision on genuinely non-BDS20 traffic.
"""

from typing import Any

from pymodes._callsign import decode_callsign, is_valid_callsign_char


def is_bds20(mb: int) -> bool:
    """Return True if `mb` is a plausible BDS 2,0 report."""
    if mb == 0:
        return False

    # BDS identifier must be 0x20 (MB bits 0-7).
    if (mb >> 48) & 0xFF != 0x20:
        return False

    # Every 6-bit callsign slot must map to a valid character.
    cs_bits = mb & ((1 << 48) - 1)
    for i in range(8):
        idx = (cs_bits >> (42 - 6 * i)) & 0x3F
        if not is_valid_callsign_char(idx):
            return False

    return True


def decode_bds20(mb: int) -> dict[str, Any]:
    """Decode the callsign from a BDS 2,0 MB field."""
    cs_bits = mb & ((1 << 48) - 1)
    return {"callsign": decode_callsign(cs_bits)}
