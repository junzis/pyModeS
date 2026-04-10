"""BDS 6,0 — Heading and Speed Report.

Per ICAO Doc 9871 Table A-2-35. Reports magnetic heading, indicated
airspeed, Mach number, and vertical rates (barometric and inertial)
from the air data computer.

MB field layout (56 bits, 0-indexed from MB MSB):
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

from pymodes.decoder.bds._helpers import normalise_angle, signed


def is_bds60(mb: int) -> bool:
    """Return True if `mb` is a plausible BDS 6,0 Heading and Speed Report."""
    if mb == 0:
        return False

    hdg_status = (mb >> (55 - 0)) & 0x1
    hdg_sign = (mb >> (55 - 1)) & 0x1
    hdg_raw = (mb >> (55 - 11)) & 0x3FF

    ias_status = (mb >> (55 - 12)) & 0x1
    ias_raw = (mb >> (55 - 22)) & 0x3FF

    mach_status = (mb >> (55 - 23)) & 0x1
    mach_raw = (mb >> (55 - 33)) & 0x3FF

    vrb_status = (mb >> (55 - 34)) & 0x1
    vrb_sign = (mb >> (55 - 35)) & 0x1
    vrb_mag = (mb >> (55 - 44)) & 0x1FF

    vri_status = (mb >> (55 - 45)) & 0x1
    vri_sign = (mb >> (55 - 46)) & 0x1
    vri_mag = (mb >> (55 - 55)) & 0x1FF

    # wrongstatus checks.
    if hdg_status == 0 and (hdg_sign or hdg_raw):
        return False
    if ias_status == 0 and ias_raw:
        return False
    if mach_status == 0 and mach_raw:
        return False
    if vrb_status == 0 and (vrb_sign or vrb_mag):
        return False
    if vri_status == 0 and (vri_sign or vri_mag):
        return False

    # Range checks.
    if ias_status and ias_raw > 500:
        return False

    if mach_status and (mach_raw * 2.048 / 512.0) > 1.0:
        return False

    if vrb_status and abs(signed(vrb_mag, 9, vrb_sign) * 32) > 6000:
        return False

    return not (vri_status and abs(signed(vri_mag, 9, vri_sign) * 32) > 6000)


def decode_bds60(mb: int) -> dict[str, Any]:
    """Decode a BDS 6,0 Heading and Speed Report."""
    result: dict[str, Any] = {}

    if (mb >> (55 - 0)) & 0x1:
        sign = (mb >> (55 - 1)) & 0x1
        raw = (mb >> (55 - 11)) & 0x3FF
        deg = signed(raw, 10, sign) * 90.0 / 512.0
        result["magnetic_heading"] = normalise_angle(deg)

    if (mb >> (55 - 12)) & 0x1:
        result["indicated_airspeed"] = (mb >> (55 - 22)) & 0x3FF

    if (mb >> (55 - 23)) & 0x1:
        result["mach"] = ((mb >> (55 - 33)) & 0x3FF) * 2.048 / 512.0

    if (mb >> (55 - 34)) & 0x1:
        sign = (mb >> (55 - 35)) & 0x1
        mag = (mb >> (55 - 44)) & 0x1FF
        result["baro_vertical_rate"] = signed(mag, 9, sign) * 32

    if (mb >> (55 - 45)) & 0x1:
        sign = (mb >> (55 - 46)) & 0x1
        mag = (mb >> (55 - 55)) & 0x1FF
        result["inertial_vertical_rate"] = signed(mag, 9, sign) * 32

    return result
