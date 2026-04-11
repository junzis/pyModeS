"""Tests for pyModeS.decoder.allcall — DF11 all-call reply."""

from pyModeS import decode


class TestDf11Basic:
    def test_decode_returns_df_11(self):
        # Synthetic DF11 (CA=5, ICAO=4CA2D4, placeholder PI).
        # Top byte: 01011 101 = 0x5D
        msg = "5D4CA2D4000000"
        result = decode(msg)
        assert result["df"] == 11

    def test_decode_includes_icao(self):
        msg = "5D4CA2D4000000"
        result = decode(msg)
        assert result["icao"] == "4CA2D4"

    def test_decode_includes_capability(self):
        msg = "5D4CA2D4000000"  # CA=5 in the top byte
        result = decode(msg)
        assert result["capability"] == 5
        assert result["capability_text"] == "Level 2+, airborne"

    def test_capability_zero(self):
        # CA=0 → byte 0 = 01011 000 = 0x58
        msg = "584CA2D4000000"
        result = decode(msg)
        assert result["capability"] == 0
        assert result["capability_text"] == "Level 1"

    def test_capability_on_ground(self):
        # CA=4 → byte 0 = 01011 100 = 0x5C
        msg = "5C4CA2D4000000"
        result = decode(msg)
        assert result["capability"] == 4
        assert result["capability_text"] == "Level 2+, on-ground"

    def test_capability_either(self):
        # CA=6 → byte 0 = 01011 110 = 0x5E
        msg = "5E4CA2D4000000"
        result = decode(msg)
        assert result["capability"] == 6
        assert result["capability_text"] == "Level 2+, airborne or on-ground"

    def test_capability_fs_or_dr_nonzero(self):
        # CA=7 → byte 0 = 01011 111 = 0x5F
        msg = "5F4CA2D4000000"
        result = decode(msg)
        assert result["capability"] == 7
        assert "DR" in result["capability_text"] or "FS" in result["capability_text"]

    def test_reserved_capability(self):
        # CA=1 → byte 0 = 01011 001 = 0x59
        msg = "594CA2D4000000"
        result = decode(msg)
        assert result["capability"] == 1
        assert result["capability_text"] == "Reserved"


class TestV2VectorSurvey:
    """Plan 5 Task 3: vector lifted from pyModeS v2.21.1's
    tests/test_allcall.py. v2 asserts icao=="484FDE", capability==5,
    and interrogator()=="SI6". v3 decodes the ICAO and capability;
    the II/SI interrogator code decode is intentionally deferred
    (see pyModeS._pipe comment on DF11 trust-set exclusion).
    """

    def test_v2_df11_icao_484fde(self):
        result = decode("5D484FDEA248F5")
        assert result["df"] == 11
        assert result["icao"] == "484FDE"
        assert result["capability"] == 5
        assert result["capability_text"] == "Level 2+, airborne"
