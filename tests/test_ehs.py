from pyModeS import ehs


def test_ehs_icao():
    assert ehs.icao("A0001839CA3800315800007448D9") == '400940'
    assert ehs.icao("A000139381951536E024D4CCF6B5") == '3C4DD2'
    assert ehs.icao("A000029CFFBAA11E2004727281F1") == '4243D0'


def test_ehs_BDS():
    assert ehs.BDS("A0001838201584F23468207CDFA5") == 'BDS20'
    assert ehs.BDS("A0001839CA3800315800007448D9") == 'BDS40'
    assert ehs.BDS("A000139381951536E024D4CCF6B5") == 'BDS50'
    assert ehs.BDS("A000029CFFBAA11E2004727281F1") == 'BDS60'
    assert ehs.BDS("A0281838CAE9E12FA03FFF2DDDE5") == 'BDS44'
    assert ehs.BDS("A00017B0C8480030A4000024512F") is None


def test_ehs_BDS20_callsign():
    assert ehs.callsign("A000083E202CC371C31DE0AA1CCF") == 'KLM1017_'
    assert ehs.callsign("A0001993202422F2E37CE038738E") == 'IBK2873_'


def test_ehs_BDS40_functions():
    assert ehs.alt_mcp("A000029C85E42F313000007047D3") == 3008
    assert ehs.alt_fms("A000029C85E42F313000007047D3") == 3008
    assert ehs.pbaro("A000029C85E42F313000007047D3") == 1020.0


def test_ehs_BDS50_functions():
    assert ehs.roll("A000139381951536E024D4CCF6B5") == 2.1
    assert ehs.track("A000139381951536E024D4CCF6B5") == 114.3
    assert ehs.gs("A000139381951536E024D4CCF6B5") == 438
    assert ehs.rtrack("A000139381951536E024D4CCF6B5") == 0.125
    assert ehs.tas("A000139381951536E024D4CCF6B5") == 424


def test_ehs_BDS60_functions():
    assert ehs.heading("A000029CFFBAA11E2004727281F1") == 180.9
    assert ehs.ias("A000029CFFBAA11E2004727281F1") == 336
    assert ehs.mach("A000029CFFBAA11E2004727281F1") == 0.48
    assert ehs.baro_vr("A000029CFFBAA11E2004727281F1") == 0
    assert ehs.ins_vr("A000029CFFBAA11E2004727281F1") == -3648
