"""Tests for pyModeS.decoder.acas — DF0/16 air-air surveillance."""

from pyModeS import decode
from pyModeS._bits import crc_remainder


def _build_df0_msg(
    *,
    df: int = 0,
    vs: int = 0,
    cc: int = 0,
    sl: int = 0,
    ri: int = 0,
    ac: int = 0,
    icao: int = 0x400940,
) -> str:
    """Build a synthetic 56-bit DF0 message with correct CRC parity."""
    header = (df << 51) | (vs << 50) | (cc << 49) | (sl << 45) | (ri << 39) | (ac << 24)
    crc0 = crc_remainder(header, 56)
    parity = crc0 ^ icao
    n_full = header | parity
    return f"{n_full:014X}"


def _build_df16_msg(
    *,
    df: int = 16,
    ac: int = 0,
    mv: int = 0,
    icao: int = 0x400940,
) -> str:
    """Build a synthetic 112-bit DF16 message with correct CRC parity.

    Uses only DF and AC from the header (other header fields zero).
    mv is the 56-bit MV payload.
    """
    header_top32 = (df << 27) | ac
    n_without_parity = (header_top32 << 80) | (mv << 24)
    crc0 = crc_remainder(n_without_parity, 112)
    parity = crc0 ^ icao
    n_full = n_without_parity | parity
    return f"{n_full:028X}"


class TestDf0Short:
    def test_df0_returns_df_0(self):
        msg = _build_df0_msg(df=0, vs=0, cc=0, sl=3, ri=2, ac=0x1030)
        result = decode(msg)
        assert result["df"] == 0

    def test_df0_decodes_altitude(self):
        msg = _build_df0_msg(df=0, ac=0x1030)
        result = decode(msg)
        assert result["altitude"] == 25000

    def test_df0_vertical_status_airborne(self):
        msg = _build_df0_msg(vs=0)
        result = decode(msg)
        assert result["vertical_status"] == "airborne"

    def test_df0_vertical_status_on_ground(self):
        msg = _build_df0_msg(vs=1)
        result = decode(msg)
        assert result["vertical_status"] == "on-ground"

    def test_df0_sensitivity_level_and_reply_info(self):
        msg = _build_df0_msg(sl=3, ri=2)
        result = decode(msg)
        assert result["sensitivity_level"] == 3
        assert result["reply_information"] == 2


class TestDf16Long:
    def test_df16_returns_df_16(self):
        msg = _build_df16_msg(df=16, ac=0x1030)
        result = decode(msg)
        assert result["df"] == 16

    def test_df16_decodes_altitude(self):
        msg = _build_df16_msg(df=16, ac=0x1030)
        result = decode(msg)
        assert result["altitude"] == 25000

    def test_df16_has_mv_field(self):
        # Full 56-bit MV payload of all 1s
        mv = 0xFFFFFFFFFFFFFF  # 14 hex F's = 56 bits
        msg = _build_df16_msg(df=16, ac=0x1030, mv=mv)
        result = decode(msg)
        assert "mv" in result
        assert result["mv"] == "FFFFFFFFFFFFFF"
