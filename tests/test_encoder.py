from pyModeS import encoder


def test_identification():
    msg = encoder.encode_adsb(
        icao="406B90", typecode=4, capability=5, category=0, callsign="EZY85MH"
    )
    assert msg == "8D406B902015A678D4D220AA4BDA"


def test_speed():
    msg = encoder.encode_adsb(
        icao="485020",
        typecode=19,
        capability=5,
        speed_type="gs",
        speed=159,
        angle=182.88,
        vertical_rate=-832,
        vertical_rate_source="gnss",
        gnss_baro_alt_diff=550,
    )
    assert msg == "8D485020994409940838175B284F"
