"""Mode-S identity code (ID / squawk) decoder.

The ID field in DF5/21 is 13 bits:
    C1 A1 C2 A2 C4 A4 X B1 D1 B2 D2 B4 D4

It encodes a 4-digit octal squawk (0000-7777) where each digit is
formed by combining 3 interleaved pulse bits:

    Digit A = A4 A2 A1 (binary)
    Digit B = B4 B2 B1
    Digit C = C4 C2 C1
    Digit D = D4 D2 D1

The X bit is always 0 (reserved). Bit positions are 0-indexed MSB-first.
"""

from __future__ import annotations


def idcode_to_squawk(idcode: int) -> str:
    """Decode a 13-bit identity code to a 4-digit octal squawk string.

    Args:
        idcode: The raw 13-bit ID field as an integer in [0, 8191].

    Returns:
        A 4-character string of octal digits (e.g., "7500", "1200", "0000").

    Example:
        >>> idcode_to_squawk(0x0808)
        '1200'
    """
    # Bit positions in the 13-bit ID field (MSB-first, 0-indexed):
    #   C1=0 A1=1 C2=2 A2=3 C4=4 A4=5 X=6 B1=7 D1=8 B2=9 D2=10 B4=11 D4=12

    def bit(pos: int) -> int:
        return (idcode >> (12 - pos)) & 0x1

    a = (bit(5) << 2) | (bit(3) << 1) | bit(1)  # A4 A2 A1
    b = (bit(11) << 2) | (bit(9) << 1) | bit(7)  # B4 B2 B1
    c = (bit(4) << 2) | (bit(2) << 1) | bit(0)  # C4 C2 C1
    d = (bit(12) << 2) | (bit(10) << 1) | bit(8)  # D4 D2 D1

    return f"{a}{b}{c}{d}"
