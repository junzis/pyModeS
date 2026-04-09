"""Tests for pymodes.message — DecodedMessage and Message base class."""

import json

import pytest

from pymodes.message import DecodedMessage


class TestDecodedMessage:
    def test_is_dict_subclass(self):
        result = DecodedMessage({"df": 17, "icao": "406B90"})
        assert isinstance(result, dict)

    def test_dict_access(self):
        result = DecodedMessage({"df": 17, "icao": "406B90"})
        assert result["df"] == 17
        assert result["icao"] == "406B90"

    def test_attribute_access(self):
        result = DecodedMessage({"df": 17, "icao": "406B90", "typecode": 4})
        assert result.df == 17
        assert result.icao == "406B90"
        assert result.typecode == 4

    def test_attribute_missing_raises_attribute_error(self):
        result = DecodedMessage({"df": 17})
        with pytest.raises(AttributeError):
            _ = result.latitude

    def test_dict_get_missing_returns_none(self):
        result = DecodedMessage({"df": 17})
        assert result.get("latitude") is None

    def test_json_serializable_via_json_dumps(self):
        result = DecodedMessage({"df": 17, "icao": "406B90", "altitude": 35000})
        text = json.dumps(result)
        parsed = json.loads(text)
        assert parsed == {"df": 17, "icao": "406B90", "altitude": 35000}

    def test_to_json_method(self):
        result = DecodedMessage({"df": 17, "icao": "406B90"})
        text = result.to_json()
        assert json.loads(text) == {"df": 17, "icao": "406B90"}

    def test_to_json_with_indent(self):
        result = DecodedMessage({"df": 17, "icao": "406B90"})
        text = result.to_json(indent=2)
        assert "\n" in text  # pretty-printed
        assert json.loads(text) == {"df": 17, "icao": "406B90"}

    def test_iteration(self):
        result = DecodedMessage({"df": 17, "icao": "406B90"})
        keys = list(result)
        assert "df" in keys
        assert "icao" in keys

    def test_items(self):
        result = DecodedMessage({"df": 17, "icao": "406B90"})
        items = dict(result.items())
        assert items == {"df": 17, "icao": "406B90"}

    def test_none_value_preserved(self):
        result = DecodedMessage({"df": 17, "heading": None})
        assert result["heading"] is None
        assert result.heading is None

    def test_attribute_names_do_not_collide_with_dict_methods(self):
        # Sanity: pymodes field names like 'df', 'icao', 'typecode' don't
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
