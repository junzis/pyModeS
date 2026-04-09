"""BDS 0,9 -- ADS-B airborne velocity (TC=19).

Four subtypes share a common header and trailer but differ in the
middle 22 bits:

- Subtype 1: subsonic ground speed (N/S, E/W velocity components, kt)
- Subtype 2: supersonic ground speed (4x scale)
- Subtype 3: subsonic airspeed (heading + IAS/TAS)
- Subtype 4: supersonic airspeed (4x scale)

ME field layout (56 bits, 0-indexed from MSB of the ME field):

    bits 0-4:    TC (= 19)
    bits 5-7:    subtype (1-4)
    bit 8:       intent change flag
    bit 9:       IFR capability flag
    bits 10-12:  NAC_v

  Subtypes 1 & 2 (ground speed):
    bit 13:      v_ew direction (0 = east, 1 = west)
    bits 14-23:  v_ew magnitude (10 bits, value - 1 = actual)
    bit 24:      v_ns direction (0 = north, 1 = south)
    bits 25-34:  v_ns magnitude (10 bits, value - 1 = actual)

  Subtypes 3 & 4 (airspeed):
    bit 13:      heading status (1 = valid)
    bits 14-23:  heading (10 bits, raw * 360/1024 deg)
    bit 24:      airspeed type (0 = IAS, 1 = TAS)
    bits 25-34:  airspeed (10 bits, value - 1 = actual)

  Common trailer:
    bit 35:      vertical-rate source (0 = GNSS, 1 = barometric)
    bit 36:      vertical-rate sign (0 = climb, 1 = descent)
    bits 37-45:  vertical-rate magnitude (9 bits, (value - 1) * 64 ft/min)
    bits 46-47:  reserved
    bit 48:      GNSS-minus-baro sign
    bits 49-55:  GNSS-minus-baro magnitude (7 bits, (value - 1) * 25 ft)
"""

import math
from typing import Any


def decode_bds09(me: int) -> dict[str, Any]:
    """Decode a BDS 0,9 ME field (ADS-B airborne velocity, TC=19).

    Args:
        me: The 56-bit ME field as an integer.

    Returns:
        Dict with subtype plus subtype-specific fields and the common
        trailer (vr_source, vertical_rate, geo_minus_baro, nac_v).
    """
    subtype = (me >> 48) & 0x7  # bits 5-7
    nac_v = (me >> 43) & 0x7  # bits 10-12

    result: dict[str, Any] = {
        "subtype": subtype,
        "nac_v": nac_v,
    }

    if subtype in (1, 2):
        result.update(_decode_ground_speed(me, subtype))
    elif subtype in (3, 4):
        result.update(_decode_air_speed(me, subtype))

    # Common trailer
    vr_source = (me >> 20) & 0x1  # bit 35
    vr_sign = (me >> 19) & 0x1  # bit 36
    vr_mag = (me >> 10) & 0x1FF  # bits 37-45
    result["vr_source"] = "BARO" if vr_source == 1 else "GNSS"
    if vr_mag == 0:
        result["vertical_rate"] = None
    else:
        sign = -1 if vr_sign == 1 else 1
        result["vertical_rate"] = int(sign * (vr_mag - 1) * 64)

    # GNSS minus baro altitude diff: bit 48 sign, bits 49-55 magnitude
    diff_sign = (me >> 7) & 0x1
    diff_mag = me & 0x7F  # bits 49-55
    if diff_mag == 0 or diff_mag == 127:
        result["geo_minus_baro"] = None
    else:
        sign = -1 if diff_sign == 1 else 1
        result["geo_minus_baro"] = int(sign * (diff_mag - 1) * 25)

    return result


def _decode_ground_speed(me: int, subtype: int) -> dict[str, Any]:
    """Subtype 1 (subsonic) or 2 (supersonic) ground-speed decoding."""
    v_ew_sign = (me >> 42) & 0x1  # bit 13
    v_ew_mag = (me >> 32) & 0x3FF  # bits 14-23
    v_ns_sign = (me >> 31) & 0x1  # bit 24
    v_ns_mag = (me >> 21) & 0x3FF  # bits 25-34

    if v_ew_mag == 0 or v_ns_mag == 0:
        # Not available
        return {
            "groundspeed": None,
            "track": None,
        }

    v_ew = v_ew_mag - 1
    v_ns = v_ns_mag - 1
    if subtype == 2:  # supersonic
        v_ew *= 4
        v_ns *= 4

    # East is positive; sign bit of 1 means westward (negative)
    v_we = -v_ew if v_ew_sign == 1 else v_ew
    # North is positive; sign bit of 1 means southward (negative)
    v_sn = -v_ns if v_ns_sign == 1 else v_ns

    spd = int(math.sqrt(v_we * v_we + v_sn * v_sn))

    trk = math.degrees(math.atan2(v_we, v_sn))
    if trk < 0:
        trk += 360

    return {
        "groundspeed": spd,
        "track": trk,
    }


def _decode_air_speed(me: int, subtype: int) -> dict[str, Any]:
    """Subtype 3 (subsonic) or 4 (supersonic) airspeed decoding."""
    hdg_status = (me >> 42) & 0x1  # bit 13
    hdg_raw = (me >> 32) & 0x3FF  # bits 14-23
    as_type = (me >> 31) & 0x1  # bit 24
    as_mag = (me >> 21) & 0x3FF  # bits 25-34

    heading: float | None = None if hdg_status == 0 else hdg_raw / 1024 * 360.0

    airspeed: int | None
    if as_mag == 0:
        airspeed = None
    elif subtype == 4:
        airspeed = (as_mag - 1) * 4
    else:
        airspeed = as_mag - 1

    return {
        "airspeed": airspeed,
        "heading": heading,
        "airspeed_type": "TAS" if as_type == 1 else "IAS",
    }
