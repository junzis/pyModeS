"""BDS 2,0 — Aircraft Identification (Comm-B).

Payload layout (56 bits, 0-indexed from MSB of MB):
    bits  0- 7 : BDS identifier (fixed 0x20)
    bits  8-55 : 8 x 6-bit callsign characters (same encoding as BDS 0,8)

Reuses _callsign.decode_callsign which expects a 48-bit int where bit
positions are 0-indexed from the MSB (char 0 at bits 0-5, char 7 at
bits 42-47). Since MB bits 8-55 are the bottom 48 bits of the 56-bit
MB int, we mask with `(1 << 48) - 1`.

Validator rejects all-zero MB, wrong BDS ID, and any 6-bit slot whose
raw index maps to '#' in the v2 character table. The invalid-index
set is derived from _callsign._CALLSIGN_CHARS at import time so the
two sources of truth cannot drift.
"""

from typing import Any

from pymodes._callsign import _CALLSIGN_CHARS, decode_callsign

# Every 6-bit index whose character is the invalid-index sentinel '#'.
# Derived from the character table so the set stays in sync with any
# future change to _CALLSIGN_CHARS.
_INVALID_CALLSIGN_IDX: frozenset[int] = frozenset(
    i for i, c in enumerate(_CALLSIGN_CHARS) if c == "#"
)


def is_bds20(mb: int) -> bool:
    """Return True if `mb` is a plausible BDS 2,0 report."""
    if mb == 0:
        return False

    # BDS identifier must be 0x20 (MB bits 0-7).
    if (mb >> 48) & 0xFF != 0x20:
        return False

    # Reject any 6-bit slot whose raw index is an invalid-callsign
    # sentinel. decode_callsign strips '#' from its output, so we
    # cannot detect these after the fact.
    cs_bits = mb & ((1 << 48) - 1)
    for i in range(8):
        idx = (cs_bits >> (42 - 6 * i)) & 0x3F
        if idx in _INVALID_CALLSIGN_IDX:
            return False

    return True


def decode_bds20(mb: int) -> dict[str, Any]:
    """Decode the 8-character callsign from a BDS 2,0 MB field."""
    cs_bits = mb & ((1 << 48) - 1)
    return {"callsign": decode_callsign(cs_bits)}
