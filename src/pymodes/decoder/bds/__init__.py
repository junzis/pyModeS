"""BDS register decoders for ADS-B (DF17/18) and Comm-B (DF20/21).

Each module implements a single `decode_bdsXX(me: int) -> dict[str, Any]`
function that operates on the 56-bit ME (ADS-B) or MB (Comm-B) field
as a Python int. Bit positions are 0-indexed from the MSB of the 56-bit
payload, matching the BDS register spec layout.

Plan 2 adds the ADS-B set: bds05, bds06, bds08, bds09, bds61, bds62,
bds65. Plan 3 adds the Comm-B set: bds10, bds17, bds20, bds30, bds40,
bds44, bds45, bds50, bds60.
"""
