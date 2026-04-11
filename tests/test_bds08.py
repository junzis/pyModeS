"""Tests for pyModeS.decoder.bds.bds08 — ADS-B identification (BDS 0,8)."""

from pyModeS import decode
from pyModeS.decoder.bds.bds08 import decode_bds08


class TestBds08CallsignAndCategory:
    def test_ezy85mh_from_v2_corpus(self):
        # Golden from v2 test_adsb_callsign + test_adsb_category:
        # msg = "8D406B902015A678D4D220AA4BDA", callsign "EZY85MH "
        # (one trailing space which the decoder strips), category 0
        # payload = msg[8:22] as int
        payload = 0x2015A678D4D220
        result = decode_bds08(payload)
        assert result["callsign"] == "EZY85MH"
        assert result["category"] == 0

    def test_category_no_info_wake_vortex(self):
        # category=0 → "No category information" regardless of TC
        payload = 0x2015A678D4D220  # TC=4, cat=0
        result = decode_bds08(payload)
        assert result["wake_vortex"] == "No category information"


class TestBds08EndToEnd:
    def test_decode_df17_identification_message(self):
        # Full round-trip via pyModeS.decode()
        # NOTE: This test will fail after Task 5 because no ADSB class
        # is registered yet. Task 6 will make it pass.
        result = decode("8D406B902015A678D4D220AA4BDA")
        assert result["df"] == 17
        assert result["icao"] == "406B90"
        assert result["typecode"] == 4
        assert result["bds"] == "0,8"
        assert result["callsign"] == "EZY85MH"
        assert result["category"] == 0
        assert result["wake_vortex"] == "No category information"

    def test_decode_df17_crc_valid(self):
        result = decode("8D406B902015A678D4D220AA4BDA")
        assert result["crc_valid"] is True
