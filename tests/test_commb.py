"""Tests for pymodes.decoder.commb — CommB class for DF20/21."""

import pytest

from pymodes import decode
from pymodes.errors import InvalidHexError


class TestCommBHeaderDecoding:
    def test_df20_header_altitude(self):
        # DF20 Comm-B altitude reply. The AC13 field lives at bits 19-31
        # of the full 112-bit message, same layout as DF4. The MB payload
        # here is BDS20 (aircraft identification); once Task 4 wires up
        # BDS20 dispatch this message also carries a callsign alongside
        # the header altitude.
        result = decode("A000083E202CC371C31DE0AA1CCF")
        assert result["df"] == 20
        assert "altitude" in result
        assert isinstance(result["altitude"], int)

    def test_df21_header_squawk(self):
        # DF21 Comm-B identity reply. The ID13 field lives at bits 19-31.
        # Synthetic: we reuse an A8... DF21 message and assert the squawk
        # field is extracted from those bits. Once Task 7 wires up BDS50
        # dispatch this synthetic MB also validates as a Track and Turn
        # Report; the header squawk extraction is what this test pins.
        result = decode("A8001EBCFFFB23286004A73F6A5B")
        assert result["df"] == 21
        assert "squawk" in result
        assert isinstance(result["squawk"], str)
        assert len(result["squawk"]) == 4


class TestCommBIcaoVerified:
    def test_df20_without_icao_hint_unverified(self):
        # Without an icao= hint, CommB derives ICAO from the CRC
        # remainder and marks the result unverified.
        result = decode("A000083E202CC371C31DE0AA1CCF")
        assert result["df"] == 20
        assert result["icao_verified"] is False
        # The CRC-derived ICAO is still present (best effort).
        assert "icao" in result

    def test_df20_with_icao_hint_verified(self):
        # With an icao= hint, CommB uses the hint directly and marks
        # the result verified.
        result = decode("A000083E202CC371C31DE0AA1CCF", icao="AABBCC")
        assert result["icao"] == "AABBCC"
        assert result["icao_verified"] is True

    def test_df21_with_icao_hint_verified(self):
        result = decode("A8001EBCFFFB23286004A73F6A5B", icao="123456")
        assert result["icao"] == "123456"
        assert result["icao_verified"] is True


class TestCommBDoesNotAffectOtherDFs:
    def test_df17_icao_unchanged(self):
        # DF17 has ICAO in the clear (bits 8-31); the icao_hint kwarg
        # should have no effect and icao_verified should not be present.
        result = decode("8D406B902015A678D4D220AA4BDA")
        assert result["df"] == 17
        assert result["icao"] == "406B90"
        assert "icao_verified" not in result


class TestCommBIcaoHintValidation:
    def test_short_hint_rejected(self):
        with pytest.raises(InvalidHexError):
            decode("A000083E202CC371C31DE0AA1CCF", icao="ABC")

    def test_long_hint_rejected(self):
        with pytest.raises(InvalidHexError):
            decode("A000083E202CC371C31DE0AA1CCF", icao="ABCDEFG")

    def test_non_hex_hint_rejected(self):
        with pytest.raises(InvalidHexError):
            decode("A000083E202CC371C31DE0AA1CCF", icao="ZZZZZZ")

    def test_lowercase_hint_normalised(self):
        result = decode("A000083E202CC371C31DE0AA1CCF", icao="aabbcc")
        assert result["icao"] == "AABBCC"
        assert result["icao_verified"] is True
