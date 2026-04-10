"""Bit-extraction primitives for Mode-S message decoding.

Every Mode-S message is represented internally as a Python integer
holding the full 56 or 112 bits (short vs long format). Bit positions
are measured from the MSB: bit 0 is the leftmost (most significant)
bit of the message.

This module provides three primitives used by every decoder:

- extract_unsigned(n, start, width, total_bits) — unsigned field extraction
- extract_signed(n, start, width, total_bits) — signed (two's complement) extraction
- crc_remainder(n, length) — 24-bit Mode-S CRC computation
"""


def extract_unsigned(n: int, start: int, width: int, total_bits: int) -> int:
    """Extract `width` bits starting at bit `start` (MSB-first) from an
    `total_bits`-wide integer.

    Args:
        n: The Mode-S message as a Python int. Must fit in `total_bits` bits.
        start: 0-indexed bit position from the MSB (bit 0 is leftmost).
        width: Number of bits to extract.
        total_bits: Total width of the source integer (56 for short Mode-S,
            112 for long Mode-S).

    Returns:
        The extracted bits as a non-negative integer in [0, 2**width - 1].

    Example:
        >>> msg = int("8D406B902015A678D4D220AA4BDA", 16)
        >>> extract_unsigned(msg, 0, 5, 112)   # DF (bits 0-4)
        17
        >>> extract_unsigned(msg, 8, 24, 112)  # ICAO (bits 8-31)
        4221840
    """
    shift = total_bits - start - width
    return (n >> shift) & ((1 << width) - 1)


def extract_signed(n: int, start: int, width: int, total_bits: int) -> int:
    """Extract `width` bits as a signed two's-complement integer.

    Same bit-positioning semantics as extract_unsigned, but interprets the
    MSB of the extracted value as a sign bit.

    Args:
        n: The Mode-S message as a Python int.
        start: 0-indexed bit position from the MSB.
        width: Number of bits (must be >= 2 to carry a sign bit).
        total_bits: Total width of the source integer.

    Returns:
        Signed integer in [-2**(width-1), 2**(width-1) - 1].
    """
    raw = extract_unsigned(n, start, width, total_bits)
    sign_bit = 1 << (width - 1)
    if raw & sign_bit:
        raw -= 1 << width
    return raw


# Mode-S CRC-24 polynomial: x^24 + x^23 + x^22 + x^21 + x^20 + x^19 + x^18 +
#                           x^17 + x^16 + x^15 + x^14 + x^13 + x^12 + x^10 +
#                           x^3 + 1
# Per ICAO Annex 10 Vol IV §3.1.2.6. Two equivalent representations:
#   25-bit with implicit top bit: 0x1FFF409 (used by the bit-by-bit form)
#   24-bit with the top bit dropped: 0x00FFF409 (used by the table form,
#   matches FlightAware dump1090's MODES_GENERATOR_POLY)
_CRC_POLY = 0xFFF409


def _build_crc_table() -> tuple[int, ...]:
    """Precompute the 256-entry CRC-24 lookup table at module load.

    Each entry ``table[i]`` is the CRC-24 of an input with byte ``i`` in
    the top 8 bits and zeros elsewhere — i.e., the result of processing
    that byte with the bit-by-bit algorithm after eight shift-and-XOR
    rounds. This is the standard byte-at-a-time CRC table technique
    (Sarwate 1988).

    Cross-checked against FlightAware dump1090 crc.c::initLookupTables;
    identical output for all 256 entries.
    """
    table = [0] * 256
    for i in range(256):
        c = i << 16
        for _ in range(8):
            c = ((c << 1) ^ _CRC_POLY) if (c & 0x800000) else (c << 1)
        table[i] = c & 0xFFFFFF
    return tuple(table)


_CRC_TABLE: tuple[int, ...] = _build_crc_table()


def crc_remainder(n: int, length: int) -> int:
    """Compute the Mode-S CRC-24 remainder of a `length`-bit integer.

    For DF17/18 (extended squitter), a valid message has a remainder of 0.
    For DF20/21 (Comm-B), the remainder equals the aircraft's ICAO address
    (optionally XORed with a BDS code overlay from the interrogation).

    Args:
        n: The full Mode-S message as a Python int (56 or 112 bits).
        length: Total bit-width of the message (56 or 112).

    Returns:
        24-bit CRC remainder as an integer in [0, 2**24 - 1].

    Example:
        >>> msg = int("8D406B902015A678D4D220AA4BDA", 16)
        >>> crc_remainder(msg, 112)
        0

    Implementation:
        Byte-at-a-time long division using a precomputed 256-entry lookup
        table (see ``_build_crc_table``). For each data byte (11 bytes for
        a long Mode-S message, 4 for a short), one table indexing and one
        XOR advance the running CRC by 8 bits. After the data bytes are
        consumed, the 24 parity bits at the tail of the message are XORed
        into the running CRC to produce the final remainder.

        The equivalent bit-by-bit form, kept here for reference, is::

            def crc_remainder_bitwise(n: int, length: int) -> int:
                remainder = n
                poly_shifted = (_CRC_POLY | 0x1000000) << (length - 25)
                for i in range(length - 24):
                    if remainder & (1 << (length - 1 - i)):
                        remainder ^= poly_shifted >> i
                return remainder & 0xFFFFFF

        The bit-by-bit form processes each of the top (length - 24) data
        bits individually, aligning the polynomial at the current bit and
        XORing it in when the bit is set. The byte-at-a-time form is about
        4.5x faster on 112-bit messages and ~4x on 56-bit ones, and both
        produce identical output (cross-validated over the 12,000-message
        tests/data corpus).
    """
    n_data_bytes = (length - 24) // 8
    crc = 0
    shift = length - 8
    for _ in range(n_data_bytes):
        byte = (n >> shift) & 0xFF
        crc = ((crc << 8) & 0xFFFFFF) ^ _CRC_TABLE[((crc >> 16) ^ byte) & 0xFF]
        shift -= 8
    parity = n & 0xFFFFFF
    return (crc ^ parity) & 0xFFFFFF
