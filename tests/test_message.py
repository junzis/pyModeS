"""Tests for pyModeS.message — Decoded and Message base class."""

import json

import pytest

from pyModeS.errors import InvalidHexError, InvalidLengthError
from pyModeS.message import Decoded, Message


class TestDecoded:
    def test_is_dict_subclass(self):
        result = Decoded({"df": 17, "icao": "406B90"})
        assert isinstance(result, dict)

    def test_dict_access(self):
        result = Decoded({"df": 17, "icao": "406B90"})
        assert result["df"] == 17
        assert result["icao"] == "406B90"

    def test_attribute_access(self):
        result = Decoded({"df": 17, "icao": "406B90", "typecode": 4})
        assert result.df == 17
        assert result.icao == "406B90"
        assert result.typecode == 4

    def test_attribute_missing_raises_attribute_error(self):
        result = Decoded({"df": 17})
        with pytest.raises(AttributeError):
            _ = result.latitude

    def test_dict_get_missing_returns_none(self):
        result = Decoded({"df": 17})
        assert result.get("latitude") is None

    def test_json_serializable_via_json_dumps(self):
        result = Decoded({"df": 17, "icao": "406B90", "altitude": 35000})
        text = json.dumps(result)
        parsed = json.loads(text)
        assert parsed == {"df": 17, "icao": "406B90", "altitude": 35000}

    def test_to_json_method(self):
        result = Decoded({"df": 17, "icao": "406B90"})
        text = result.to_json()
        assert json.loads(text) == {"df": 17, "icao": "406B90"}

    def test_to_json_with_indent(self):
        result = Decoded({"df": 17, "icao": "406B90"})
        text = result.to_json(indent=2)
        assert "\n" in text  # pretty-printed
        assert json.loads(text) == {"df": 17, "icao": "406B90"}

    def test_iteration(self):
        result = Decoded({"df": 17, "icao": "406B90"})
        keys = list(result)
        assert "df" in keys
        assert "icao" in keys

    def test_items(self):
        result = Decoded({"df": 17, "icao": "406B90"})
        items = dict(result.items())
        assert items == {"df": 17, "icao": "406B90"}

    def test_none_value_preserved(self):
        result = Decoded({"df": 17, "heading": None})
        assert result["heading"] is None
        assert result.heading is None

    def test_attribute_names_do_not_collide_with_dict_methods(self):
        # Sanity: pyModeS field names like 'df', 'icao', 'typecode' don't
        # collide with dict methods like 'keys', 'items', 'update'.
        # This test locks in that we won't accidentally name a field
        # something that shadows a dict method.
        FORBIDDEN = set(dir({}))
        SAMPLE_FIELDS = {
            "df",
            "icao",
            "typecode",
            "bds",
            "callsign",
            "category",
            "altitude",
            "latitude",
            "longitude",
            "groundspeed",
            "track",
            "heading",
            "vertical_rate",
            "squawk",
            "crc_valid",
            "crc",
        }
        collisions = SAMPLE_FIELDS & FORBIDDEN
        assert not collisions, f"field names collide with dict methods: {collisions}"


class TestMessageConstruction:
    def test_from_long_hex_string(self):
        m = Message("8D406B902015A678D4D220AA4BDA")
        assert m._length == 112
        assert m._n == int("8D406B902015A678D4D220AA4BDA", 16)

    def test_from_short_hex_string(self):
        m = Message("20000000000000")
        assert m._length == 56
        assert m._n == 0x20000000000000

    def test_from_int_requires_length_hint(self):
        # An int alone is ambiguous (56 or 112 bits); explicit length kwarg required
        m = Message(0x8D406B902015A678D4D220AA4BDA, length=112)
        assert m._length == 112

    def test_from_int_no_length_defaults_to_112(self):
        # Without explicit length, assume long format (most common).
        # v3.0.0 does not emit a warning for this case; callers who
        # construct from int are expected to know the message length.
        m = Message(0x8D406B902015A678D4D220AA4BDA)
        assert m._length == 112

    def test_invalid_hex_raises(self):
        with pytest.raises(InvalidHexError):
            Message("XYZ")

    def test_wrong_length_raises(self):
        with pytest.raises(InvalidLengthError):
            Message("8D")

    def test_hex_is_case_insensitive(self):
        m_upper = Message("8D406B902015A678D4D220AA4BDA")
        m_lower = Message("8d406b902015a678d4d220aa4bda")
        assert m_upper._n == m_lower._n


class TestMessageDfIcaoCrc:
    def test_df17_df_is_17(self):
        m = Message("8D406B902015A678D4D220AA4BDA")
        assert m.df == 17

    def test_df17_icao_from_header(self):
        m = Message("8D406B902015A678D4D220AA4BDA")
        assert m.icao == "406B90"

    def test_df11_icao_from_header(self):
        # DF11 all-call reply has ICAO in bits 8-31 (same as DF17/18).
        # Synthetic test with placeholder CRC — we only check df and icao.
        m = Message("58406B90000000")
        assert m.df == 11
        assert m.icao == "406B90"

    def test_df4_icao_from_crc_derivation(self):
        # DF4 encodes ICAO in the CRC remainder.
        # Build a synthetic DF4 message where parity = crc_of_header XOR icao
        # so the computed remainder equals icao.
        from pyModeS._bits import crc_remainder

        icao = 0x400940
        # 56-bit message: [header:32][parity:24]
        # Header: DF=4 (00100) in top 5 bits = 0x20 in top byte, rest zero
        n_without_parity = 0x20000000 << 24
        crc0 = crc_remainder(n_without_parity, 56)
        parity = crc0 ^ icao
        n_full = n_without_parity | parity
        m = Message(f"{n_full:014X}")
        assert m.df == 4
        assert m.icao == "400940"

    def test_df17_crc_valid(self):
        # Known-valid DF17 message — CRC remainder should be 0
        m = Message("8D406B902015A678D4D220AA4BDA")
        assert m.crc_valid is True
        assert m.crc == 0

    def test_df17_crc_invalid(self):
        # Flip a bit in the message body to break CRC
        n = int("8D406B902015A678D4D220AA4BDA", 16) ^ (1 << 50)
        m = Message(n, length=112)
        assert m.crc_valid is False
        assert m.crc != 0

    def test_typecode_for_df17(self):
        # DF17 TC=4 identification
        m = Message("8D406B902015A678D4D220AA4BDA")
        assert m.typecode == 4

    def test_typecode_for_df20_is_none(self):
        # Typecode is only defined for DF17/18 extended squitter
        m = Message("A000083E202CC371C31DE0AA1CCF")
        assert m.df == 20
        assert m.typecode is None

    def test_cached_property_computes_once(self):
        # Accessing .df twice should not recompute
        m = Message("8D406B902015A678D4D220AA4BDA")
        first = m.df
        # Directly check the __dict__ entry that cached_property stores
        assert "df" in m.__dict__
        second = m.df
        assert first == second == 17


class TestMessageFromPayload:
    def test_from_payload_classmethod(self):
        # Payload (ME field) for "8D406B902015A678D4D220AA4BDA" is bits
        # 32-87, which are hex chars 8-21 = "2015A678D4D220"
        m = Message.from_payload("2015A678D4D220", df=17, icao="406B90")
        assert m.df == 17
        assert m.icao == "406B90"
        assert m.typecode == 4  # payload[0:5] = 00100 = 4

    def test_from_payload_wrong_length_raises(self):
        with pytest.raises(InvalidLengthError):
            Message.from_payload("2015A6", df=17, icao="406B90")
