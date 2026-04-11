"""Tests for pyModeS.decoder.bds.bds62 — ADS-B target state and status (BDS 6,2)."""

from pyModeS import decode


class TestBds62:
    """BDS 6,2 Target State and Status (DO-260B, single format)."""

    MSG = "8DA05629EA21485CBF3F8CADAEEB"

    def test_dispatch_and_subtype(self):
        result = decode(self.MSG)
        assert result["df"] == 17
        assert result["typecode"] == 29
        assert result["bds"] == "6,2"
        assert result["subtype"] == 1  # DO-260B compliant golden

    def test_selected_altitude(self):
        # v2: selected_altitude(msg) → (16992, "MCP/FCU")
        # Note: jet1090 rounds to nearest 100 → 17000. v3 matches v2
        # (exact) so the raw 32-ft increments are preserved.
        result = decode(self.MSG)
        assert result["selected_altitude"] == 16992
        assert result["selected_altitude_source"] == "MCP/FCU"

    def test_barometric_pressure_setting(self):
        # v2: baro_pressure_setting(msg) → 1012.8
        result = decode(self.MSG)
        assert abs(result["baro_pressure_setting"] - 1012.8) < 0.01

    def test_selected_heading(self):
        # v2: selected_heading(msg) ≈ 66.8
        result = decode(self.MSG)
        assert abs(result["selected_heading"] - 66.8) < 0.1

    def test_autopilot_and_modes(self):
        result = decode(self.MSG)
        assert result["autopilot"] is True
        assert result["vnav_mode"] is True
        assert result["altitude_hold_mode"] is False
        assert result["approach_mode"] is False
        assert result["tcas_operational"] is True
        assert result["lnav_mode"] is True

    def test_nav_integrity_fields(self):
        # NAC_p, NIC_baro, and SIL are all present in the DO-260B
        # format. Values depend on the golden transmitter's config.
        result = decode(self.MSG)
        assert "nac_p" in result
        assert "nic_baro" in result
        assert "sil" in result
        assert 0 <= result["nac_p"] <= 15
        assert result["nic_baro"] in (0, 1)
        assert 0 <= result["sil"] <= 3

    def test_selected_heading_sign_bit_one(self):
        # Regression from v2 test_selected_heading_sign_bit_one:
        # "8DA05629EA21485EBF3F8CADAEEB" → ~246.8°
        result = decode("8DA05629EA21485EBF3F8CADAEEB")
        assert abs(result["selected_heading"] - 246.796875) < 0.01
