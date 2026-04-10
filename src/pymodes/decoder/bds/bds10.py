"""BDS 1,0 — Data Link Capability Report.

Per ICAO Doc 9871 Table A-2-16 and Annex 10 Vol IV §3.1.2.6.10.2.

MB field layout (56 bits, 0-indexed from the MSB of MB):
    bits  0- 7 : BDS identifier (fixed 0x10)
    bit   8    : continuation flag
    bits  9-13 : reserved (must be 0)
    bit  14    : overlay command capability (OVC)
    bit  15    : ACAS operational
    bits 16-22 : Mode S subnetwork version (7 bits)
    bit  23    : transponder level 5 (enhanced protocol)
    bit  24    : Mode S specific services capability
    bits 25-27 : uplink ELM throughput (3 bits)
    bits 28-31 : downlink ELM throughput (4 bits)
    bit  32    : aircraft identification capability
    bit  33    : squitter capability
    bit  34    : surveillance identifier code capability
    bit  35    : common usage GICB capability
    bit  36    : ACAS hybrid surveillance
    bit  37    : ACAS resolution advisory
    bits 38-39 : ACAS RTCA version (2 bits)
    bits 40-55 : DTE status array (16 bits)

Validator rejects all-zero MB, wrong BDS ID, non-zero reserved bits,
and v2's OVC/subnet consistency heuristic: if OVC=1 the subnetwork
version must be >= 5 (spec requires DO-181E for overlay support);
if OVC=0 the version must be <= 4. This heuristic is not in the
ICAO spec but helps inference precision on mixed traffic.
"""

from typing import Any


def is_bds10(mb: int) -> bool:
    """Return True if `mb` is a plausible BDS 1,0 report."""
    if mb == 0:
        return False

    # BDS identifier must be 0x10 (MB bits 0-7).
    if (mb >> 48) & 0xFF != 0x10:
        return False

    # Reserved bits 9-13 must be zero (5 bits, shift = 55 - 13 = 42).
    if (mb >> 42) & 0x1F != 0:
        return False

    # v2 OVC/subnet consistency heuristic.
    ovc = (mb >> 41) & 0x1  # bit 14
    subnet = (mb >> 33) & 0x7F  # bits 16-22 (7 bits, shift = 55 - 22 = 33)
    if ovc == 1 and subnet < 5:
        return False
    return not (ovc == 0 and subnet > 4)


def decode_bds10(mb: int) -> dict[str, Any]:
    """Decode a BDS 1,0 Data Link Capability Report MB field.

    Assumes `is_bds10(mb)` is True. Returns every field in the spec
    as a bool or int; no status-bit gating (all fields are always
    present in the capability report).
    """
    return {
        "config": bool((mb >> 47) & 0x1),  # bit 8
        "overlay_command_capability": bool((mb >> 41) & 0x1),  # bit 14
        "acas_operational": bool((mb >> 40) & 0x1),  # bit 15
        "mode_s_subnetwork_version": (mb >> 33) & 0x7F,  # bits 16-22
        "transponder_level5": bool((mb >> 32) & 0x1),  # bit 23
        "mode_s_specific_services": bool((mb >> 31) & 0x1),  # bit 24
        "uplink_elm_throughput": (mb >> 28) & 0x7,  # bits 25-27
        "downlink_elm_throughput": (mb >> 24) & 0xF,  # bits 28-31
        "aircraft_identification_capability": bool((mb >> 23) & 0x1),  # bit 32
        "squitter_capability": bool((mb >> 22) & 0x1),  # bit 33
        "surveillance_identifier_code": bool((mb >> 21) & 0x1),  # bit 34
        "common_usage_gicb_capability": bool((mb >> 20) & 0x1),  # bit 35
        "acas_hybrid_surveillance": bool((mb >> 19) & 0x1),  # bit 36
        "acas_resolution_advisory": bool((mb >> 18) & 0x1),  # bit 37
        "acas_rtca_version": (mb >> 16) & 0x3,  # bits 38-39
        "dte_status": mb & 0xFFFF,  # bits 40-55
    }
