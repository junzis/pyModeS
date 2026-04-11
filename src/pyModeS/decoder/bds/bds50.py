"""BDS 5,0 — Track and Turn Report.

Per ICAO Doc 9871 Table A-2-34. Heading/track/roll/speed snapshot
reported by the flight management system. Every field has a status
bit; unreliable fields are absent from the output dict.

Payload layout (56 bits, 0-indexed from payload MSB):
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

from pyModeS.decoder.bds._helpers import normalise_angle, signed, wrong_status


def is_bds50(payload: int) -> bool:
    """Return True if `payload` is a plausible BDS 5,0 Track and Turn Report."""
    if payload == 0:
        return False

    # wrongstatus checks (status = 0 but value field != 0). The value
    # field widths include the sign bit where present, so e.g. the
    # roll check spans payload bits 1-10 (sign + 9-bit magnitude).
    # This is stricter than v2, which skips the sign bit — a
    # status=0 sign=1 payload is suspicious and we reject it.
    if wrong_status(payload, 0, 1, 10):  # roll: sign + 9-bit magnitude
        return False
    if wrong_status(payload, 11, 12, 11):  # true track: sign + 10-bit raw
        return False
    if wrong_status(payload, 23, 24, 10):  # groundspeed: 10-bit raw
        return False
    if wrong_status(payload, 34, 35, 10):  # track rate: sign + 9-bit magnitude
        return False
    if wrong_status(payload, 45, 46, 10):  # true airspeed: 10-bit raw
        return False

    # Decode fields needed for range checks.
    roll_status = (payload >> (55 - 0)) & 0x1
    roll_sign = (payload >> (55 - 1)) & 0x1
    roll_mag = (payload >> (55 - 10)) & 0x1FF

    gs_status = (payload >> (55 - 23)) & 0x1
    gs_raw = (payload >> (55 - 33)) & 0x3FF

    tas_status = (payload >> (55 - 45)) & 0x1
    tas_raw = (payload >> (55 - 55)) & 0x3FF

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


def decode_bds50(payload: int) -> dict[str, Any]:
    """Decode a BDS 5,0 Track and Turn Report."""
    result: dict[str, Any] = {}

    if (payload >> (55 - 0)) & 0x1:
        sign = (payload >> (55 - 1)) & 0x1
        mag = (payload >> (55 - 10)) & 0x1FF
        result["roll"] = signed(mag, 9, sign) * 45.0 / 256.0

    if (payload >> (55 - 11)) & 0x1:
        sign = (payload >> (55 - 12)) & 0x1
        raw = (payload >> (55 - 22)) & 0x3FF
        deg = signed(raw, 10, sign) * 90.0 / 512.0
        result["true_track"] = normalise_angle(deg)

    if (payload >> (55 - 23)) & 0x1:
        result["groundspeed"] = ((payload >> (55 - 33)) & 0x3FF) * 2

    if (payload >> (55 - 34)) & 0x1:
        sign = (payload >> (55 - 35)) & 0x1
        mag = (payload >> (55 - 44)) & 0x1FF
        result["track_rate"] = signed(mag, 9, sign) * 8.0 / 256.0

    if (payload >> (55 - 45)) & 0x1:
        result["true_airspeed"] = ((payload >> (55 - 55)) & 0x3FF) * 2

    return result
