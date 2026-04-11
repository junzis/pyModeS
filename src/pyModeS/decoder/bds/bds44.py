"""BDS 4,4 — Meteorological Routine Air Report (MRAR).

Per ICAO Doc 9871 Table A-2-33. MRAR is a pilot-optional downlink
that reports wind, temperature, pressure, turbulence, and humidity
at the aircraft's current position. Because it is optional and
shares bit patterns with other registers, v2 treats BDS44 as a
heuristic register in infer() — only tried when `include_meteo=True`.

Payload layout (56 bits, 0-indexed from payload MSB):
    bits  0- 3 : figure of merit (4 bits, validator: <= 4)
    bit   4    : wind status
    bits  5-13 : wind speed (9 bits, kt)
    bits 14-22 : wind direction (9 bits, scale 180/256 = 0.703125 deg)
    bit  23    : static air temperature sign
    bits 24-33 : temperature (10 bits, scale 0.25 deg C, signed by bit 23,
                 unconditional — no status bit gate per v2)
    bit  34    : static pressure status
    bits 35-45 : static pressure (11 bits, hPa raw)
    bit  46    : turbulence status
    bits 47-48 : turbulence (2 bits: 0=NIL, 1=Light, 2=Mod, 3=Severe)
    bit  49    : humidity status
    bits 50-55 : humidity (6 bits, scale 100/64 = %)
"""

from typing import Any

from pyModeS.decoder.bds._helpers import signed, wrong_status


def is_bds44(payload: int) -> bool:
    """Return True if `payload` is a plausible BDS 4,4 MRAR."""
    if payload == 0:
        return False

    # FOM sanity: must be 0..4 inclusive.
    fom = (payload >> (55 - 3)) & 0xF
    if fom > 4:
        return False

    # Wind must be present (v2 heuristic).
    wind_status = (payload >> (55 - 4)) & 0x1
    if wind_status == 0:
        return False

    # Status/value consistency for pressure, turbulence, humidity.
    if wrong_status(payload, 34, 35, 11):  # static pressure
        return False
    if wrong_status(payload, 46, 47, 2):  # turbulence
        return False
    if wrong_status(payload, 49, 50, 6):  # humidity
        return False

    wind_speed = (payload >> (55 - 13)) & 0x1FF
    wind_dir_raw = (payload >> (55 - 22)) & 0x1FF
    temp_sign = (payload >> (55 - 23)) & 0x1
    temp_raw = (payload >> (55 - 33)) & 0x3FF

    # Wind speed range.
    if wind_speed > 250:
        return False

    # Temperature unconditional range [-80, 60] deg C.
    temp_signed = temp_raw - 1024 if temp_sign else temp_raw
    temp_c = temp_signed * 0.25
    if temp_c < -80.0 or temp_c > 60.0:
        return False

    # Reject all-zero meteorological data (wind speed == 0 AND
    # wind dir == 0 AND temp == 0).
    return not (wind_speed == 0 and wind_dir_raw == 0 and temp_raw == 0)


def decode_bds44(payload: int) -> dict[str, Any]:
    """Decode a BDS 4,4 MRAR payload."""
    result: dict[str, Any] = {
        "figure_of_merit": (payload >> (55 - 3)) & 0xF,
    }

    if (payload >> (55 - 4)) & 0x1:
        result["wind_speed"] = (payload >> (55 - 13)) & 0x1FF
        result["wind_direction"] = ((payload >> (55 - 22)) & 0x1FF) * (180.0 / 256.0)

    # Temperature is unconditional per v2 (the status bit at payload
    # bit 23 is actually the sign bit in this layout).
    temp_sign = (payload >> (55 - 23)) & 0x1
    temp_raw = (payload >> (55 - 33)) & 0x3FF
    result["static_air_temperature"] = signed(temp_raw, 10, temp_sign) * 0.25

    if (payload >> (55 - 34)) & 0x1:
        result["static_pressure"] = (payload >> (55 - 45)) & 0x7FF

    if (payload >> (55 - 46)) & 0x1:
        result["turbulence"] = (payload >> (55 - 48)) & 0x3

    if (payload >> (55 - 49)) & 0x1:
        result["humidity"] = ((payload >> (55 - 55)) & 0x3F) * (100.0 / 64.0)

    return result
