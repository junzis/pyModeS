"""BDS 5,0 — Track and Turn Report.

Per ICAO Doc 9871 Table A-2-34. Heading/track/roll/speed snapshot
reported by the flight management system. Every field has a status
bit; unreliable fields are absent from the output dict.

MB field layout (56 bits, 0-indexed from MB MSB):
    bit   0    : roll angle status
    bit   1    : roll angle sign bit
    bits  2-10 : roll angle magnitude (9 bits, scale 45/256 deg, signed by bit 1)
    bit  11    : true track status
    bit  12    : true track sign bit
    bits 13-22 : true track (10 bits, scale 90/512 deg, signed by bit 12,
                 result normalised to [0, 360))
    bit  23    : groundspeed status
    bits 24-33 : groundspeed (10 bits, scale 2 = kt)
    bit  34    : track angle rate status
    bit  35    : track angle rate sign bit
    bits 36-44 : track angle rate (9 bits, scale 8/256 deg/s, signed by bit 35)
    bit  45    : true airspeed status
    bits 46-55 : true airspeed (10 bits, scale 2 = kt)

Validator range checks:
    |roll| <= 50 deg
    groundspeed <= 600 kt
    true_airspeed <= 600 kt
    |true_airspeed - groundspeed| <= 200 kt when both present
"""

from typing import Any

from pymodes.decoder.bds._helpers import normalise_angle, signed


def is_bds50(mb: int) -> bool:
    """Return True if `mb` is a plausible BDS 5,0 Track and Turn Report."""
    if mb == 0:
        return False

    # Decode each field (without sign handling) to range-check.
    roll_status = (mb >> (55 - 0)) & 0x1
    roll_sign = (mb >> (55 - 1)) & 0x1
    roll_mag = (mb >> (55 - 10)) & 0x1FF

    track_status = (mb >> (55 - 11)) & 0x1
    track_sign = (mb >> (55 - 12)) & 0x1
    track_raw = (mb >> (55 - 22)) & 0x3FF

    gs_status = (mb >> (55 - 23)) & 0x1
    gs_raw = (mb >> (55 - 33)) & 0x3FF

    rtrk_status = (mb >> (55 - 34)) & 0x1
    rtrk_sign = (mb >> (55 - 35)) & 0x1
    rtrk_mag = (mb >> (55 - 44)) & 0x1FF

    tas_status = (mb >> (55 - 45)) & 0x1
    tas_raw = (mb >> (55 - 55)) & 0x3FF

    # wrongstatus checks (status = 0 but value field != 0).
    # Roll: v2 uses msb=3 which skips the sign bit; we include the
    # sign bit in our check because a status=0 sign=1 MB is suspicious.
    if roll_status == 0 and (roll_sign or roll_mag):
        return False
    if track_status == 0 and (track_sign or track_raw):
        return False
    if gs_status == 0 and gs_raw:
        return False
    if rtrk_status == 0 and (rtrk_sign or rtrk_mag):
        return False
    if tas_status == 0 and tas_raw:
        return False

    # Range checks (only for fields whose status is 1).
    if roll_status:
        roll_deg = signed(roll_mag, 9, roll_sign) * 45.0 / 256.0
        if abs(roll_deg) > 50.0:
            return False

    if gs_status:
        gs_kt = gs_raw * 2
        if gs_kt > 600:
            return False

    if tas_status:
        tas_kt = tas_raw * 2
        if tas_kt > 600:
            return False

    return not (gs_status and tas_status and abs(tas_raw * 2 - gs_raw * 2) > 200)


def decode_bds50(mb: int) -> dict[str, Any]:
    """Decode a BDS 5,0 Track and Turn Report."""
    result: dict[str, Any] = {}

    if (mb >> (55 - 0)) & 0x1:
        sign = (mb >> (55 - 1)) & 0x1
        mag = (mb >> (55 - 10)) & 0x1FF
        result["roll"] = signed(mag, 9, sign) * 45.0 / 256.0

    if (mb >> (55 - 11)) & 0x1:
        sign = (mb >> (55 - 12)) & 0x1
        raw = (mb >> (55 - 22)) & 0x3FF
        deg = signed(raw, 10, sign) * 90.0 / 512.0
        result["true_track"] = normalise_angle(deg)

    if (mb >> (55 - 23)) & 0x1:
        result["groundspeed"] = ((mb >> (55 - 33)) & 0x3FF) * 2

    if (mb >> (55 - 34)) & 0x1:
        sign = (mb >> (55 - 35)) & 0x1
        mag = (mb >> (55 - 44)) & 0x1FF
        result["track_rate"] = signed(mag, 9, sign) * 8.0 / 256.0

    if (mb >> (55 - 45)) & 0x1:
        result["true_airspeed"] = ((mb >> (55 - 55)) & 0x3FF) * 2

    return result
