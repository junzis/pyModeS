"""CommB — decoder for DF20 (altitude reply) and DF21 (identity reply).

Comm-B replies carry a 56-bit MB (message-B) payload at bits 32-87
of the 112-bit message, preceded by a short header:

    bits 0-4:    DF (20 or 21)
    bits 5-7:    FS  (flight status)
    bits 8-12:   DR  (downlink request)
    bits 13-18:  UM  (utility message)
    bits 19-31:  AC  (altitude code — DF20) or ID (squawk — DF21)
    bits 32-87:  MB  (56-bit BDS register payload)
    bits 88-111: AP  (parity overlaid with ICAO, optionally XORed with
                      a BDS code from the eliciting interrogation)

BDS dispatch is driven by `infer()`: a two-phase scan that checks
format-ID'd registers (1,0 / 1,7 / 2,0 / 3,0) fast, then runs
heuristic validators for 4,0 / 5,0 / 6,0 (and 4,4 / 4,5 when
`include_meteo=True`). The first candidate becomes `bds` in the
result dict; if multiple candidates survive the scan they are also
returned as `bds_candidates`.

During the walking-skeleton phase (before every BDS register is
added), `_COMMB_DISPATCH` is empty and `CommB.decode()` returns only
the header field. Each BDS task extends the dispatch and the result
grows incrementally.
"""

from collections.abc import Callable
from typing import Any

from pymodes._altcode import altcode_to_altitude
from pymodes._idcode import idcode_to_squawk
from pymodes.decoder import register
from pymodes.decoder._base import DecoderBase
from pymodes.decoder.bds import _infer, bds10, bds17, bds20, bds30, bds40
from pymodes.message import Decoded

# BDS code -> decoder. Populated by each BDS task as it lands.
_COMMB_DISPATCH: dict[str, Callable[[int], dict[str, Any]]] = {
    "1,0": bds10.decode_bds10,
    "1,7": bds17.decode_bds17,
    "2,0": bds20.decode_bds20,
    "3,0": bds30.decode_bds30,
    "4,0": bds40.decode_bds40,
}


@register(20, 21)
class CommB(DecoderBase):
    """Decoder for DF20 Comm-B altitude replies and DF21 Comm-B identity replies."""

    def decode(self) -> Decoded:
        result: Decoded = Decoded()

        # Header field: altitude for DF20, squawk for DF21.
        # Both live at bits 19-31 of the full 112-bit message
        # (same slot as DF4/DF5 AC/ID).
        ac_or_id = self._extract(19, 13)
        if self._df == 20:
            result["altitude"] = altcode_to_altitude(ac_or_id)
        else:  # DF21
            result["squawk"] = idcode_to_squawk(ac_or_id)

        # MB payload is already cached as self._me by DecoderBase.
        # Walking-skeleton: the dispatch table is empty in Task 1 and
        # grows one register at a time in Tasks 2-10. Task 11 replaces
        # this inline scan with a call into decoder/bds/_infer.infer().
        for bds_code, decoder in _COMMB_DISPATCH.items():
            if _infer.matches(bds_code, self._me):
                result["bds"] = bds_code
                result.update(decoder(self._me))
                break

        return result
