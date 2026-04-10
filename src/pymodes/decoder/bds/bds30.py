"""BDS 3,0 — ACAS Active Resolution Advisory.

Per ICAO Annex 10 Vol IV §4.3.8.4.2.4. This register carries the
active Resolution Advisory (RA) state of the ACAS II unit, including
the ARA bits (what RA is currently issued), the RAC bits (resolution
advisory complement — which manoeuvres the aircraft must NOT take),
and the identity of the threat.

MB field layout (56 bits, 0-indexed from the MSB of MB):
    bits  0- 7 : BDS identifier (fixed 0x30)
    bit   8    : ARA[0] — any RA active (issued_ra)
    bit   9    : ARA[1] — corrective
    bit  10    : ARA[2] — downward sense
    bit  11    : ARA[3] — increased rate
    bit  12    : ARA[4] — sense reversal
    bit  13    : ARA[5] — altitude crossing
    bit  14    : ARA[6] — positive
    bits 15-21 : ARA reserved for ACAS III (7 bits, value must be < 48 per v2 heuristic)
    bit  22    : RAC[0] — no below
    bit  23    : RAC[1] — no above
    bit  24    : RAC[2] — no left
    bit  25    : RAC[3] — no right
    bit  26    : RA terminated
    bit  27    : multiple threat encounter
    bits 28-29 : TTI — threat type indicator (0=none, 1=ICAO, 2=alt+range+brg)
    bits 30-55 : TID — threat identity data, format depends on TTI

TID format:
- TTI=0: no threat identity; TID bits are unused.
- TTI=1: bits 30-53 = 24-bit ICAO; bits 54-55 = reserved zero.
- TTI=2: bits 30-42 = 13-bit AC13 altitude code (decoded via altcode_to_altitude);
         bits 43-49 = 7-bit range raw n (NM = (n-1)/10 if n > 0 else None);
         bits 50-55 = 6-bit bearing raw n (degrees = 6*(n-1)+3 if n > 0 else None).

v2 has no field-level decoder for BDS30 (only the `is30` validator).
This module adds a full decoder aligned with jet1090 because BDS61
subtype 2 (ADS-B ACAS RA broadcast) embeds the same structure and
will consume this decoder in Plan 3 Task 12.
"""

from typing import Any

from pymodes._altcode import altcode_to_altitude


def is_bds30(mb: int) -> bool:
    """Return True if `mb` is a plausible BDS 3,0 ACAS RA report."""
    if mb == 0:
        return False

    # BDS identifier must be 0x30.
    if (mb >> 48) & 0xFF != 0x30:
        return False

    # ARA reserved-for-ACAS-III field (7 bits, MB 15-21) must be < 48
    # per v2's heuristic (spec leaves these bits for future ACAS III use).
    ara_reserved = (mb >> (55 - 21)) & 0x7F
    if ara_reserved >= 48:
        return False

    # TTI (MB bits 28-29) must not be 0b11 (reserved value).
    tti = (mb >> (55 - 29)) & 0x3
    return tti != 0b11


def decode_bds30(mb: int) -> dict[str, Any]:
    """Decode a BDS 3,0 ACAS Active RA report.

    Assumes `is_bds30(mb)` is True. The returned dict always contains
    the ARA/RAC flags plus `threat_type_indicator`. When TTI=1 the
    dict also contains `threat_icao`; when TTI=2 it contains
    `threat_altitude`, `threat_range`, `threat_bearing` (some of which
    may be None if the raw field indicates "not available").
    """
    result: dict[str, Any] = {
        "threat_type_indicator": (mb >> (55 - 29)) & 0x3,
        "issued_ra": bool((mb >> (55 - 8)) & 0x1),
        "corrective": bool((mb >> (55 - 9)) & 0x1),
        "downward_sense": bool((mb >> (55 - 10)) & 0x1),
        "increased_rate": bool((mb >> (55 - 11)) & 0x1),
        "sense_reversal": bool((mb >> (55 - 12)) & 0x1),
        "altitude_crossing": bool((mb >> (55 - 13)) & 0x1),
        "positive": bool((mb >> (55 - 14)) & 0x1),
        "no_below": bool((mb >> (55 - 22)) & 0x1),
        "no_above": bool((mb >> (55 - 23)) & 0x1),
        "no_left": bool((mb >> (55 - 24)) & 0x1),
        "no_right": bool((mb >> (55 - 25)) & 0x1),
        "ra_terminated": bool((mb >> (55 - 26)) & 0x1),
        "multiple_threat": bool((mb >> (55 - 27)) & 0x1),
    }

    tti = result["threat_type_indicator"]

    if tti == 1:
        # 24-bit ICAO at bits 30-53 (24 bits). Shift = 55 - 53 = 2.
        icao_int = (mb >> 2) & 0xFFFFFF
        result["threat_icao"] = f"{icao_int:06X}"
    elif tti == 2:
        # Altitude: 13-bit AC13 at bits 30-42. Shift = 55 - 42 = 13.
        ac13 = (mb >> 13) & 0x1FFF
        result["threat_altitude"] = altcode_to_altitude(ac13)

        # Range: 7-bit at bits 43-49. Shift = 55 - 49 = 6.
        range_raw = (mb >> 6) & 0x7F
        result["threat_range"] = (range_raw - 1) / 10 if range_raw > 0 else None

        # Bearing: 6-bit at bits 50-55. Shift = 0.
        bearing_raw = mb & 0x3F
        result["threat_bearing"] = (
            6 * (bearing_raw - 1) + 3 if bearing_raw > 0 else None
        )

    return result
