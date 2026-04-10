"""Tests for pymodes.position._airports — surface-reference lookup."""

import pytest

from pymodes.position._airports import resolve_surface_ref


class TestResolveSurfaceRef:
    def test_known_icao_code(self):
        # Tolerance ~100 m — the shipped dataset is refreshed from
        # OurAirports, whose coordinates may drift slightly between
        # releases. The test just needs to confirm a plausible
        # position for a well-known airport.
        lat, lon = resolve_surface_ref("EHAM")
        assert lat == pytest.approx(52.308, abs=0.01)
        assert lon == pytest.approx(4.764, abs=0.01)

    def test_tuple_passthrough(self):
        assert resolve_surface_ref((49.0, 6.0)) == (49.0, 6.0)

    def test_unknown_code_raises(self):
        with pytest.raises(ValueError, match="unknown airport code"):
            resolve_surface_ref("ZZZZ")

    def test_dataset_contains_expected_airports(self):
        from pymodes.data.airports import AIRPORTS

        for code in ("EHAM", "KJFK", "NZCH", "LFPG", "EGLL", "RJTT"):
            assert code in AIRPORTS
