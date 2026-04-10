"""BDS 6,2 -- ADS-B Target State and Status (TC=29).

Only one format is currently defined (the DO-260B Target State and
Status message). The 2-bit subtype field (payload bits 5-6) is
emitted as an informational field but we do not branch on it --
matching jet1090's single-struct approach. DO-260A subtype 0 and
reserved values 2/3 are parsed with the same layout; callers can
ignore the result if the subtype value is unexpected.

Payload layout (56 bits, 0-indexed from MSB) per DO-260B
section 2.2.3.2.7.1, cross-checked against
jet1090/crates/rs1090/src/decode/bds/bds62.rs:

    bits 0-4:    TC (= 29)
    bits 5-6:    subtype (informational; DO-260B compliant = 1)
    bit 7:       SIL supplement (reserved; not decoded)
    bit 8:       selected altitude source (0 = MCP/FCU, 1 = FMS)
    bits 9-19:   selected altitude (11 bits; 0 = N/A; (raw-1)*32 ft)
    bits 20-28:  baro pressure setting (9 bits; 0 = N/A; 800+(raw-1)*0.8 mbar)
    bit 29:      selected heading status
    bits 30-38:  selected heading (9 bits; raw * 360/512 deg)
    bits 39-42:  NAC_p (4 bits)
    bit 43:      NIC_baro
    bits 44-45:  SIL (2 bits)
    bit 46:      mode status (gates autopilot/vnav/alt-hold/approach/lnav)
    bit 47:      autopilot engaged
    bit 48:      VNAV mode
    bit 49:      altitude hold mode
    bit 50:      IMF / ADS-R flag (reserved)
    bit 51:      approach mode
    bit 52:      TCAS operational (always valid, not gated by mode status)
    bit 53:      LNAV mode
    bits 54-55:  reserved
"""

from typing import Any


def decode_bds62(payload: int) -> dict[str, Any]:
    """Decode a BDS 6,2 payload (ADS-B target state and status).

    Args:
        payload: The 56-bit payload as an integer.

    Returns:
        Dict with subtype and the full set of DO-260B Target State
        and Status fields.
    """
    result: dict[str, Any] = {"subtype": (payload >> 49) & 0x3}  # bits 5-6

    # Selected altitude source at bit 8, value at bits 9-19 (11 bits).
    alt_source_bit = (payload >> 47) & 0x1
    alt_raw = (payload >> 36) & 0x7FF
    if alt_raw == 0:
        result["selected_altitude"] = None
        result["selected_altitude_source"] = "N/A"
    else:
        result["selected_altitude"] = (alt_raw - 1) * 32
        result["selected_altitude_source"] = "FMS" if alt_source_bit == 1 else "MCP/FCU"

    # Barometric pressure setting at bits 20-28 (9 bits).
    baro_raw = (payload >> 27) & 0x1FF
    if baro_raw == 0:
        result["baro_pressure_setting"] = None
    else:
        result["baro_pressure_setting"] = 800 + (baro_raw - 1) * 0.8

    # Selected heading: status bit at 29, 9-bit value at bits 30-38.
    # Equivalent formulation: raw * 360/512 (our choice) or
    # raw * 180/256 (jet1090); mathematically identical.
    hdg_status = (payload >> 26) & 0x1
    hdg_raw = (payload >> 17) & 0x1FF
    if hdg_status == 0:
        result["selected_heading"] = None
    else:
        result["selected_heading"] = hdg_raw * 360 / 512

    # Navigation integrity / accuracy fields.
    result["nac_p"] = (payload >> 13) & 0xF  # bits 39-42
    result["nic_baro"] = (payload >> 12) & 0x1  # bit 43
    result["sil"] = (payload >> 10) & 0x3  # bits 44-45

    # Mode status bit (bit 46) gates the five autopilot/nav flags.
    # TCAS operational (bit 52) is always valid regardless.
    mode_status = (payload >> 9) & 0x1
    if mode_status == 0:
        result["autopilot"] = None
        result["vnav_mode"] = None
        result["altitude_hold_mode"] = None
        result["approach_mode"] = None
        result["lnav_mode"] = None
    else:
        result["autopilot"] = bool((payload >> 8) & 0x1)  # bit 47
        result["vnav_mode"] = bool((payload >> 7) & 0x1)  # bit 48
        result["altitude_hold_mode"] = bool((payload >> 6) & 0x1)  # bit 49
        result["approach_mode"] = bool((payload >> 4) & 0x1)  # bit 51
        result["lnav_mode"] = bool((payload >> 2) & 0x1)  # bit 53

    result["tcas_operational"] = bool((payload >> 3) & 0x1)  # bit 52

    return result
