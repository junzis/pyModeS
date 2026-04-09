"""Surv — decoder for DF4 (altitude) and DF5 (identity) replies.

Short 56-bit surveillance replies elicited by ground-station
interrogations. Both carry the same header fields (FS, DR, UM);
DF4's payload is the altitude code, DF5's is the identity (squawk) code.

Layout:
    [DF: 5][FS: 3][DR: 5][UM: 6][AC/ID: 13][AP: 24]
"""

from pymodes._altcode import altcode_to_altitude
from pymodes._idcode import idcode_to_squawk
from pymodes.decoder import register
from pymodes.decoder._base import DecoderBase
from pymodes.message import Decoded

_FLIGHT_STATUS_TEXT = {
    0: "No alert, no SPI, airborne",
    1: "No alert, no SPI, on ground",
    2: "Alert, no SPI, airborne",
    3: "Alert, no SPI, on ground",
    4: "Alert, SPI, airborne or on ground",
    5: "No alert, SPI, airborne or on ground",
    6: "Reserved",
    7: "Reserved",
}


@register(4, 5)
class Surv(DecoderBase):
    """Decoder for DF4 surveillance altitude replies and DF5 identity replies."""

    def decode(self) -> Decoded:
        result: Decoded = Decoded()

        # Flight status: bits 5-7
        fs = self._extract(5, 3)
        result["flight_status"] = fs
        result["flight_status_text"] = _FLIGHT_STATUS_TEXT.get(fs, "Unknown")

        # Downlink request: bits 8-12
        result["downlink_request"] = self._extract(8, 5)

        # Utility message: bits 13-18
        result["utility_message"] = self._extract(13, 6)

        # Altitude code (DF4) or identity code (DF5): bits 19-31
        ac_or_id = self._extract(19, 13)

        if self._df == 4:
            result["altitude"] = altcode_to_altitude(ac_or_id)
        else:  # DF5
            result["squawk"] = idcode_to_squawk(ac_or_id)

        return result
