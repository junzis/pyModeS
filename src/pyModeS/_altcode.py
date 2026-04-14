"""Mode-S altitude code (AC field) decoder.

The AC field in DF0/4/16/20 is 13 bits: C1 A1 C2 A2 C4 A4 M B1 Q B2 D2 B4 D4.
It supports two encodings:

- Q = 1: 25-foot interval, linear. 11 bits form a value N;
  altitude = N * 25 - 1000 (feet).
- Q = 0: 100-foot interval, Gillham code (a Gray-code variant used by
  legacy pressure altimeters; see ICAO Annex 10 Vol IV and DO-260).
  Re-orders the 11 non-M non-Q bits into a Gillham-coded (500-ft,
  100-ft) pair and converts to feet via
  `alt = n500 * 500 + n100 * 100 - 1300`. Note: Q=0 is a distinct
  encoding standard, not an indicator of high altitude.

If the entire 13-bit field is zero, altitude is reported as unknown.
"""


def altcode_to_altitude(ac: int) -> int | None:
    """Decode a 13-bit Mode-S altitude code field to feet.

    Args:
        ac: The raw 13-bit AC field as an integer in [0, 8191].

    Returns:
        Altitude in feet as an int, or None if the code is invalid
        or represents "altitude unknown".

    Bit layout (MSB first, 13 bits):
        C1 A1 C2 A2 C4 A4 M B1 Q B2 D2 B4 D4
        0  1  2  3  4  5  6 7  8 9  10 11 12
    """
    if ac == 0:
        return None

    # Extract M (pos 6 → LSB bit 6) and Q (pos 8 → LSB bit 4).
    m_bit = (ac >> 6) & 0x1
    q_bit = (ac >> 4) & 0x1

    if m_bit == 0 and q_bit == 1:
        # 25-foot interval, linear encoding. Drop M (LSB bit 6) and
        # Q (LSB bit 4); the remaining 11 bits form the linear value.
        n = ((ac >> 2) & 0x7E0) | ((ac >> 1) & 0x10) | (ac & 0xF)
        return n * 25 - 1000

    if m_bit == 0 and q_bit == 0:
        # 100-foot interval, Gillham code.
        # Extract each named bit from the 13-bit AC field.
        def b(pos: int) -> int:
            return (ac >> (12 - pos)) & 0x1

        c1, a1 = b(0), b(1)
        c2, a2 = b(2), b(3)
        c4, a4 = b(4), b(5)
        b1 = b(7)
        b2, d2 = b(9), b(10)
        b4, d4 = b(11), b(12)

        # Rearrange the non-M, non-Q bits per DO-260 into the sequence
        #   D2 D4 A1 A2 A4 B1 B2 B4 C1 C2 C4  (11 bits)
        # The first 8 bits form a Gillham-coded 500-ft counter and the
        # last 3 bits a 100-ft counter, per ICAO Annex 10 Vol IV.
        gc500 = (
            (d2 << 7)
            | (d4 << 6)
            | (a1 << 5)
            | (a2 << 4)
            | (a4 << 3)
            | (b1 << 2)
            | (b2 << 1)
            | b4
        )
        gc100 = (c1 << 2) | (c2 << 1) | c4

        n500 = _gray2int(gc500)
        n100 = _gray2int(gc100)

        # n100 in {0, 5, 6} is invalid per the Mode-S spec.
        if n100 in (0, 5, 6):
            return None

        # n100 == 7 is remapped to 5 per the spec.
        if n100 == 7:
            n100 = 5

        # Odd n500 inverts the direction of n100 counting.
        if n500 % 2:
            n100 = 6 - n100

        return n500 * 500 + n100 * 100 - 1300

    # M = 1: meter-based encoding (rare, non-standard). Return None.
    return None


def _gray2int(n: int) -> int:
    """Convert an unsigned Gillham code to a plain binary integer.

    Gillham is a reflected Gray-code variant, so the standard Gray-to-binary
    fold (XOR with successive right-shifts) applies.
    """
    n ^= n >> 8
    n ^= n >> 4
    n ^= n >> 2
    n ^= n >> 1
    return n
