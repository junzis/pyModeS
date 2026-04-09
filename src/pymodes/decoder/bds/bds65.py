"""BDS 6,5 -- ADS-B Aircraft Operational Status (TC=31).

Subtypes by ADS-B version:
- v0 (DO-260): only subtype 0 (airborne) is defined; surface BDS65
  did not exist.
- v1 (DO-260A) and v2 (DO-260B): subtype 0 (airborne) and
  subtype 1 (surface) are both defined.

BDS65 is complicated. The field layout differs substantially across
ADS-B versions, and the sub-field breakdown of the capability_class
(bits 8-23) and operational_mode (bits 24-39) regions depends on
both subtype and version. Plan 2 ships a minimal, robust decoder
that extracts the reliably-positioned fields and exposes
capability_class / operational_mode as raw 16-bit ints.

TODO (deferred): full version-aware sub-field breakdown of
capability_class and operational_mode (ACAS/CDTI/ARV/TS/TC for
airborne, POE/1090ES/GRND/UATin/NACv/NICc for surface, GPS antenna
offset and L/W codes for surface, GVA, BAI, and per-version NIC
supplement variants). See jet1090 crates/rs1090/src/decode/bds/
bds65.rs for the full reference structure. Will land in a follow-up
once captured vectors for each (version, subtype) combination are
available.

ME field layout (always-extracted bits, common across versions):
    bits 0-4:    TC (= 31)
    bits 5-7:    subtype
    bits 8-23:   capability class codes (16 bits, raw; sub-fields TODO)
    bits 24-39:  operational mode codes (16 bits, raw; sub-fields TODO)
    bits 40-42:  ADS-B version (3 bits)
    bit 43:      NIC supplement A
    bits 44-47:  NAC_p (4 bits)
    bits 48-49:  reserved / GVA (2 bits, TODO)
    bits 50-51:  SIL (2 bits)
    bit 52:      NIC_baro -- airborne subtype 0 AND version >= 1 only.
                 (Note: NIC_baro also appears in BDS62 at ME bit 43
                 with no version gating -- the two fields are
                 independent.)
    bit 53:      HRD (heading reference direction: 0 = true north,
                 1 = magnetic north)
    bit 54:      SIL supplement -- ADS-B v2 only
    bit 55:      reserved
"""

from typing import Any


def decode_bds65(me: int) -> dict[str, Any]:
    """Decode a BDS 6,5 ME field (ADS-B operational status).

    Args:
        me: The 56-bit ME field as an integer.

    Returns:
        Dict with subtype, version, nic_supplement_a, nac_p, sil,
        hrd, capability_class (raw 16-bit), operational_mode (raw
        16-bit). Also emits nic_baro when subtype == 0 AND version
        >= 1, and sil_supplement when version == 2.
    """
    subtype = (me >> 48) & 0x7  # bits 5-7

    capability_class = (me >> 32) & 0xFFFF  # bits 8-23
    operational_mode = (me >> 16) & 0xFFFF  # bits 24-39
    version = (me >> 13) & 0x7  # bits 40-42
    nic_supplement_a = (me >> 12) & 0x1  # bit 43
    nac_p = (me >> 8) & 0xF  # bits 44-47
    sil = (me >> 4) & 0x3  # bits 50-51
    hrd = (me >> 2) & 0x1  # bit 53

    result: dict[str, Any] = {
        "subtype": subtype,
        "version": version,
        "nic_supplement_a": nic_supplement_a,
        "nac_p": nac_p,
        "sil": sil,
        "hrd": hrd,
        "capability_class": capability_class,
        "operational_mode": operational_mode,
    }

    # NIC_baro: airborne only, and only for ADS-B v1 and v2.
    # For v0, bit 52 has a different meaning; for surface subtype,
    # the bit is reserved or carries a track/heading flag (TODO).
    if subtype == 0 and version >= 1:
        result["nic_baro"] = (me >> 3) & 0x1

    # SIL supplement is only defined for ADS-B v2
    if version == 2:
        result["sil_supplement"] = (me >> 1) & 0x1

    return result
