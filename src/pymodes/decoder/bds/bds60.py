"""BDS 6,0 — Heading and Speed Report.

Per ICAO Doc 9871 Table A-2-35. Reports magnetic heading, indicated
airspeed, Mach number, and vertical rates (barometric and inertial)
from the air data computer.

Payload layout (56 bits, 0-indexed from payload MSB):
    bit   0    : magnetic heading status
    bit   1    : magnetic heading sign bit
    bits  2-11 : magnetic heading (10 bits, scale 90/512 deg,
                 signed by bit 1, normalised to [0, 360))
    bit  12    : indicated airspeed status
    bits 13-22 : indicated airspeed (10 bits, unsigned, kt)
    bit  23    : mach status
    bits 24-33 : mach (10 bits, unsigned, scale 2.048/512)
    bit  34    : barometric vertical rate status
    bit  35    : barometric vertical rate sign bit
    bits 36-44 : baro vertical rate (9 bits, scale 32 ft/min, signed by bit 35)
    bit  45    : inertial vertical rate status
    bit  46    : inertial vertical rate sign bit
    bits 47-55 : inertial vertical rate (9 bits, scale 32 ft/min, signed by bit 46)

Validator range checks:
    indicated_airspeed <= 500 kt
    mach <= 1
    |baro_vertical_rate| <= 6000 ft/min
    |inertial_vertical_rate| <= 6000 ft/min

The v2 DF20-specific altitude-based IAS-vs-Mach cross-check is NOT
implemented — it requires access to the full Mode-S header from the
message, which would add coupling for marginal inference gain.
"""

from typing import Any

from pymodes.decoder.bds._helpers import normalise_angle, signed, wrong_status


def is_bds60(payload: int) -> bool:
    """Return True if `payload` is a plausible BDS 6,0 Heading and Speed Report."""
    if payload == 0:
        return False

    # wrongstatus checks. Widths include sign bits where present, so
    # e.g. the heading check spans payload bits 1-11 (sign + 10-bit raw).
    if wrong_status(payload, 0, 1, 11):  # heading: sign + 10-bit raw
        return False
    if wrong_status(payload, 12, 13, 10):  # indicated airspeed: 10-bit raw
        return False
    if wrong_status(payload, 23, 24, 10):  # mach: 10-bit raw
        return False
    if wrong_status(payload, 34, 35, 10):  # baro vertical rate: sign + 9-bit mag
        return False
    if wrong_status(payload, 45, 46, 10):  # inertial vertical rate: sign + 9-bit mag
        return False

    # Decode fields needed for range checks.
    ias_status = (payload >> (55 - 12)) & 0x1
    ias_raw = (payload >> (55 - 22)) & 0x3FF

    mach_status = (payload >> (55 - 23)) & 0x1
    mach_raw = (payload >> (55 - 33)) & 0x3FF

    vrb_status = (payload >> (55 - 34)) & 0x1
    vrb_sign = (payload >> (55 - 35)) & 0x1
    vrb_mag = (payload >> (55 - 44)) & 0x1FF

    vri_status = (payload >> (55 - 45)) & 0x1
    vri_sign = (payload >> (55 - 46)) & 0x1
    vri_mag = (payload >> (55 - 55)) & 0x1FF

    # Range checks.
    if ias_status and ias_raw > 500:
        return False

    if mach_status and (mach_raw * 2.048 / 512.0) > 1.0:
        return False

    if vrb_status and abs(signed(vrb_mag, 9, vrb_sign) * 32) > 6000:
        return False

    return not (vri_status and abs(signed(vri_mag, 9, vri_sign) * 32) > 6000)


def decode_bds60(payload: int) -> dict[str, Any]:
    """Decode a BDS 6,0 Heading and Speed Report."""
    result: dict[str, Any] = {}

    if (payload >> (55 - 0)) & 0x1:
        sign = (payload >> (55 - 1)) & 0x1
        raw = (payload >> (55 - 11)) & 0x3FF
        deg = signed(raw, 10, sign) * 90.0 / 512.0
        result["magnetic_heading"] = normalise_angle(deg)

    if (payload >> (55 - 12)) & 0x1:
        result["indicated_airspeed"] = (payload >> (55 - 22)) & 0x3FF

    if (payload >> (55 - 23)) & 0x1:
        result["mach"] = ((payload >> (55 - 33)) & 0x3FF) * 2.048 / 512.0

    if (payload >> (55 - 34)) & 0x1:
        sign = (payload >> (55 - 35)) & 0x1
        mag = (payload >> (55 - 44)) & 0x1FF
        result["baro_vertical_rate"] = signed(mag, 9, sign) * 32

    if (payload >> (55 - 45)) & 0x1:
        sign = (payload >> (55 - 46)) & 0x1
        mag = (payload >> (55 - 55)) & 0x1FF
        result["inertial_vertical_rate"] = signed(mag, 9, sign) * 32

    return result
