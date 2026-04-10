"""End-to-end position decoding through the public API."""

import pytest

from pymodes import decode


class TestMessageDecodeDirect:
    """Direct Message.decode() kwarg path — works after Task 9."""

    def test_message_decode_with_reference(self):
        from pymodes import Message

        msg = Message("8D40058B58C901375147EFD09357")
        result = msg.decode(reference=(49.0, 6.0))
        assert result["latitude"] == pytest.approx(49.82410, abs=0.001)
        assert result["longitude"] == pytest.approx(6.06785, abs=0.001)

    def test_message_decode_with_airport(self):
        from pymodes import Message

        msg = Message("8FC8200A3AB8F5F893096B000000")
        result = msg.decode(airport="NZCH")
        assert result["latitude"] == pytest.approx(-43.48564, abs=0.001)
        assert result["longitude"] == pytest.approx(172.53942, abs=0.001)

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


class TestSurfaceAirport:
    def test_airport_code_returns_latlon(self):
        # Surface CPR vector from v2 tests
        result = decode("8FC8200A3AB8F5F893096B000000", airport="NZCH")
        assert result["latitude"] == pytest.approx(-43.48564, abs=0.001)
        assert result["longitude"] == pytest.approx(172.53942, abs=0.001)

    def test_airport_tuple_returns_latlon(self):
        result = decode("8FC8200A3AB8F5F893096B000000", airport=(-43.5, 172.5))
        assert result["latitude"] == pytest.approx(-43.48564, abs=0.001)
        assert result["longitude"] == pytest.approx(172.53942, abs=0.001)

    def test_unknown_airport_raises(self):
        with pytest.raises(ValueError, match="unknown airport code"):
            decode("8FC8200A3AB8F5F893096B000000", airport="ZZZZ")

    def test_no_airport_keeps_raw_cpr_only(self):
        result = decode("8FC8200A3AB8F5F893096B000000")
        assert "latitude" not in result
        assert "longitude" not in result
        assert "cpr_lat" in result
