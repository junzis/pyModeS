"""6-bit-per-character callsign decoder for ADS-B and Comm-B.

ADS-B identification messages (BDS 0,8, TC=1-4) carry an 8-character
callsign as eight 6-bit slots packed into 48 bits of the ME field.
Comm-B register 2,0 uses the same encoding.

The character set is a fixed 64-entry table (ICAO Annex 10 Vol IV);
slots that decode to the placeholder '#' represent unused or invalid
characters and are stripped from the final output. Underscores ('_')
represent space characters and are preserved.
"""

_CALLSIGN_CHARS = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ#####_###############0123456789######"


def decode_callsign(bits: int) -> str:
    """Decode a 48-bit packed callsign to an 8-character string.

    Args:
        bits: The raw 48-bit callsign field as an integer. Eight 6-bit
            slots, MSB-first.

    Returns:
        The callsign string with placeholder '#' characters stripped.
        May be empty if all slots decode to '#'.

    Example:
        >>> decode_callsign(0x15A678D4D220)
        'EZY85MH_'
    """
    chars: list[str] = [
        _CALLSIGN_CHARS[(bits >> (42 - 6 * i)) & 0x3F] for i in range(8)
    ]
    return "".join(chars).replace("#", "")
