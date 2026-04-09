"""Tests for pymodes.core.decode() top-level function."""

import json

import pytest

from pymodes import decode
from pymodes.errors import InvalidHexError, InvalidLengthError
from pymodes.message import DecodedMessage


class TestDecodeSingleMessage:
    def test_returns_decoded_message(self):
        result = decode("8D406B902015A678D4D220AA4BDA")
        assert isinstance(result, DecodedMessage)

    def test_includes_df_and_icao(self):
        result = decode("8D406B902015A678D4D220AA4BDA")
        assert result["df"] == 17
        assert result["icao"] == "406B90"

    def test_includes_crc_valid_for_df17(self):
        result = decode("8D406B902015A678D4D220AA4BDA")
        assert result["crc_valid"] is True

    def test_invalid_hex_raises(self):
        with pytest.raises(InvalidHexError):
            decode("XYZ")

    def test_wrong_length_raises(self):
        with pytest.raises(InvalidLengthError):
            decode("8D")

    def test_case_insensitive(self):
        r1 = decode("8D406B902015A678D4D220AA4BDA")
        r2 = decode("8d406b902015a678d4d220aa4bda")
        assert r1["df"] == r2["df"]
        assert r1["icao"] == r2["icao"]

    def test_short_message(self):
        # A 14-hex short message (e.g., DF4 all zero)
        # DF=4, everything else zero; ICAO derived from CRC of zeros
        result = decode("20000000000000")
        assert result["df"] == 4

    def test_attribute_access_on_result(self):
        result = decode("8D406B902015A678D4D220AA4BDA")
        assert result.df == 17
        assert result.icao == "406B90"

    def test_result_is_json_serializable(self):
        result = decode("8D406B902015A678D4D220AA4BDA")
        text = json.dumps(result)
        assert "406B90" in text
