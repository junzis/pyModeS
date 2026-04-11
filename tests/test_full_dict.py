"""Tests for full_dict=True mode."""

from pyModeS import decode
from pyModeS._schema import _FULL_SCHEMA


class TestFullDict:
    def test_default_mode_is_sparse(self):
        result = decode("8D406B902015A678D4D220AA4BDA")
        # Sparse mode: only fields that apply to this message
        assert "df" in result
        assert "icao" in result
        assert "callsign" in result  # BDS 0,8 identification
        # BDS 5,0 fields don't apply
        assert "roll" not in result
        assert "wind_speed" not in result

    def test_full_dict_populates_every_schema_key(self):
        result = decode("8D406B902015A678D4D220AA4BDA", full_dict=True)
        for key in _FULL_SCHEMA:
            assert key in result, f"full_dict missing schema key: {key}"

    def test_full_dict_preserves_decoded_values(self):
        result = decode("8D406B902015A678D4D220AA4BDA", full_dict=True)
        # The actual decoded fields keep their values
        assert result["df"] == 17
        assert result["icao"] == "406B90"
        assert result["callsign"] is not None
        # Inapplicable fields are explicit None
        assert result["roll"] is None
        assert result["wind_speed"] is None
        assert result["latitude"] is None  # no reference passed

    def test_full_dict_preserves_position_when_resolved(self):
        result = decode(
            "8D40058B58C901375147EFD09357",
            reference=(49.0, 6.0),
            full_dict=True,
        )
        assert result["latitude"] is not None
        assert result["longitude"] is not None
        assert result["roll"] is None  # still None — not a BDS 5,0 message
