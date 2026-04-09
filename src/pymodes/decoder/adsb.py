"""ADSB — decoder for DF17/18 extended squitter (ADS-B).

DF17 is emitted by Mode-S transponders equipped with ADS-B Out; DF18 is
the "non-transponder" variant used by ADS-R, TIS-B, and surface
vehicles. Both share the same 112-bit layout and the same ME field
format:

    bits 0-4:    DF (5)
    bits 5-7:    CA/CF (capability / control field, 3)
    bits 8-31:   ICAO (24)
    bits 32-87:  ME -- the ADS-B payload (56)
    bits 88-111: CRC (24)

The 5-bit typecode at ME bits 0-4 (message bits 32-36) selects the
BDS register that defines the rest of the ME layout. The ADSB class
dispatches on typecode via the _ADSB_DISPATCH table, which is
pre-expanded from the human-editable _ADSB_RANGES list at module
import time.

Each BDS decoder is a module-level function
decode_bdsXX(me: int) -> dict[str, Any] operating on the 56-bit ME
field as a Python int. Bit positions inside the BDS functions are
0-indexed from the MSB of the ME field, matching the BDS register
spec layout.
"""

from collections.abc import Callable
from typing import Any

from pymodes.decoder import register
from pymodes.decoder._base import DecoderBase
from pymodes.decoder.bds import bds05, bds06, bds08, bds09
from pymodes.message import Decoded


def _not_implemented_bds61(me: int) -> dict[str, Any]:
    raise NotImplementedError("bds61 decoder not yet implemented")


def _not_implemented_bds62(me: int) -> dict[str, Any]:
    raise NotImplementedError("bds62 decoder not yet implemented")


def _not_implemented_bds65(me: int) -> dict[str, Any]:
    raise NotImplementedError("bds65 decoder not yet implemented")


# Human-editable range table. Each row is (typecode_set, bds_code, decoder_fn).
_ADSB_RANGES: list[tuple[set[int] | range, str, Callable[..., dict[str, Any]]]] = [
    (range(1, 5), "0,8", bds08.decode_bds08),
    (range(5, 9), "0,6", bds06.decode_bds06),
    (range(9, 19), "0,5", bds05.decode_bds05),
    ({19}, "0,9", bds09.decode_bds09),
    (range(20, 23), "0,5", bds05.decode_bds05),
    ({28}, "6,1", _not_implemented_bds61),
    ({29}, "6,2", _not_implemented_bds62),
    ({31}, "6,5", _not_implemented_bds65),
]


# Pre-expanded at module load time for O(1) lookup.
_ADSB_DISPATCH: dict[int, tuple[str, Callable[..., dict[str, Any]]]] = {
    tc: (bds, decoder) for tc_set, bds, decoder in _ADSB_RANGES for tc in tc_set
}


@register(17, 18)
class ADSB(DecoderBase):
    """Decoder for DF17 (extended squitter) and DF18 (non-transponder ADS-B)."""

    def decode(self) -> Decoded:
        # TC is at ME bits 0-4 (top 5 bits of the 56-bit ME int).
        tc = (self._me >> 51) & 0x1F
        result: Decoded = Decoded({"typecode": tc})

        entry = _ADSB_DISPATCH.get(tc)
        if entry is None:
            # Reserved / unknown typecode -- return just {typecode: tc}
            # so callers can still see the TC without crashing.
            return result

        bds_code, decoder = entry
        result["bds"] = bds_code

        # BDS05 needs tc to distinguish barometric (TC 9-18) vs
        # GNSS altitude (TC 20-22).
        if bds_code == "0,5":
            result.update(decoder(self._me, tc=tc))
        else:
            result.update(decoder(self._me))

        return result
