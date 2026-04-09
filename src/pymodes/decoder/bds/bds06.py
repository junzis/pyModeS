"""BDS 0,6 -- ADS-B surface position (TC 5-8).

No altitude (aircraft is on the ground). Decodes movement (packed
speed), track (with validity flag), and raw CPR lat/lon fields.

ME field layout (56 bits, 0-indexed from MSB):
    bits 0-4:    TC
    bits 5-11:   MOV (movement, 7 bits, packed speed)
    bit 12:      track status (1 = valid)
    bits 13-19:  track (7 bits, raw * 360/128 deg)
    bit 20:      T (time sync)
    bit 21:      F (CPR format: 0 even, 1 odd)
    bits 22-38:  CPR latitude (17 bits, raw)
    bits 39-55:  CPR longitude (17 bits, raw)

Movement decoding (from v2 bds06.surface_velocity):
    mov == 0 or > 124  -> None (no info)
    mov == 1            -> 0.0 (stopped)
    mov == 124          -> 175.0 (max)
    otherwise: piecewise-linear lookup across 6 bins.
"""

from typing import Any

# Movement encoding bins: lower bound, kt at lower bound, step within bin.
_MOV_LB: list[int] = [2, 9, 13, 39, 94, 109, 124]
_KTS_LB: list[float] = [0.125, 1, 2, 15, 70, 100, 175]
_STEP: list[float] = [0.125, 0.25, 0.5, 1, 2, 5]


def _decode_movement(mov: int) -> float | None:
    """Decode the 7-bit movement field to ground speed in knots."""
    if mov == 0 or mov > 124:
        return None
    if mov == 1:
        return 0.0
    if mov == 124:
        return 175.0
    # Find the smallest bin index whose lower bound is > mov
    i = next(idx for idx, lb in enumerate(_MOV_LB) if lb > mov)
    return _KTS_LB[i - 1] + (mov - _MOV_LB[i - 1]) * _STEP[i - 1]


def decode_bds06(me: int) -> dict[str, Any]:
    """Decode a BDS 0,6 ME field (ADS-B surface position).

    Args:
        me: The 56-bit ME field as an integer.

    Returns:
        Dict with movement, groundspeed, track, track_status,
        cpr_format, cpr_lat, cpr_lon.
    """
    mov = (me >> 44) & 0x7F  # bits 5-11
    track_status = (me >> 43) & 0x1  # bit 12
    track_raw = (me >> 36) & 0x7F  # bits 13-19
    cpr_format = (me >> 34) & 0x1  # bit 21
    cpr_lat = (me >> 17) & 0x1FFFF  # bits 22-38
    cpr_lon = me & 0x1FFFF  # bits 39-55

    track: float | None = track_raw * 360 / 128 if track_status == 1 else None

    return {
        "movement": mov,
        "groundspeed": _decode_movement(mov),
        "track": track,
        "track_status": track_status,
        "cpr_format": cpr_format,
        "cpr_lat": cpr_lat,
        "cpr_lon": cpr_lon,
    }
