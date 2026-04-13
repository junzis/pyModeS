"""BDS 0,5 -- ADS-B airborne position.

Two typecode ranges:
- TC 9-18: barometric altitude (from the 12-bit altcode)
- TC 20-22: GNSS altitude (12-bit integer meters converted to feet)

Payload layout (56 bits, 0-indexed from MSB of payload):
    bits 0-4:    TC
    bits 5-6:    SS (surveillance status)
    bit 7:       NIC_B (ADS-B v1/v2) or SAF (single antenna flag, v0)
    bits 8-19:   AC (12-bit altitude code)
    bit 20:      T (time sync bit)
    bit 21:      F (CPR format: 0 = even, 1 = odd)
    bits 22-38:  CPR latitude (17 bits, raw)
    bits 39-55:  CPR longitude (17 bits, raw)

CPR lat/lon resolution from an even/odd frame pair is handled by
:mod:`pyModeS.position._cpr`; this decoder exposes the raw 17-bit
CPR fields as ints and leaves the pair-matching to callers.
"""

from typing import Any

from pyModeS._altcode import altcode_to_altitude
from pyModeS._uncertainty import TC_NUCp_lookup


def decode_bds05(payload: int, *, tc: int) -> dict[str, Any]:
    """Decode a BDS 0,5 payload (ADS-B airborne position).

    Args:
        payload: The 56-bit payload as an integer.
        tc: The ADS-B typecode (9-18 for barometric, 20-22 for GNSS).
            Passed in by the ADSB class dispatcher because the altitude
            encoding differs across the two ranges.

    Returns:
        Dict with altitude, surveillance_status, nic_b, cpr_format,
        cpr_lat, cpr_lon, nuc_p.
    """
    ss = (payload >> 49) & 0x3  # bits 5-6
    nic_b = (payload >> 48) & 0x1  # bit 7
    ac = (payload >> 36) & 0xFFF  # bits 8-19 (12 bits)
    cpr_format = (payload >> 34) & 0x1  # bit 21
    cpr_lat = (payload >> 17) & 0x1FFFF  # bits 22-38 (17 bits)
    cpr_lon = payload & 0x1FFFF  # bits 39-55 (17 bits)

    altitude: int | None
    if 9 <= tc <= 18:
        # Barometric altitude: insert a zero M bit at position 6 of
        # the 13-bit altcode. Top 6 bits of AC (positions 0-5) shift
        # left by 7; the M bit at position 6 is 0; bottom 6 bits of
        # AC (positions 6-11) become altcode bits 7-12.
        altcode = ((ac >> 6) << 7) | (ac & 0x3F)
        altitude = altcode_to_altitude(altcode)
    elif 20 <= tc <= 22:
        # GNSS altitude: 12-bit integer meters converted to feet
        altitude = int(ac * 3.28084)
    else:
        altitude = None

    return {
        "altitude": altitude,
        "surveillance_status": ss,
        "nic_b": nic_b,
        "cpr_format": cpr_format,
        "cpr_lat": cpr_lat,
        "cpr_lon": cpr_lon,
        "nuc_p": TC_NUCp_lookup.get(tc, 0),
    }
