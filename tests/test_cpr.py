"""Tests for pymodes.position._cpr — CPR position decoding primitives."""

import pytest

from pymodes.position._cpr import airborne_position_with_ref, cprNL


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


class TestAirbornePositionWithRef:
    # Golden vectors copied verbatim from v2 tests/test_adsb.py.
    # The v2 function takes the full hex string and extracts CPR
    # internally. Our new API takes the raw CPR ints directly
    # (since Message.decode() already has them), so we precompute.

    @staticmethod
    def _cpr_fields(hex_msg: str) -> tuple[int, int, int]:
        """Return (cpr_format, cpr_lat_raw, cpr_lon_raw) for a hex ADS-B msg.

        Bit 53 (of the 112-bit message) = F (CPR format),
        bits 54-70 = CPR lat, bits 71-87 = CPR lon. Using 0-indexed
        payload bits here: bit 21 = F, bits 22-38 = lat, bits 39-55 = lon.
        """
        n = int(hex_msg, 16)
        payload = (n >> 24) & ((1 << 56) - 1)
        cpr_format = (payload >> 34) & 0x1
        cpr_lat = (payload >> 17) & 0x1FFFF
        cpr_lon = payload & 0x1FFFF
        return cpr_format, cpr_lat, cpr_lon

    def test_even_message_europe(self):
        fmt, lat_cpr, lon_cpr = self._cpr_fields("8D40058B58C901375147EFD09357")
        lat, lon = airborne_position_with_ref(fmt, lat_cpr, lon_cpr, 49.0, 6.0)
        assert lat == pytest.approx(49.82410, abs=0.001)
        assert lon == pytest.approx(6.06785, abs=0.001)

    def test_odd_message_europe(self):
        fmt, lat_cpr, lon_cpr = self._cpr_fields("8D40058B58C904A87F402D3B8C59")
        lat, lon = airborne_position_with_ref(fmt, lat_cpr, lon_cpr, 49.0, 6.0)
        assert lat == pytest.approx(49.81755, abs=0.001)
        assert lon == pytest.approx(6.08442, abs=0.001)

    def test_numerical_challenge(self):
        """v2 regression: reference close to a zone boundary."""
        fmt, lat_cpr, lon_cpr = self._cpr_fields("8D06A15358BF17FF7D4A84B47B95")
        lat_ref = 30.508474576271183  # close to (360/59)*5
        lon_ref = 7.2 * 5.0 + 3e-15
        lat, lon = airborne_position_with_ref(fmt, lat_cpr, lon_cpr, lat_ref, lon_ref)
        assert lat == pytest.approx(30.50540, abs=0.001)
        assert lon == pytest.approx(33.44787, abs=0.001)


class TestAirbornePositionPair:
    @staticmethod
    def _cpr_fields(hex_msg: str) -> tuple[int, int, int]:
        n = int(hex_msg, 16)
        payload = (n >> 24) & ((1 << 56) - 1)
        return (
            (payload >> 34) & 0x1,
            (payload >> 17) & 0x1FFFF,
            payload & 0x1FFFF,
        )

    def test_pair_odd_newer(self):
        """Matches v2 tests/test_adsb.py::test_adsb_position — odd frame is newer."""
        from pymodes.position._cpr import airborne_position_pair

        _, elat, elon = self._cpr_fields("8D40058B58C901375147EFD09357")
        _, olat, olon = self._cpr_fields("8D40058B58C904A87F402D3B8C59")
        result = airborne_position_pair(elat, elon, olat, olon, even_is_newer=False)
        assert result is not None
        lat, lon = result
        assert lat == pytest.approx(49.81755, abs=0.001)
        assert lon == pytest.approx(6.08442, abs=0.001)

    def test_pair_even_is_newer(self):
        """Same CPR pair, but reverse the newer flag.

        With even newer, the algorithm uses the even-frame latitude zone
        and the result is slightly different from the odd-newer case.
        Expected values computed by running the same formula with
        even_is_newer=True.
        """
        from pymodes.position._cpr import airborne_position_pair

        _, elat, elon = self._cpr_fields("8D40058B58C901375147EFD09357")
        _, olat, olon = self._cpr_fields("8D40058B58C904A87F402D3B8C59")
        result = airborne_position_pair(elat, elon, olat, olon, even_is_newer=True)
        assert result is not None
        lat, lon = result
        assert lat == pytest.approx(49.82410, abs=0.001)
        assert lon == pytest.approx(6.06785, abs=0.001)

    def test_pair_zone_mismatch_returns_none(self):
        """CPR pair whose resolved latitudes fall in different NL zones.

        cpr_lat_even=8192 → lat≈66.38° (NL=23)
        cpr_lat_odd=114688 → lat≈66.36° (NL=24)
        Found by grid search over the NL formula.
        """
        from pymodes.position._cpr import airborne_position_pair

        result = airborne_position_pair(8192, 0, 114688, 0, even_is_newer=True)
        assert result is None


class TestSurfacePositionWithRef:
    @staticmethod
    def _cpr_fields(hex_msg: str) -> tuple[int, int, int]:
        n = int(hex_msg, 16)
        payload = (n >> 24) & ((1 << 56) - 1)
        return (
            (payload >> 34) & 0x1,
            (payload >> 17) & 0x1FFFF,
            payload & 0x1FFFF,
        )

    def test_christchurch_surface(self):
        """Matches v2 tests/test_adsb.py::test_adsb_surface_position_with_ref."""
        from pymodes.position._cpr import surface_position_with_ref

        fmt, lat_cpr, lon_cpr = self._cpr_fields("8FC8200A3AB8F5F893096B000000")
        lat, lon = surface_position_with_ref(fmt, lat_cpr, lon_cpr, -43.5, 172.5)
        assert lat == pytest.approx(-43.48564, abs=0.001)
        assert lon == pytest.approx(172.53942, abs=0.001)


class TestSurfacePositionPair:
    @staticmethod
    def _cpr_fields(hex_msg: str) -> tuple[int, int, int]:
        n = int(hex_msg, 16)
        payload = (n >> 24) & ((1 << 56) - 1)
        return (
            (payload >> 34) & 0x1,
            (payload >> 17) & 0x1FFFF,
            payload & 0x1FFFF,
        )

    def test_christchurch_pair(self):
        """Verbatim from v2 tests/test_adsb.py::test_adsb_surface_position."""
        from pymodes.position._cpr import surface_position_pair

        # even: 8CC8200A3AC8F009BCDEF2000000 (t=0)
        # odd:  8FC8200A3AB8F5F893096B000000 (t=2) — odd is newer
        _, elat, elon = self._cpr_fields("8CC8200A3AC8F009BCDEF2000000")
        _, olat, olon = self._cpr_fields("8FC8200A3AB8F5F893096B000000")
        result = surface_position_pair(
            elat,
            elon,
            olat,
            olon,
            lat_ref=-43.496,
            lon_ref=172.558,
            even_is_newer=False,
        )
        assert result is not None
        lat, lon = result
        assert lat == pytest.approx(-43.48564, abs=0.001)
        assert lon == pytest.approx(172.53942, abs=0.001)
