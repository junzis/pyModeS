"""Tests for pyModeS.decoder.bds.bds05 — ADS-B airborne position (BDS 0,5)."""

from pyModeS import decode
from pyModeS.decoder.bds.bds05 import decode_bds05  # noqa: F401


class TestBds05Altitude:
    def test_altitude_39000_from_v2_corpus(self):
        # Golden from v2 test_adsb_alt:
        # "8D40058B58C901375147EFD09357" → altitude 39000
        result = decode("8D40058B58C901375147EFD09357")
        assert result["df"] == 17
        assert result["typecode"] == 11
        assert result["bds"] == "0,5"
        assert result["altitude"] == 39000

    def test_altitude_negative_and_boundary(self):
        # From v2 test_adsb_altitude_negative_and_small
        cases = [
            ("8d484fde5803b647ecec4fcdd74f", -325),
            ("8d4845575803c647bcec2a980abc", -300),
            ("8d3424d25803d64c18ee03351f89", -275),
            ("8d4401e458058645a8ea90496290", 0),
            ("8d346355580596459cea86756acc", 25),
            ("8d346355580b064116e70a269f97", 1000),
            ("8d343386581f06318ad4fecab734", 5000),
        ]
        for msg, expected in cases:
            result = decode(msg)
            assert result["altitude"] == expected, (
                f"msg={msg} expected {expected}, got {result['altitude']}"
            )


class TestBds05CprFields:
    def test_cpr_fields_present(self):
        result = decode("8D40058B58C901375147EFD09357")
        assert "cpr_format" in result
        assert "cpr_lat" in result
        assert "cpr_lon" in result
        assert result["cpr_format"] in (0, 1)
        assert 0 <= result["cpr_lat"] < (1 << 17)
        assert 0 <= result["cpr_lon"] < (1 << 17)

    def test_even_frame(self):
        # "8D40058B58C901375147EFD09357" is the EVEN frame from v2
        # test_adsb_position (pair with ...58C904A87F402D3B8C59)
        result = decode("8D40058B58C901375147EFD09357")
        assert result["cpr_format"] == 0

    def test_odd_frame(self):
        result = decode("8D40058B58C904A87F402D3B8C59")
        assert result["cpr_format"] == 1


class TestBds05Supplements:
    def test_nic_b_present_for_barometric(self):
        # TC 9-18 messages carry a NIC_B bit; expose as `nic_b` (0 or 1)
        result = decode("8D40058B58C901375147EFD09357")
        assert "nic_b" in result
        assert result["nic_b"] in (0, 1)

    def test_nuc_p_present(self):
        # TC=11 → NUCp = 7 (from TC_NUCp_lookup)
        result = decode("8D40058B58C901375147EFD09357")
        assert result["nuc_p"] == 7
