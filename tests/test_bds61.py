"""Tests for pyModeS.decoder.bds.bds61 — ADS-B aircraft status (BDS 6,1)."""

from pyModeS import decode


class TestBds61Emergency:
    def test_no_emergency_from_v2_corpus(self):
        # From v2 test_adsb_emergency:
        # "8DA2C1B6E112B600000000760759" → not emergency, state=0, squawk=6513
        result = decode("8DA2C1B6E112B600000000760759")
        assert result["df"] == 17
        assert result["typecode"] == 28
        assert result["bds"] == "6,1"
        assert result["subtype"] == 1
        assert result["emergency_state"] == 0
        assert result["squawk"] == "6513"

    def test_subtype_field_present(self):
        result = decode("8DA2C1B6E112B600000000760759")
        assert result["subtype"] == 1
