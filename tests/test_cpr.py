"""Tests for pymodes.position._cpr — CPR position decoding primitives."""

from pymodes.position._cpr import cprNL


class TestCprNL:
    def test_equator(self):
        # At the equator, NL = 59 (maximum zones)
        assert cprNL(0.0) == 59

    def test_near_equator_positive(self):
        assert cprNL(0.1) == 59

    def test_near_equator_negative(self):
        assert cprNL(-0.1) == 59

    def test_mid_latitude(self):
        # Somewhere in the bulk of the table; matches v2 trig formula.
        assert cprNL(45.0) == 42

    def test_high_latitude(self):
        # Matches v2 trig formula.
        assert cprNL(80.0) == 10

    def test_pole_boundary_87(self):
        # Exactly 87° is a special case: NL = 2
        assert cprNL(87.0) == 2
        assert cprNL(-87.0) == 2

    def test_above_87(self):
        # Above 87° (polar region) NL = 1
        assert cprNL(87.5) == 1
        assert cprNL(-87.5) == 1

    def test_monotone_decreasing(self):
        # NL is monotone non-increasing with |lat|
        prev = cprNL(0.0)
        for lat_int in range(1, 88):
            nl = cprNL(float(lat_int))
            assert nl <= prev, f"non-monotone at lat={lat_int}: {prev} -> {nl}"
            prev = nl

    def test_symmetric(self):
        # NL depends only on |lat|
        for lat in (5.0, 15.3, 45.7, 67.2, 86.9):
            assert cprNL(lat) == cprNL(-lat)

    def test_matches_v2_trig_formula(self):
        """Regress against the v2 trig formula at 1-degree resolution."""
        from math import acos, cos, floor, pi

        nz = 15
        a = 1 - cos(pi / (2 * nz))
        for lat_int in range(-87, 88):
            lat = float(lat_int)
            if abs(lat) < 1e-8:
                expected = 59
            elif abs(abs(lat) - 87) <= 1e-8 + 1e-5 * 87:
                expected = 2
            else:
                b = cos(pi / 180 * abs(lat)) ** 2
                expected = floor(2 * pi / acos(1 - a / b))
            assert cprNL(lat) == expected, f"mismatch at lat={lat}"
