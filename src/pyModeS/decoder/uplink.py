"""Mode-S interrogation fields, ported from the v2 uplink decoder.

Uplink formats overlap downlink formats. This decoder is selected explicitly
by ``uplink=True`` and is therefore separate from the downlink registry.
"""

from typing import Any

from pyModeS.decoder._base import DecoderBase
from pyModeS.message import Decoded


def uplink_icao(n: int, length: int) -> str:
    """Recover the address from uplink address/parity using the v2 algorithm.

    Uplink address recovery differs from the downlink CRC remainder. The
    shift register below processes both the data and the received parity.
    """
    polynomial = 0xFFFA0480 << (length - 56)
    data = n >> 24
    parity = n & 0xFFFFFF
    address = 0
    topbit = 1 << (length - 25)
    for j in range(length):
        if data & topbit:
            data ^= polynomial
        data = (data << 1) | ((parity >> 23) & 1)
        parity <<= 1
        if j > length - 26:
            address = (address + ((data >> (length - 25)) & 1)) << 1
    return f"{address >> 2:06X}"


class Uplink(DecoderBase):
    """Decode UF11 all-call and UF4/5/20/21 selective interrogations.

    Other uplink formats return only the common header, as in v2. Requested
    BDS registers use the v3 comma notation, for example ``"2,0"``.
    """

    def decode(self, *, known: dict[str, Any] | None = None) -> Decoded:
        result = Decoded()
        if self._df == 11:
            result["probability_of_reply"] = self._extract(5, 4)
            label = self._extract(13, 3)
            code = self._extract(9, 4)
            if label == 0:
                result["interrogator_code"] = f"II{code}"
            elif label <= 4:
                result["interrogator_code"] = f"SI{code + (label - 1) * 16}"
            else:
                result["interrogator_code"] = None
        elif self._df in (4, 5, 20, 21):
            di = self._extract(13, 3)
            rr = self._extract(8, 5)
            result["designator_identification"] = di
            result["reply_request"] = rr
            result["lockout"] = False
            if di in (0, 1, 7):
                result["interrogator_code"] = f"II{self._extract(16, 4)}"
                if di in (1, 7):
                    result["lockout"] = bool(self._extract(25, 1))
            elif di == 3:
                result["interrogator_code"] = f"SI{self._extract(16, 6)}"
                result["lockout"] = bool(self._extract(22, 1))
            if di == 7:
                result["reply_request_subfield"] = self._extract(20, 4)
            elif di == 3:
                result["reply_request_subfield"] = self._extract(23, 4)
            if rr > 15:
                bds2 = result.get("reply_request_subfield", 0)
                result["bds"] = f"{rr - 16:X},{bds2:X}"
        return result
