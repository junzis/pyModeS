"""BDS 4,5 — Meteorological Hazard Report (MHR).

Per ICAO Doc 9871 Table A-2-32. MHR reports in-flight weather
hazards (turbulence, wind shear, microburst, icing, wake vortex)
plus temperature, pressure, and radio height at the aircraft.
Like BDS 4,4 it is treated as a heuristic slow-path register.

MB field layout (56 bits, 0-indexed from MB MSB):
    bit   0    : turbulence status
    bits  1- 2 : turbulence level (0=nil..3=severe)
    bit   3    : wind shear status
    bits  4- 5 : wind shear level
    bit   6    : microburst status
    bits  7- 8 : microburst level
    bit   9    : icing status
    bits 10-11 : icing level
    bit  12    : wake vortex status
    bits 13-14 : wake vortex level
    bit  15    : static air temperature status  (v3 bug fix: honour this bit)
    bit  16    : temperature sign
    bits 17-25 : temperature magnitude (9 bits, signed by bit 16, scale 0.25 deg C)
    bit  26    : static pressure status
    bits 27-37 : static pressure (11 bits, hPa raw)
    bit  38    : radio height status
    bits 39-50 : radio height (12 bits, scale 16 ft)
    bits 51-55 : reserved (must be zero)

v2 has a bug where temperature was decoded regardless of the status
bit at MB 15. v3 respects the status bit — this is Decision D for
Plan 3, aligning with jet1090 and the ICAO spec.
"""

from typing import Any

from pymodes.decoder.bds._helpers import signed, wrong_status


def is_bds45(mb: int) -> bool:
    """Return True if `mb` is a plausible BDS 4,5 MHR."""
    if mb == 0:
        return False

    # Reserved bits 51-55 must all be zero.
    if (mb & 0x1F) != 0:
        return False

    # Status-bit consistency checks for all 8 gated fields.
    if wrong_status(mb, 0, 1, 2):  # turbulence
        return False
    if wrong_status(mb, 3, 4, 2):  # wind shear
        return False
    if wrong_status(mb, 6, 7, 2):  # microburst
        return False
    if wrong_status(mb, 9, 10, 2):  # icing
        return False
    if wrong_status(mb, 12, 13, 2):  # wake vortex
        return False
    if wrong_status(mb, 15, 16, 10):  # temperature (sign + 9-bit magnitude)
        return False
    if wrong_status(mb, 26, 27, 11):  # static pressure
        return False
    if wrong_status(mb, 38, 39, 12):  # radio height
        return False

    # Temperature range check (only when status bit is 1).
    if (mb >> (55 - 15)) & 0x1:
        temp_sign = (mb >> (55 - 16)) & 0x1
        temp_mag = (mb >> (55 - 25)) & 0x1FF
        temp_c = signed(temp_mag, 9, temp_sign) * 0.25
        if temp_c < -80.0 or temp_c > 60.0:
            return False

    return True


def decode_bds45(mb: int) -> dict[str, Any]:
    """Decode a BDS 4,5 Meteorological Hazard Report MB field."""
    result: dict[str, Any] = {}

    if (mb >> (55 - 0)) & 0x1:
        result["turbulence"] = (mb >> (55 - 2)) & 0x3
    if (mb >> (55 - 3)) & 0x1:
        result["wind_shear"] = (mb >> (55 - 5)) & 0x3
    if (mb >> (55 - 6)) & 0x1:
        result["microburst"] = (mb >> (55 - 8)) & 0x3
    if (mb >> (55 - 9)) & 0x1:
        result["icing"] = (mb >> (55 - 11)) & 0x3
    if (mb >> (55 - 12)) & 0x1:
        result["wake_vortex"] = (mb >> (55 - 14)) & 0x3

    # Temperature — honour the status bit at MB 15 (v3 bug fix vs v2).
    if (mb >> (55 - 15)) & 0x1:
        temp_sign = (mb >> (55 - 16)) & 0x1
        temp_mag = (mb >> (55 - 25)) & 0x1FF
        result["static_air_temperature"] = signed(temp_mag, 9, temp_sign) * 0.25

    if (mb >> (55 - 26)) & 0x1:
        result["static_pressure"] = (mb >> (55 - 37)) & 0x7FF

    if (mb >> (55 - 38)) & 0x1:
        result["radio_height"] = ((mb >> (55 - 50)) & 0xFFF) * 16

    return result
