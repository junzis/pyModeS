"""6-bit ICAO callsign encoding used by ADS-B BDS 0,8 and Comm-B BDS 2,0.

The ICAO Mode-S callsign alphabet is a truncation of ASCII. Each 6-bit
slot stores the low 6 bits of the corresponding ASCII character:

    1..26   -> 'A'..'Z'  (slot | 0x40 reconstructs the ASCII letter)
    32      -> ' '       (already ASCII space 0x20)
    48..57  -> '0'..'9'  (already ASCII digits 0x30..0x39)
    anything else -> '#' (invalid character sentinel)

A 48-bit integer holds 8 such slots, char 0 at bits 0-5 (MSB-first)
through char 7 at bits 42-47. Real-world callsigns are left-justified
and right-padded with spaces; this decoder strips both leading and
trailing whitespace so the returned string is the bare callsign.

The 64-entry lookup table is built once at module import from the
ASCII rules above, so there is no hand-typed string that can drift
from the validator's notion of "valid character".
"""


def _build_table() -> str:
    """Return the 64-character lookup table derived from ASCII rules."""
    table: list[str] = []
    for i in range(64):
        if 1 <= i <= 26:
            table.append(chr(i | 0x40))  # A-Z
        elif i == 32 or 48 <= i <= 57:
            table.append(chr(i))  # space or 0-9
        else:
            table.append("#")  # invalid
    return "".join(table)


_CALLSIGN_TABLE: str = _build_table()


def decode_callsign(bits: int) -> str:
    """Decode an 8x6-bit ICAO callsign from a 48-bit integer.

    Args:
        bits: The 48-bit callsign payload as a Python int (bits 0-5
            hold char 0, bits 42-47 hold char 7).

    Returns:
        The decoded callsign with leading and trailing whitespace
        stripped. Interior whitespace (rare but possible) is preserved.
        Invalid 6-bit values decode to '#' and remain in the output so
        that bad payloads are visible to the caller.
    """
    return "".join(
        _CALLSIGN_TABLE[(bits >> (42 - 6 * i)) & 0x3F] for i in range(8)
    ).strip()


def is_valid_callsign_char(idx: int) -> bool:
    """Return True if a 6-bit index maps to a valid callsign character.

    Used by Comm-B BDS 2,0 inference to reject MBs whose callsign
    slots contain characters that are not in the ICAO alphabet.
    """
    return _CALLSIGN_TABLE[idx] != "#"
