"""Bit-math helpers shared across BDS register decoders.

BDS validators and decoders all operate on a 56-bit MB field as a
Python int, extracting bit-slices with `(mb >> (55 - end)) & mask`.
Several registers share the same post-extraction transformations:

- Separate sign-bit + magnitude encoding (e.g. BDS 5,0 roll, BDS 6,0
  heading) that needs to be reassembled into a signed Python int.
- Angular values in degrees that need wrapping into the half-open
  interval [0, 360).

This module owns those transformations so every BDS register module
can import them by name instead of duplicating the arithmetic. The
module is underscore-prefixed to signal package-private status; no
public API lives here.
"""


def signed(value: int, width: int, sign: int) -> int:
    """Combine an unsigned magnitude and a separate sign bit into a signed int.

    Args:
        value: The unsigned magnitude (0..2**width - 1).
        width: The number of bits the magnitude occupies.
        sign: The sign bit (0 = positive, 1 = negative).

    Returns:
        Positive `value` if `sign == 0`, else `value - 2**width`. For
        width=9 this yields the range [-512, 511]; for width=10 it
        yields [-1024, 1023].

    Note:
        This is NOT standard two's complement — Mode-S encodes sign
        and magnitude in separate bit fields, so `sign=1 magnitude=0`
        represents `-2**width`, not `-0`. Callers depending on v2
        byte-for-byte parity must keep this sign-magnitude convention.
    """
    if sign:
        return value - (1 << width)
    return value


def normalise_angle(deg: float) -> float:
    """Wrap an angle into the half-open interval [0, 360).

    Python's floor-mod handles negatives correctly: `(-180.0) % 360.0
    == 180.0`. Safe for any float argument.
    """
    return deg % 360.0


def wrong_status(mb: int, status_bit: int, value_start: int, value_width: int) -> bool:
    """Return True if a status-gated value field is inconsistent.

    BDS registers with status-bit gates encode each field as a
    status bit followed by a fixed-width value. When the status is
    0, the entire value field (including any sign bit) must also be
    0; a nonzero value with status=0 indicates either a corrupt
    message or a non-BDS-X report that accidentally passed the
    format-ID check.

    Args:
        mb: The 56-bit MB field as a Python int.
        status_bit: 0-indexed position of the status bit from MB MSB.
        value_start: 0-indexed position of the first value bit.
        value_width: Number of bits in the value field (may include
            a sign bit; the whole field is checked for non-zero).

    Returns:
        True if status == 0 and any bit in the value field is set,
        False otherwise.

    Example:
        BDS 4,0 MCP altitude at MB bits 0 (status) and 1-12 (12-bit
        altitude raw): `wrong_status(mb, 0, 1, 12)` returns True when
        the status bit is clear but the altitude bits are not.
    """
    status = (mb >> (55 - status_bit)) & 0x1
    if status != 0:
        return False
    value_shift = 55 - (value_start + value_width - 1)
    value = (mb >> value_shift) & ((1 << value_width) - 1)
    return value != 0
