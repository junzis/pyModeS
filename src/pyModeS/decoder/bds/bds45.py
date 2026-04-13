"""BDS 4,5 — Meteorological Hazard Report (MHR).

Per ICAO Doc 9871 Table A-2-32. MHR reports in-flight weather
hazards (turbulence, wind shear, microburst, icing, wake vortex)
plus temperature, pressure, and radio height at the aircraft.
Like BDS 4,4 it is treated as a heuristic slow-path register.

Payload layout (56 bits, 0-indexed from payload MSB):
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

Temperature is only decoded when its status bit (payload bit 15) is
set, following the ICAO spec and jet1090. pyModeS 2.x had a bug
where it decoded temperature unconditionally.
"""

from typing import Any

from pyModeS.decoder.bds._helpers import signed, wrong_status


def is_bds45(payload: int) -> bool:
    """Return True if `payload` is a plausible BDS 4,5 MHR."""
    if payload == 0:
        return False

    # Reserved bits 51-55 must all be zero.
    if (payload & 0x1F) != 0:
        return False

    # Status-bit consistency checks for all 8 gated fields.
    if wrong_status(payload, 0, 1, 2):  # turbulence
        return False
    if wrong_status(payload, 3, 4, 2):  # wind shear
        return False
    if wrong_status(payload, 6, 7, 2):  # microburst
        return False
    if wrong_status(payload, 9, 10, 2):  # icing
        return False
    if wrong_status(payload, 12, 13, 2):  # wake vortex
        return False
    if wrong_status(payload, 15, 16, 10):  # temperature (sign + 9-bit magnitude)
        return False
    if wrong_status(payload, 26, 27, 11):  # static pressure
        return False
    if wrong_status(payload, 38, 39, 12):  # radio height
        return False

    # Temperature range check (only when status bit is 1).
    if (payload >> (55 - 15)) & 0x1:
        temp_sign = (payload >> (55 - 16)) & 0x1
        temp_mag = (payload >> (55 - 25)) & 0x1FF
        temp_c = signed(temp_mag, 9, temp_sign) * 0.25
        if temp_c < -80.0 or temp_c > 60.0:
            return False

    return True


def decode_bds45(payload: int) -> dict[str, Any]:
    """Decode a BDS 4,5 Meteorological Hazard Report payload."""
    result: dict[str, Any] = {}

    if (payload >> (55 - 0)) & 0x1:
        result["turbulence"] = (payload >> (55 - 2)) & 0x3
    if (payload >> (55 - 3)) & 0x1:
        result["wind_shear"] = (payload >> (55 - 5)) & 0x3
    if (payload >> (55 - 6)) & 0x1:
        result["microburst"] = (payload >> (55 - 8)) & 0x3
    if (payload >> (55 - 9)) & 0x1:
        result["icing"] = (payload >> (55 - 11)) & 0x3
    if (payload >> (55 - 12)) & 0x1:
        result["wake_vortex"] = (payload >> (55 - 14)) & 0x3

    # Temperature — honour the status bit at payload bit 15 (v3 bug
    # fix vs v2).
    if (payload >> (55 - 15)) & 0x1:
        temp_sign = (payload >> (55 - 16)) & 0x1
        temp_mag = (payload >> (55 - 25)) & 0x1FF
        result["static_air_temperature"] = signed(temp_mag, 9, temp_sign) * 0.25

    if (payload >> (55 - 26)) & 0x1:
        result["static_pressure"] = (payload >> (55 - 37)) & 0x7FF

    if (payload >> (55 - 38)) & 0x1:
        result["radio_height"] = ((payload >> (55 - 50)) & 0xFFF) * 16

    return result
