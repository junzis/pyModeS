"""BDS 0,8 — ADS-B aircraft identification and category (TC=1-4).

ME field layout (56 bits, 0-indexed from MSB):
    bits 0-4:   TC (typecode, 5 bits)
    bits 5-7:   CAT (aircraft category, 3 bits)
    bits 8-55:  CS (callsign, 8 x 6-bit chars)
"""

from typing import Any

from pymodes._callsign import decode_callsign

# Wake vortex / aircraft category strings per ICAO Doc 9871 and
# 1090 MOPS DO-260B Table A-2-8. Keyed by (tc, category).
_WAKE_VORTEX: dict[tuple[int, int], str] = {
    # TC=4 — Set A: heavy / high performance
    (4, 1): "Light",
    (4, 2): "Medium 1",
    (4, 3): "Medium 2",
    (4, 4): "High vortex aircraft",
    (4, 5): "Heavy",
    (4, 6): "High performance",
    (4, 7): "Rotorcraft",
    # TC=3 — Set B: gliders, balloons, parachutists, UAVs
    (3, 1): "Glider / sailplane",
    (3, 2): "Lighter-than-air",
    (3, 3): "Parachutist / skydiver",
    (3, 4): "Ultralight / hang-glider / paraglider",
    (3, 5): "Reserved",
    (3, 6): "UAV",
    (3, 7): "Space / transatmospheric vehicle",
    # TC=2 — Set C: surface vehicles and obstacles
    (2, 1): "Surface emergency vehicle",
    (2, 2): "Reserved",
    (2, 3): "Surface service vehicle",
    (2, 4): "Ground obstacle",
    (2, 5): "Ground obstacle",
    (2, 6): "Ground obstacle",
    (2, 7): "Ground obstacle",
}


def decode_bds08(me: int) -> dict[str, Any]:
    """Decode a BDS 0,8 ME field (ADS-B identification).

    Args:
        me: The 56-bit ME field as an integer.

    Returns:
        A dict with keys: category, callsign, wake_vortex.
    """
    tc = (me >> 51) & 0x1F  # bits 0-4
    category = (me >> 48) & 0x7  # bits 5-7
    # Callsign bits 8-55: bottom 48 bits of the 56-bit ME int.
    cs_bits = me & ((1 << 48) - 1)

    callsign = decode_callsign(cs_bits)
    if category == 0 or tc == 1:
        wake_vortex = "No category information"
    else:
        wake_vortex = _WAKE_VORTEX.get((tc, category), "No category information")

    return {
        "category": category,
        "callsign": callsign,
        "wake_vortex": wake_vortex,
    }
