from pyModeS import adsb
from pytest import approx

# === TEST ADS-B package ===


def test_adsb_icao():
    assert adsb.icao("8D406B902015A678D4D220AA4BDA") == "406B90"


def test_adsb_category():
    assert adsb.category("8D406B902015A678D4D220AA4BDA") == 0


def test_adsb_callsign():
    assert adsb.callsign("8D406B902015A678D4D220AA4BDA") == "EZY85MH_"


def test_adsb_position():
    pos = adsb.position(
        "8D40058B58C901375147EFD09357",
        "8D40058B58C904A87F402D3B8C59",
        1446332400,
        1446332405,
    )
    assert pos == (approx(49.81755, 0.001), approx(6.08442, 0.001))


def test_adsb_position_swap_odd_even():
    pos = adsb.position(
        "8D40058B58C904A87F402D3B8C59",
        "8D40058B58C901375147EFD09357",
        1446332405,
        1446332400,
    )
    assert pos == (approx(49.81755, 0.001), approx(6.08442, 0.001))


def test_adsb_position_with_ref():
    pos = adsb.position_with_ref("8D40058B58C901375147EFD09357", 49.0, 6.0)
    assert pos == (approx(49.82410, 0.001), approx(6.06785, 0.001))
    pos = adsb.position_with_ref("8FC8200A3AB8F5F893096B000000", -43.5, 172.5)
    assert pos == (approx(-43.48564, 0.001), approx(172.53942, 0.001))


def test_adsb_airborne_position_with_ref():
    pos = adsb.airborne_position_with_ref(
        "8D40058B58C901375147EFD09357", 49.0, 6.0
    )
    assert pos == (approx(49.82410, 0.001), approx(6.06785, 0.001))
    pos = adsb.airborne_position_with_ref(
        "8D40058B58C904A87F402D3B8C59", 49.0, 6.0
    )
    assert pos == (approx(49.81755, 0.001), approx(6.08442, 0.001))


def test_adsb_airborne_position_with_ref_numerical_challenge():
    lat_ref = 30.508474576271183 # Close to (360.0/59.0)*5
    lon_ref = 7.2*5.0+3e-15
    pos = adsb.airborne_position_with_ref(
        "8D06A15358BF17FF7D4A84B47B95", lat_ref, lon_ref
    )
    assert pos == (approx(30.50540, 0.001), approx(33.44787, 0.001))


def test_adsb_surface_position_with_ref():
    pos = adsb.surface_position_with_ref(
        "8FC8200A3AB8F5F893096B000000", -43.5, 172.5
    )
    assert pos == (approx(-43.48564, 0.001), approx(172.53942, 0.001))


def test_adsb_surface_position():
    pos = adsb.surface_position(
        "8CC8200A3AC8F009BCDEF2000000",
        "8FC8200A3AB8F5F893096B000000",
        0,
        2,
        -43.496,
        172.558,
    )
    assert pos == (approx(-43.48564, 0.001), approx(172.53942, 0.001))


def test_adsb_alt():
    assert adsb.altitude("8D40058B58C901375147EFD09357") == 39000


def test_adsb_velocity():
    vgs = adsb.velocity("8D485020994409940838175B284F")
    vas = adsb.velocity("8DA05F219B06B6AF189400CBC33F")
    vgs_surface = adsb.velocity("8FC8200A3AB8F5F893096B000000")
    assert vgs == (159, approx(182.88, 0.1), -832, "GS")
    assert vas == (375, approx(243.98, 0.1), -2304, "TAS")
    assert vgs_surface == (19, approx(42.2, 0.1), 0, "GS")
    assert adsb.altitude_diff("8D485020994409940838175B284F") == 550


def test_adsb_emergency():
    assert not adsb.is_emergency("8DA2C1B6E112B600000000760759")
    assert adsb.emergency_state("8DA2C1B6E112B600000000760759") == 0
    assert adsb.emergency_squawk("8DA2C1B6E112B600000000760759") == "6513"


def test_adsb_target_state_status():
    sel_alt = adsb.selected_altitude("8DA05629EA21485CBF3F8CADAEEB")
    assert sel_alt == (16992, "MCP/FCU")
    assert adsb.baro_pressure_setting("8DA05629EA21485CBF3F8CADAEEB") == 1012.8
    assert adsb.selected_heading("8DA05629EA21485CBF3F8CADAEEB") == approx(
        66.8, 0.1
    )
    assert adsb.autopilot("8DA05629EA21485CBF3F8CADAEEB") is True
    assert adsb.vnav_mode("8DA05629EA21485CBF3F8CADAEEB") is True
    assert adsb.altitude_hold_mode("8DA05629EA21485CBF3F8CADAEEB") is False
    assert adsb.approach_mode("8DA05629EA21485CBF3F8CADAEEB") is False
    assert adsb.tcas_operational("8DA05629EA21485CBF3F8CADAEEB") is True
    assert adsb.lnav_mode("8DA05629EA21485CBF3F8CADAEEB") is True


# def test_nic():
#     assert adsb.nic('8D3C70A390AB11F55B8C57F65FE6') == 0
#     assert adsb.nic('8DE1C9738A4A430B427D219C8225') == 1
#     assert adsb.nic('8D44058880B50006B1773DC2A7E9') == 2
#     assert adsb.nic('8D44058881B50006B1773DC2A7E9') == 3
#     assert adsb.nic('8D4AB42A78000640000000FA0D0A') == 4
#     assert adsb.nic('8D4405887099F5D9772F37F86CB6') == 5
#     assert adsb.nic('8D4841A86841528E72D9B472DAC2') == 6
#     assert adsb.nic('8D44057560B9760C0B840A51C89F') == 7
#     assert adsb.nic('8D40621D58C382D690C8AC2863A7') == 8
#     assert adsb.nic('8F48511C598D04F12CCF82451642') == 9
#     assert adsb.nic('8DA4D53A50DBF8C6330F3B35458F') == 10
#     assert adsb.nic('8D3C4ACF4859F1736F8E8ADF4D67') == 11


def test_airborne_velocity_subtype3_heading_zero():
    """BDS09 subtype 3 (airspeed) with heading=0° (due north) must decode,
    not be silently dropped by the ground-speed zero-guard.

    Regression for the bug where bds09.airborne_velocity's early return
    at line 55-56 treated all zero bit-14-24 fields as invalid, including
    legitimate heading=0° for airspeed subtypes.
    """
    # Synthetic TC=19 subtype=3 message:
    #   heading=0°, airspeed=100 kt IAS, VR=+1024 ft/min (GNSS).
    # CRC is not verified by adsb.velocity(), so the last 6 hex chars
    # are arbitrary zero padding.
    msg = "8D4841409B04000CA04400000000"
    result = adsb.velocity(msg)
    assert result is not None, "Should not return None for heading=0°"
    spd, hdg, vs, spd_type = result
    assert spd == 100
    assert hdg == 0.0, f"Expected heading 0.0°, got {hdg}"
    assert vs == 1024
    assert spd_type == "IAS"


def test_selected_heading_sign_bit_one():
    """BDS62 selected heading, sign bit = 1 (upper half of range).

    Regression for the formula bug where (hdg_sign+1)*magnitude*(180/256)
    disagreed with the correct bin2int(mb[30:39])*360/512 whenever the
    sign bit was set. Message below is the existing sign=0 test message
    (`8DA05629EA21485CBF3F8CADAEEB` from test_adsb_target_state_status)
    with bit 30 of the ME flipped (nibble 7: C→E), giving
    mb[30:39]=101011111 (351).  Expected: 351 * 360/512 = 246.796875°.

    The sign=0 case is already covered by the existing
    test_adsb_target_state_status test in this file.
    """
    msg = "8DA05629EA21485EBF3F8CADAEEB"
    hdg = adsb.selected_heading(msg)
    assert hdg is not None
    assert abs(hdg - 246.796875) < 0.01, f"Expected ~246.8°, got {hdg}"


def test_nuc_p_happy_path():
    """nuc_p returns a 4-tuple for a valid airborne position message (TC=11)."""
    msg = "8D40058B58C901375147EFD09357"
    NUCp, HPL, RCu, RCv = adsb.nuc_p(msg)
    assert NUCp is not None


def test_nuc_p_rejects_identification():
    """nuc_p raises for a non-position typecode (TC=4 aircraft identification)."""
    import pytest
    with pytest.raises(RuntimeError):
        adsb.nuc_p("8D406B902015A678D4D220AA4BDA")


def test_adsb_altitude_negative_and_small():
    """BDS 0,5 altitude decode — negative values (below sea level),
    zero, and small positives. Regression gate for the altitude
    contract after the c_common/py_common unification.
    """
    cases = [
        ("8d484fde5803b647ecec4fcdd74f", -325),
        ("8d4845575803c647bcec2a980abc", -300),
        ("8d3424d25803d64c18ee03351f89", -275),
        ("8d4401e458058645a8ea90496290", 0),
        ("8d346355580596459cea86756acc", 25),
        ("8d346355580b064116e70a269f97", 1000),
        ("8d343386581f06318ad4fecab734", 5000),
    ]
    for msg, expected in cases:
        got = adsb.altitude(msg)
        assert got == expected, f"msg={msg} expected alt={expected}, got {got}"


def test_adsb_vertical_rate_sign_bits():
    """BDS 0,9 vertical rate — positive and negative values at the
    minimum-magnitude boundary (±64 ft/min) and typical mid-range.

    Uses adsb.velocity() which dispatches to airborne_velocity for TC=19
    and returns (spd, trk/hdg, vs, type).
    """
    cases = [
        ("8d3461cf9908388930080f948ea1", +64),
        ("8d3461cf9908558e100c1071eb67", +128),
        ("8d3461cf99085a8f10400f80e6ac", +960),
        ("8d394c0f990c4932780838866883", -64),
    ]
    for msg, expected_vs in cases:
        result = adsb.velocity(msg)
        assert result is not None, f"msg={msg} returned None"
        vs = result[2]
        assert vs == expected_vs, f"msg={msg} expected vs={expected_vs}, got {vs}"


def test_adsb_surface_velocity_movement_ranges():
    """BDS 0,6 surface movement field — one sample per step-boundary bin.

    Regression gate for the existing correct implementation across
    movement-code bins: 0 (no info), 1 (stopped), 9 (1.0 kt),
    24/25 (0.5 kt step range), 39, 94, 109, 124. adsb.velocity()
    dispatches to surface_velocity for TC 5-8.
    """
    cases = [
        ("8c3944f8400002acb23cda192b95", None),   # code 0 → no info
        ("903a33ff40100858d34ff3cce976", 0.0),    # code 1 → stopped
        ("8c394c0f389b1667e947db7bb8bc", 1.0),    # code 9
        ("8c3461cf398d60597b4ea434c4d7", 7.5),    # code 24
        ("8c3461cf399d6059814ea81483a9", 8.0),    # code 25 (validates 0.5 kt step)
        ("8c3461cf3a7f3059c94e5bf4e169", 15.0),   # code 39
        ("8c3950cf3dede47bac304d3b5122", 70.0),   # code 94
        ("8c3933203edde47b9e2ffa5e77b8", 100.0),  # code 109
        ("8d3933203fcde2a84e39e1c6c5bc", 175.0),  # code 124
    ]
    for msg, expected_spd in cases:
        result = adsb.velocity(msg)
        spd = result[0]
        if expected_spd is None:
            assert spd is None, f"msg={msg} expected None, got {spd}"
        else:
            assert spd is not None and abs(spd - expected_spd) < 0.01, (
                f"msg={msg} expected {expected_spd} kt, got {spd}"
            )
