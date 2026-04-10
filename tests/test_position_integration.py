"""End-to-end position decoding through the public API."""

import pytest

from pymodes import decode


class TestMessageDecodeDirect:
    """Direct Message.decode() kwarg path."""

    def test_message_decode_with_reference(self):
        from pymodes import Message

        msg = Message("8D40058B58C901375147EFD09357")
        result = msg.decode(reference=(49.0, 6.0))
        assert result["latitude"] == pytest.approx(49.82410, abs=0.001)
        assert result["longitude"] == pytest.approx(6.06785, abs=0.001)

    def test_message_decode_with_surface_ref(self):
        from pymodes import Message

        # Real DF18 surface movement from jet1090 corpus (LFBO taxiway).
        msg = Message("903a23ff426a4e65f7487a775d17")
        result = msg.decode(surface_ref="LFBO")
        assert result["latitude"] == pytest.approx(43.62646, abs=0.001)
        assert result["longitude"] == pytest.approx(1.37476, abs=0.001)

    def test_message_decode_no_context(self):
        from pymodes import Message

        msg = Message("8D40058B58C901375147EFD09357")
        result = msg.decode()
        assert "latitude" not in result
        assert "cpr_lat" in result


class TestAirborneReference:
    def test_reference_returns_latlon(self):
        result = decode(
            "8D40058B58C901375147EFD09357",
            reference=(49.0, 6.0),
        )
        assert result["latitude"] == pytest.approx(49.82410, abs=0.001)
        assert result["longitude"] == pytest.approx(6.06785, abs=0.001)
        # Raw CPR fields should still be present
        assert "cpr_lat" in result
        assert "cpr_lon" in result
        assert result["cpr_format"] == 0  # even

    def test_no_reference_keeps_raw_cpr_only(self):
        result = decode("8D40058B58C901375147EFD09357")
        assert "latitude" not in result
        assert "longitude" not in result
        assert "cpr_lat" in result


class TestSurfaceRef:
    # Real DF18 BDS 0,6 surface movement from the jet1090 corpus —
    # ICAO 3A23FF on an LFBO taxiway. Replaces the earlier synthetic
    # 000000-parity vector.
    REAL_SURFACE_MSG = "903a23ff426a4e65f7487a775d17"

    def test_icao_code_returns_latlon(self):
        result = decode(self.REAL_SURFACE_MSG, surface_ref="LFBO")
        assert result["latitude"] == pytest.approx(43.62646, abs=0.001)
        assert result["longitude"] == pytest.approx(1.37476, abs=0.001)

    def test_tuple_returns_latlon(self):
        result = decode(self.REAL_SURFACE_MSG, surface_ref=(43.63, 1.37))
        assert result["latitude"] == pytest.approx(43.62646, abs=0.001)
        assert result["longitude"] == pytest.approx(1.37476, abs=0.001)

    def test_unknown_icao_raises(self):
        with pytest.raises(ValueError, match="unknown airport code"):
            decode(self.REAL_SURFACE_MSG, surface_ref="ZZZZ")

    def test_no_surface_ref_keeps_raw_cpr_only(self):
        result = decode(self.REAL_SURFACE_MSG)
        assert "latitude" not in result
        assert "longitude" not in result
        assert "cpr_lat" in result
