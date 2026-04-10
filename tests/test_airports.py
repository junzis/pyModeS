"""Tests for pymodes.position._airports — airport lookup."""

import pytest

from pymodes.position._airports import resolve_airport


class TestResolveAirport:
    def test_known_code(self):
        lat, lon = resolve_airport("EHAM")
        assert lat == pytest.approx(52.30806)
        assert lon == pytest.approx(4.76417)

    def test_tuple_passthrough(self):
        assert resolve_airport((49.0, 6.0)) == (49.0, 6.0)

    def test_unknown_code_raises(self):
        with pytest.raises(ValueError, match="unknown airport code"):
            resolve_airport("ZZZZ")

    def test_seed_contains_expected_airports(self):
        from pymodes.data.airports import AIRPORTS

        for code in ("EHAM", "KJFK", "NZCH", "LFPG"):
            assert code in AIRPORTS
