"""Bit-extraction primitives for Mode-S message decoding.

Every Mode-S message is represented internally as a Python integer
holding the full 56 or 112 bits (short vs long format). Bit positions
are measured from the MSB: bit 0 is the leftmost (most significant)
bit of the message.

This module provides three primitives used by every decoder:

- extract_field(n, start, width, total_bits) — unsigned field extraction
- extract_signed(n, start, width, total_bits) — signed (two's complement) extraction
- crc_remainder(n, length) — 24-bit Mode-S CRC computation
"""

from __future__ import annotations


def extract_field(n: int, start: int, width: int, total_bits: int) -> int:
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
        >>> extract_field(msg, 0, 5, 112)   # DF (bits 0-4)
        17
        >>> extract_field(msg, 8, 24, 112)  # ICAO (bits 8-31)
        4221840
    """
    shift = total_bits - start - width
    return (n >> shift) & ((1 << width) - 1)


def extract_signed(n: int, start: int, width: int, total_bits: int) -> int:
    """Extract `width` bits as a signed two's-complement integer.

    Same bit-positioning semantics as extract_field, but interprets the
    MSB of the extracted value as a sign bit.

    Args:
        n: The Mode-S message as a Python int.
        start: 0-indexed bit position from the MSB.
        width: Number of bits (must be >= 2 to carry a sign bit).
        total_bits: Total width of the source integer.

    Returns:
        Signed integer in [-2**(width-1), 2**(width-1) - 1].
    """
    raw = extract_field(n, start, width, total_bits)
    sign_bit = 1 << (width - 1)
    if raw & sign_bit:
        raw -= 1 << width
    return raw


# Mode-S CRC-24 polynomial: x^24 + x^23 + x^22 + x^21 + x^20 + x^19 + x^18 +
#                           x^17 + x^16 + x^15 + x^14 + x^13 + x^12 + x^10 +
#                           x^3 + 1
# This is the polynomial used for both ADS-B (DF17/18) and Comm-B (DF20/21).
# Per ICAO Annex 10 Vol IV §3.1.2.6; full 25-bit representation: 0x1FFF409
_CRC_POLY = 0x1FFF409


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
    """
    # The CRC is computed over (length - 24) data bits; the trailing 24 bits
    # are the parity field. We align the polynomial so its MSB matches the
    # current highest data bit, XOR it in, and shift right.
    remainder = n
    poly_shifted = _CRC_POLY << (length - 25)
    for i in range(length - 24):
        if remainder & (1 << (length - 1 - i)):
            remainder ^= poly_shifted >> i
    return remainder & 0xFFFFFF
