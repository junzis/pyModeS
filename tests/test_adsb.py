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
