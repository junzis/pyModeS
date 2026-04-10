"""BDS 4,0 — Selected Vertical Intention.

Per ICAO Doc 9871 Table A-2-31. This register reports the pilot's
selected altitude targets (MCP/FCU and FMS) and the current
barometric pressure setting at the aircraft, plus MCP mode flags
and the target altitude source.

MB field layout (56 bits, 0-indexed from MB MSB):
    bit   0    : MCP/FCU selected altitude status
    bits  1-12 : MCP/FCU selected altitude (12 bits, raw * 16 = ft)
    bit  13    : FMS selected altitude status
    bits 14-25 : FMS selected altitude (12 bits, raw * 16 = ft)
    bit  26    : barometric pressure setting status
    bits 27-38 : barometric pressure setting (12 bits, raw * 0.1 + 800 = mbar)
    bits 39-46 : reserved (must be zero)
    bit  47    : MCP mode bits status
    bit  48    : VNAV mode
    bit  49    : altitude hold mode
    bit  50    : approach mode
    bits 51-52 : reserved (must be zero)
    bit  53    : target altitude source status
    bits 54-55 : target altitude source (0=unknown, 1=aircraft altitude,
                 2=MCP/FCU selected altitude, 3=FMS selected altitude)

Altitude scaling is left raw (value * 16) per our spec decision —
lossless, matches v2. jet1090 rounds to the nearest 100 ft; we do not.
"""

from typing import Any

_ALT_SOURCE = {
    0: "unknown",
    1: "aircraft_altitude",
    2: "mcp_fcu",
    3: "fms",
}


def is_bds40(mb: int) -> bool:
    """Return True if `mb` is a plausible BDS 4,0 report."""
    if mb == 0:
        return False

    # Status-bit consistency: if the status bit is 0, the gated value
    # field must also be 0.
    def wrong(status_bit: int, value_start: int, value_width: int) -> bool:
        status = (mb >> (55 - status_bit)) & 0x1
        value_shift = 55 - (value_start + value_width - 1)
        value = (mb >> value_shift) & ((1 << value_width) - 1)
        return status == 0 and value != 0

    if wrong(0, 1, 12):  # MCP altitude
        return False
    if wrong(13, 14, 12):  # FMS altitude
        return False
    if wrong(26, 27, 12):  # baro pressure
        return False
    if wrong(47, 48, 3):  # MCP mode bits (vnav, alt hold, approach)
        return False
    if wrong(53, 54, 2):  # target altitude source
        return False

    # Reserved bits 39-46 (8 bits) must be zero.
    if ((mb >> (55 - 46)) & 0xFF) != 0:
        return False

    # Reserved bits 51-52 (2 bits) must be zero.
    return ((mb >> (55 - 52)) & 0x3) == 0


def decode_bds40(mb: int) -> dict[str, Any]:
    """Decode a BDS 4,0 Selected Vertical Intention MB field.

    Returns only the fields whose status bits are set. MCP mode bits
    and target altitude source are nested under their status gates.
    """
    result: dict[str, Any] = {}

    if (mb >> (55 - 0)) & 0x1:
        raw = (mb >> (55 - 12)) & 0xFFF
        result["selected_altitude_mcp"] = raw * 16

    if (mb >> (55 - 13)) & 0x1:
        raw = (mb >> (55 - 25)) & 0xFFF
        result["selected_altitude_fms"] = raw * 16

    if (mb >> (55 - 26)) & 0x1:
        raw = (mb >> (55 - 38)) & 0xFFF
        result["baro_pressure_setting"] = raw * 0.1 + 800.0

    if (mb >> (55 - 47)) & 0x1:
        result["vnav_mode"] = bool((mb >> (55 - 48)) & 0x1)
        result["altitude_hold_mode"] = bool((mb >> (55 - 49)) & 0x1)
        result["approach_mode"] = bool((mb >> (55 - 50)) & 0x1)

    if (mb >> (55 - 53)) & 0x1:
        src = (mb >> (55 - 55)) & 0x3
        result["target_altitude_source"] = _ALT_SOURCE[src]

    return result
