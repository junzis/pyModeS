"""BDS 1,7 — Common Usage GICB Capability Report.

The payload is a 24-bit capability map starting at payload bit 0,
where each bit corresponds to one of the 24 common-usage BDS
registers. The map indicates which registers the transponder is
willing to report via ground-initiated Comm-B (GICB) interrogation.

Payload layout (56 bits, 0-indexed from MSB):
    bits  0-23 : capability map (24 bits, one bit per register)
    bits 24-55 : reserved (must be 0 per v2's stricter heuristic;
                 jet1090 only requires bits 29-55 zero, but the
                 stricter check improves inference precision)

v2 also requires payload bit 6 to be 1 — the BDS 2,0 (aircraft
identification) capability is mandatory for any aircraft that can
emit a BDS 1,7 report, so a zero there indicates the payload is not
a BDS 1,7 report at all.
"""

from typing import Any

# Capability map index (payload bit 0..23) → BDS register.
# Per ICAO Doc 9871 Table A-2-25.
_CAPABILITY_BDS: list[str] = [
    "0,5",
    "0,6",
    "0,7",
    "0,8",
    "0,9",
    "0,A",
    "2,0",
    "2,1",
    "4,0",
    "4,1",
    "4,2",
    "4,3",
    "4,4",
    "4,5",
    "4,8",
    "5,0",
    "5,1",
    "5,2",
    "5,3",
    "5,4",
    "5,5",
    "5,6",
    "5,F",
    "6,0",
]


def is_bds17(payload: int) -> bool:
    """Return True if `payload` is a plausible BDS 1,7 report."""
    if payload == 0:
        return False

    # BDS 2,0 capability (map index 6) must be set — mandatory per spec.
    if (payload >> (55 - 6)) & 0x1 == 0:
        return False

    # v2's stricter trailing-zero heuristic: payload bits 24-55
    # (32 bits) must all be zero.
    return payload & ((1 << 32) - 1) == 0


def decode_bds17(payload: int) -> dict[str, Any]:
    """Decode a BDS 1,7 capability report into a list of supported BDS codes."""
    supported: list[str] = []
    for i, bds_code in enumerate(_CAPABILITY_BDS):
        if (payload >> (55 - i)) & 0x1:
            supported.append(bds_code)
    return {"supported_bds": supported}
