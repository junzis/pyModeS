"""Tests for pymodes._schema."""

from pymodes._schema import _FULL_SCHEMA


class TestSchemaShape:
    def test_schema_size(self):
        # Schema was generated from an AST survey of every decoder.
        # Expected count is 123 as of the initial generation. Bump
        # this when adding new decoders or extending existing ones.
        assert len(_FULL_SCHEMA) == 123

    def test_schema_has_core_fields(self):
        for key in ("df", "icao", "crc_valid", "altitude", "callsign", "latitude"):
            assert key in _FULL_SCHEMA, f"missing core field: {key}"

    def test_schema_keys_are_strings(self):
        for key in _FULL_SCHEMA:
            assert isinstance(key, str)
            assert key.isidentifier(), f"non-identifier key: {key!r}"
