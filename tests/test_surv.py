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


class TestV2VectorSurvey:
    """Plan 5 Task 3: real-world vectors lifted from pyModeS v2.21.1's
    tests/test_surv.py. The v2 tests call the low-level surv.altitude /
    surv.fs / surv.um / surv.identity helpers on these hexes; v3 goes
    through pymodes.decode(). These are the only live DF4/DF5 vectors
    v2 shipped, so we keep them as a coverage anchor here.
    """

    def test_v2_df4_altitude_36000(self):
        # v2: surv.altitude("20001718029FCD") == 36000
        result = decode("20001718029FCD")
        assert result["df"] == 4
        assert result["altitude"] == 36000

    def test_v2_df4_utility_message_iis9_ids1(self):
        # v2: surv.um("200CBE4ED80137") == (IIS=9, IDS=1, "Comm-B ...")
        # v3 stores the raw 6-bit UM field; IIS occupies the top 4 bits
        # and IDS the low 2, so 9 << 2 | 1 == 37.
        result = decode("200CBE4ED80137")
        assert result["df"] == 4
        assert result["downlink_request"] == 1
        assert result["utility_message"] == (9 << 2) | 1

    def test_v2_df5_identity_0356(self):
        # v2: surv.fs(...)==2, surv.dr(...)==0, surv.identity(...)=="0356"
        result = decode("2A00516D492B80")
        assert result["df"] == 5
        assert result["flight_status"] == 2
        assert result["downlink_request"] == 0
        assert result["squawk"] == "0356"
