"""Tests for pymodes.decoder.surv — DF4/5 surveillance replies."""

from pymodes import decode
from pymodes._bits import crc_remainder


def _build_surv_msg(header: int, icao: int) -> str:
    """Helper: compute parity for a synthetic 56-bit surveillance reply.

    header: the top 32 bits (DF/FS/DR/UM/AC-or-ID) already shifted
        into the top-32-bits position of a 56-bit int (i.e., `<< 24`).
    icao: the target ICAO address the CRC should decode to.
    Returns the 14-character hex string of the full 56-bit message.
    """
    crc0 = crc_remainder(header, 56)
    parity = crc0 ^ icao
    n_full = header | parity
    return f"{n_full:014X}"


class TestDf4Altitude:
    def test_df4_returns_df_4(self):
        # DF=4 (00100) in top 5 bits, FS=DR=UM=0, AC=0x1030 (→ 25000 ft)
        header = 0x20001030 << 24
        msg = _build_surv_msg(header, icao=0x400940)
        result = decode(msg)
        assert result["df"] == 4
        assert result["icao"] == "400940"

    def test_df4_includes_altitude(self):
        header = 0x20001030 << 24
        msg = _build_surv_msg(header, icao=0x400940)
        result = decode(msg)
        assert result["altitude"] == 25000

    def test_df4_includes_flight_status(self):
        # FS=2: top byte = 00100 010 = 0x22
        header = 0x22001030 << 24
        msg = _build_surv_msg(header, icao=0x400940)
        result = decode(msg)
        assert result["flight_status"] == 2
        assert "alert" in result["flight_status_text"].lower()
        assert "airborne" in result["flight_status_text"].lower()

    def test_df4_zero_altitude_code(self):
        # AC = 0 → altitude unknown
        header = 0x20000000 << 24
        msg = _build_surv_msg(header, icao=0x400940)
        result = decode(msg)
        assert result["df"] == 4
        assert result["altitude"] is None


class TestDf5Identity:
    def test_df5_returns_df_5(self):
        # DF=5 (00101) in top 5 bits, FS=DR=UM=0, ID=0x0808 (squawk 1200)
        header = 0x28000808 << 24
        msg = _build_surv_msg(header, icao=0x400940)
        result = decode(msg)
        assert result["df"] == 5

    def test_df5_includes_squawk(self):
        header = 0x28000808 << 24
        msg = _build_surv_msg(header, icao=0x400940)
        result = decode(msg)
        assert result["squawk"] == "1200"

    def test_df5_hijack_squawk(self):
        # Squawk 7500 = 0x0AA2
        header = 0x28000AA2 << 24
        msg = _build_surv_msg(header, icao=0x400940)
        result = decode(msg)
        assert result["squawk"] == "7500"
