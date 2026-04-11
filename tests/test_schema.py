"""Tests for pyModeS._schema."""

from typing import Any, ClassVar

from pyModeS._schema import _FULL_SCHEMA


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


class TestSchemaDriftDetection:
    """Walk a representative set of messages and verify every emitted
    key is declared in _FULL_SCHEMA.

    The schema is a SUPERSET of what any single decode emits (it
    declares the union across all decoders plus the batch/pipe error
    envelope). This test only checks the other direction: no decoder
    emits a key NOT declared in the schema.
    """

    # Hand-curated representative corpus, one or two per BDS register
    # and one per supported DF. (hex_msg, decode_kwargs) tuples.
    # Synthetic 56-bit / 112-bit messages carry pre-computed CRC parity.
    _CORPUS: ClassVar[list[tuple[str, dict[str, Any]]]] = [
        # Short surveillance and all-call
        ("0061103063A012", {}),  # DF0  ACAS short (synthetic)
        ("22001030766CD1", {}),  # DF4  altitude reply (synthetic)
        ("28000808106DE2", {}),  # DF5  identity reply (synthetic)
        ("5D4CA2D4000000", {}),  # DF11 all-call reply
        ("80001030FFFFFFFFFFFFFFE8E47B", {}),  # DF16 ACAS long (synthetic)
        # DF17 ADS-B extended squitter, one per BDS register
        ("8D406B902015A678D4D220AA4BDA", {}),  # BDS 0,8 identification (TC 4)
        (
            "8D40058B58C901375147EFD09357",
            {"reference": (49.0, 6.0)},
        ),  # BDS 0,5 airborne position (TC 11)
        (
            "903a23ff426a4e65f7487a775d17",
            {"surface_ref": "LFBO"},
        ),  # BDS 0,6 surface position (TC 8) — real LFBO taxi vector
        ("8D485020994409940838175B284F", {}),  # BDS 0,9 velocity sub 1
        ("8DA2C1B6E112B600000000760759", {}),  # BDS 6,1 aircraft status
        ("8DA05629EA21485CBF3F8CADAEEB", {}),  # BDS 6,2 target state and status
        (
            "8D400000F8000000005A38AF6F85",
            {},
        ),  # BDS 6,5 operational status (synthetic TC 31)
        # DF20 / DF21 Comm-B (BDS dispatched by infer())
        ("A800178D10010080F50000D5893C", {}),  # BDS 1,0 data link capability
        ("A0000638FA81C10000000081A92F", {}),  # BDS 1,7 GICB capability
        ("A000083E202CC371C31DE0AA1CCF", {}),  # BDS 2,0 aircraft identification
        ("A000029C85E42F313000007047D3", {}),  # BDS 4,0 selected vertical intention
        ("a000029cffbaa11e2004727281f1", {}),  # BDS 5,0 / 6,0 ambiguous
        ("a000139381951536e024d4ccf6b5", {}),  # BDS 5,0 track and turn
        ("A00004128F39F91A7E27C46ADC21", {}),  # BDS 6,0 heading and speed
        ("a8001eba360c11400a800f10cba2", {}),  # DF21 header-only (no BDS match)
    ]

    def test_no_decoder_emits_undeclared_key(self):
        from pyModeS import decode

        emitted: set[str] = set()
        decoded_count = 0
        for hex_msg, kwargs in self._CORPUS:
            result = decode(hex_msg, **kwargs)  # let exceptions surface
            emitted.update(result.keys())
            decoded_count += 1

        # Floor: every corpus entry must produce a result, and the
        # combined emitted-key set must cover at least 50 distinct
        # fields. A regression that mass-skips entries (or that
        # collapses decoder output to nothing) trips this floor.
        assert decoded_count == len(self._CORPUS)
        assert len(emitted) >= 50, (
            f"corpus only emitted {len(emitted)} distinct keys; "
            f"expected >= 50 (mass-skip regression?)"
        )

        undeclared = emitted - set(_FULL_SCHEMA.keys())
        assert not undeclared, (
            f"decoders emit keys not declared in _FULL_SCHEMA: {sorted(undeclared)}"
        )
