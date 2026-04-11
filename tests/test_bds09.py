"""Tests for pyModeS.decoder.bds.bds09 — ADS-B airborne velocity (BDS 0,9, TC=19)."""

from pyModeS import decode
from pyModeS.decoder.bds.bds09 import decode_bds09  # noqa: F401


class TestBds09GroundSpeed:
    def test_subtype1_subsonic_gs(self):
        # Golden from v2 test_adsb_velocity:
        # "8D485020994409940838175B284F" → (159, 182.88, -832, "GS")
        # altitude_diff = 550
        result = decode("8D485020994409940838175B284F")
        assert result["df"] == 17
        assert result["typecode"] == 19
        assert result["bds"] == "0,9"
        assert result["subtype"] == 1
        assert result["groundspeed"] == 159
        assert abs(result["track"] - 182.88) < 0.1
        assert result["vertical_rate"] == -832
        assert result["vr_source"] == "GNSS"
        assert result["geo_minus_baro"] == 550


class TestBds09AirSpeed:
    def test_subtype3_airspeed_tas(self):
        # Golden from v2 test_adsb_velocity:
        # "8DA05F219B06B6AF189400CBC33F" → (375, 243.98, -2304, "TAS")
        result = decode("8DA05F219B06B6AF189400CBC33F")
        assert result["typecode"] == 19
        assert result["subtype"] == 3
        assert result["airspeed"] == 375
        assert abs(result["heading"] - 243.98) < 0.1
        assert result["vertical_rate"] == -2304
        assert result["airspeed_type"] == "TAS"

    def test_subtype3_heading_zero_regression(self):
        # Regression from v2 test_airborne_velocity_subtype3_heading_zero:
        # Subtype 3 airspeed message with heading=0° must decode, not be
        # dropped by the ground-speed zero-guard.
        result = decode("8D4841409B04000CA04400000000")
        assert result["airspeed"] == 100
        assert result["heading"] == 0.0
        assert result["vertical_rate"] == 1024
        assert result["airspeed_type"] == "IAS"


class TestBds09VerticalRateSignBits:
    def test_vertical_rates_from_v2_corpus(self):
        # From v2 test_adsb_vertical_rate_sign_bits
        cases = [
            ("8d3461cf9908388930080f948ea1", +64),
            ("8d3461cf9908558e100c1071eb67", +128),
            ("8d3461cf99085a8f10400f80e6ac", +960),
            ("8d394c0f990c4932780838866883", -64),
        ]
        for msg, expected_vr in cases:
            result = decode(msg)
            assert result["vertical_rate"] == expected_vr, (
                f"msg={msg} expected {expected_vr}, got {result['vertical_rate']}"
            )


class TestBds09NacV:
    def test_nac_v_present(self):
        # NAC_v is at ME bits 10-12. Just assert it's an int in [0,7].
        result = decode("8D485020994409940838175B284F")
        assert "nac_v" in result
        assert isinstance(result["nac_v"], int)
        assert 0 <= result["nac_v"] <= 7
