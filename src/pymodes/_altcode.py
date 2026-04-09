"""Mode-S altitude code (AC field) decoder.

The AC field in DF0/4/16/20 is 13 bits: C1 A1 C2 A2 C4 A4 M B1 Q B2 D2 B4 D4.
It supports two encodings:

- Q = 1: 25-foot interval, linear. 11 bits form a value N;
  altitude = N * 25 - 1000 (feet).
- Q = 0: 100-foot interval, Gillham gray code. The 11 non-Q/M bits
  form a gray-coded altitude above the 25-ft range (rarely used in
  modern aviation; phase 1 implements Q=1 only and returns None for
  Q=0 cases until phase 5 adds gray code).

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

    # Extract M (position 6) and Q (position 8) bits.
    # For a 13-bit MSB-first field stored in a 13-bit int, position p
    # corresponds to LSB index (12 - p).
    m_bit = (ac >> 6) & 0x1  # 12 - 6 = 6
    q_bit = (ac >> 4) & 0x1  # 12 - 8 = 4

    if m_bit == 0 and q_bit == 1:
        # 25-foot interval, linear encoding. Drop M (LSB bit 6) and
        # Q (LSB bit 4); the remaining 11 bits form the linear value.
        # The bits below M and above Q (LSB bits 7..12) shift right by 2,
        # B1 (LSB bit 5) shifts right by 1, and D4..B2 (LSB bits 0..3) stay.
        n = ((ac >> 2) & 0x7E0) | ((ac >> 1) & 0x10) | (ac & 0xF)
        return n * 25 - 1000

    # Q = 0 (Gillham gray code) — not yet implemented in phase 1.
    # Phase 5 will add this. For now return None so callers don't crash.
    return None
