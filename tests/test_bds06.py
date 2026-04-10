"""Tests for pymodes.decoder.bds.bds06 — ADS-B surface position (BDS 0,6)."""

from pymodes import decode


class TestBds06MovementRanges:
    def test_movement_ranges_from_v2_corpus(self):
        # From v2 test_adsb_surface_velocity_movement_ranges
        cases = [
            ("8c3944f8400002acb23cda192b95", None),  # code 0 → no info
            ("903a33ff40100858d34ff3cce976", 0.0),  # code 1 → stopped
            ("8c394c0f389b1667e947db7bb8bc", 1.0),  # code 9
            ("8c3461cf398d60597b4ea434c4d7", 7.5),  # code 24
            ("8c3461cf399d6059814ea81483a9", 8.0),  # code 25
            ("8c3461cf3a7f3059c94e5bf4e169", 15.0),  # code 39
            ("8c3950cf3dede47bac304d3b5122", 70.0),  # code 94
            ("8c3933203edde47b9e2ffa5e77b8", 100.0),  # code 109
            ("8d3933203fcde2a84e39e1c6c5bc", 175.0),  # code 124
        ]
        for msg, expected_spd in cases:
            result = decode(msg)
            gs = result.get("groundspeed")
            if expected_spd is None:
                assert gs is None, f"msg={msg} expected None, got {gs}"
            else:
                assert gs is not None and abs(gs - expected_spd) < 0.01, (
                    f"msg={msg} expected {expected_spd}, got {gs}"
                )


class TestBds06CprAndTrack:
    # Real DF18 BDS 0,6 surface movement from the jet1090 long_flight.csv
    # corpus — ICAO 3A23FF on a taxiway at LFBO (Toulouse-Blagnac).
    REAL_SURFACE_MSG = "903a23ff426a4e65f7487a775d17"

    def test_cpr_raw_fields_present(self):
        result = decode(self.REAL_SURFACE_MSG)
        assert result["df"] == 17 or result["df"] == 18
        assert result["bds"] == "0,6"
        assert "cpr_format" in result
        assert "cpr_lat" in result
        assert "cpr_lon" in result

    def test_track_or_none(self):
        # Either track_status is 0 (track None) or it's a valid angle
        result = decode(self.REAL_SURFACE_MSG)
        assert "track_status" in result
        ts = result["track_status"]
        assert ts in (0, 1)
        if ts == 0:
            assert result["track"] is None
        else:
            assert 0 <= result["track"] < 360

    def test_no_altitude_field(self):
        # Surface position messages do NOT populate altitude
        result = decode(self.REAL_SURFACE_MSG)
        assert "altitude" not in result
