"""Tests for pyModeS.position._cpr — CPR position decoding primitives."""

import pytest

from pyModeS.position._cpr import airborne_position_with_ref, cprNL


def _cpr_fields(hex_msg: str) -> tuple[int, int, int]:
    """Extract (cpr_format, cpr_lat_raw, cpr_lon_raw) from a full hex ADS-B message.

    Bit 21 of the 56-bit payload = CPR format (0=even, 1=odd);
    bits 22-38 = CPR latitude; bits 39-55 = CPR longitude.
    """
    n = int(hex_msg, 16)
    payload = (n >> 24) & ((1 << 56) - 1)
    return (
        (payload >> 34) & 0x1,
        (payload >> 17) & 0x1FFFF,
        payload & 0x1FFFF,
    )


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

    def test_even_message_europe(self):
        fmt, lat_cpr, lon_cpr = _cpr_fields("8D40058B58C901375147EFD09357")
        lat, lon = airborne_position_with_ref(fmt, lat_cpr, lon_cpr, 49.0, 6.0)
        assert lat == pytest.approx(49.82410, abs=0.001)
        assert lon == pytest.approx(6.06785, abs=0.001)

    def test_odd_message_europe(self):
        fmt, lat_cpr, lon_cpr = _cpr_fields("8D40058B58C904A87F402D3B8C59")
        lat, lon = airborne_position_with_ref(fmt, lat_cpr, lon_cpr, 49.0, 6.0)
        assert lat == pytest.approx(49.81755, abs=0.001)
        assert lon == pytest.approx(6.08442, abs=0.001)

    def test_numerical_challenge(self):
        """v2 regression: reference close to a zone boundary."""
        fmt, lat_cpr, lon_cpr = _cpr_fields("8D06A15358BF17FF7D4A84B47B95")
        lat_ref = 30.508474576271183  # close to (360/59)*5
        lon_ref = 7.2 * 5.0 + 3e-15
        lat, lon = airborne_position_with_ref(fmt, lat_cpr, lon_cpr, lat_ref, lon_ref)
        assert lat == pytest.approx(30.50540, abs=0.001)
        assert lon == pytest.approx(33.44787, abs=0.001)


class TestAirbornePositionPair:
    def test_pair_odd_newer(self):
        """Matches v2 tests/test_adsb.py::test_adsb_position — odd frame is newer."""
        from pyModeS.position._cpr import airborne_position_pair

        _, elat, elon = _cpr_fields("8D40058B58C901375147EFD09357")
        _, olat, olon = _cpr_fields("8D40058B58C904A87F402D3B8C59")
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
        from pyModeS.position._cpr import airborne_position_pair

        _, elat, elon = _cpr_fields("8D40058B58C901375147EFD09357")
        _, olat, olon = _cpr_fields("8D40058B58C904A87F402D3B8C59")
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
        from pyModeS.position._cpr import airborne_position_pair

        result = airborne_position_pair(8192, 0, 114688, 0, even_is_newer=True)
        assert result is None

    def test_pair_impossible_latitude_returns_none(self):
        """A pair that slips past the cprNL check but resolves to an
        impossible latitude (|lat| > 90) must be rejected.

        Real DF17 pair from OpenSky (ICAO 485A33, 2025-04-13 19:34:57):
          even: 8f485a33397c737a27d1b18072cd (cpr_lat=113939, cpr_lon=119217)
          odd:  8d485a33581d663872e86a3bbfff (cpr_lat=72761,  cpr_lon=59498)
        Prior to the sanity guard these resolved to lat≈113.22°,
        producing a position over the Bering Sea for an aircraft that
        was climbing out of Amsterdam.
        """
        from pyModeS.position._cpr import airborne_position_pair

        result = airborne_position_pair(
            113939, 119217, 72761, 59498, even_is_newer=False
        )
        assert result is None


class TestSurfacePositionWithRef:
    # Real DF18 BDS 0,6 surface movement pair from jet1090's
    # long_flight.csv — aircraft ICAO 3A23FF on an LFBO taxiway.
    # Replaces the synthetic 000000-parity vectors the tests used
    # previously.
    EVEN_MSG = "903a23ff426a38565950432ebf95"
    ODD_MSG = "903a23ff426a4e65f7487a775d17"

    def test_lfbo_surface(self):
        """Real surface CPR vector resolved at LFBO airport reference."""
        from pyModeS.position._cpr import surface_position_with_ref

        fmt, lat_cpr, lon_cpr = _cpr_fields(self.ODD_MSG)
        lat, lon = surface_position_with_ref(fmt, lat_cpr, lon_cpr, 43.63, 1.37)
        assert lat == pytest.approx(43.62646, abs=0.001)
        assert lon == pytest.approx(1.37476, abs=0.001)


class TestSurfacePositionPair:
    # Same real LFBO vectors as TestSurfacePositionWithRef.
    EVEN_MSG = "903a23ff426a38565950432ebf95"
    ODD_MSG = "903a23ff426a4e65f7487a775d17"

    def test_lfbo_pair(self):
        """Real even/odd surface pair, odd-is-newer branch."""
        from pyModeS.position._cpr import surface_position_pair

        _, elat, elon = _cpr_fields(self.EVEN_MSG)
        _, olat, olon = _cpr_fields(self.ODD_MSG)
        result = surface_position_pair(
            elat,
            elon,
            olat,
            olon,
            lat_ref=43.63,
            lon_ref=1.37,
            even_is_newer=False,
        )
        assert result is not None
        lat, lon = result
        assert lat == pytest.approx(43.62646, abs=0.001)
        assert lon == pytest.approx(1.37476, abs=0.001)

    def test_lfbo_pair_even_newer(self):
        """Same pair, but exercise the even_is_newer=True branch (ni=max(nl,1))."""
        from pyModeS.position._cpr import surface_position_pair

        _, elat, elon = _cpr_fields(self.EVEN_MSG)
        _, olat, olon = _cpr_fields(self.ODD_MSG)
        result = surface_position_pair(
            elat,
            elon,
            olat,
            olon,
            lat_ref=43.63,
            lon_ref=1.37,
            even_is_newer=True,
        )
        assert result is not None
        lat, lon = result
        # Slightly different result because the algorithm uses the
        # even-frame latitude and a different ni formula.
        assert lat == pytest.approx(43.62648, abs=0.001)
        assert lon == pytest.approx(1.37462, abs=0.001)

    def test_southern_hemisphere(self):
        """Negative lat_ref → S-hemisphere mirror (lat ≈ -46° of the +43°)."""
        from pyModeS.position._cpr import surface_position_pair

        _, elat, elon = _cpr_fields(self.EVEN_MSG)
        _, olat, olon = _cpr_fields(self.ODD_MSG)
        result = surface_position_pair(
            elat,
            elon,
            olat,
            olon,
            lat_ref=-43.5,
            lon_ref=1.37,
            even_is_newer=False,
        )
        assert result is not None
        lat, lon = result
        assert lat == pytest.approx(-46.37354, abs=0.001)
        assert lon == pytest.approx(1.44350, abs=0.001)

    def test_quadrant_wrap_180(self):
        """Receiver 180° away → algorithm picks the +180 quadrant candidate."""
        from pyModeS.position._cpr import surface_position_pair

        _, elat, elon = _cpr_fields(self.EVEN_MSG)
        _, olat, olon = _cpr_fields(self.ODD_MSG)
        result = surface_position_pair(
            elat,
            elon,
            olat,
            olon,
            lat_ref=43.63,
            lon_ref=-178.63,
            even_is_newer=False,
        )
        assert result is not None
        lat, lon = result
        assert lat == pytest.approx(43.62646, abs=0.001)
        assert lon == pytest.approx(-178.62524, abs=0.001)

    def test_quadrant_wrap_90(self):
        """Receiver 90° away → algorithm picks the +90 quadrant candidate."""
        from pyModeS.position._cpr import surface_position_pair

        _, elat, elon = _cpr_fields(self.EVEN_MSG)
        _, olat, olon = _cpr_fields(self.ODD_MSG)
        result = surface_position_pair(
            elat,
            elon,
            olat,
            olon,
            lat_ref=43.63,
            lon_ref=91.37,
            even_is_newer=False,
        )
        assert result is not None
        lat, lon = result
        assert lat == pytest.approx(43.62646, abs=0.001)
        assert lon == pytest.approx(91.37476, abs=0.001)

    def test_zone_mismatch_returns_none(self):
        """Synthetic CPR pair where N-hemi candidates fall in different NL zones.

        Found by grid search: cpr_lat_even=28672, cpr_lat_odd=122880 produce
        lat_even_n ≈ 25.828° (NL=54), lat_odd_n ≈ 25.837° (NL=53).
        """
        from pyModeS.position._cpr import surface_position_pair

        result = surface_position_pair(
            28672,
            0,
            122880,
            0,
            lat_ref=50.0,
            lon_ref=0.0,
            even_is_newer=True,
        )
        assert result is None

    def test_sao_paulo_pair_from_v2_bds_inference(self):
        """Plan 5 Task 3: v2 tests/test_bds_inference.py::test_surface_position.

        v2 pair from São Paulo (Southern Hemisphere, negative longitude),
        distinct from the Christchurch pair already covered above. The v2
        assertion was ``abs(lon_ref - lon) < 0.05``.
        """
        from pyModeS.position._cpr import surface_position_pair

        # msg0 (even, t=1565608663102), msg1 (odd, t=1565608666214) → odd is newer
        _, elat, elon = _cpr_fields("8FE48C033A9FA184B934E744C6FD")
        _, olat, olon = _cpr_fields("8FE48C033A9FA68F7C3D39B1C2F0")
        result = surface_position_pair(
            elat,
            elon,
            olat,
            olon,
            lat_ref=-23.4265448,
            lon_ref=-46.4816258,
            even_is_newer=False,
        )
        assert result is not None
        lat, lon = result
        assert abs(lon - (-46.4816258)) < 0.05
        assert abs(lat - (-23.4265448)) < 0.05
