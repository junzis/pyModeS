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
