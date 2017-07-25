from pyModeS import ehs
from pyModeS import modes_common

def test_ehs_icao():
    assert ehs.icao("A0001839CA3800315800007448D9") == '400940'
    assert ehs.icao("A000139381951536E024D4CCF6B5") == '3C4DD2'
    assert ehs.icao("A000029CFFBAA11E2004727281F1") == '4243D0'


def test_df20alt():
    assert ehs.df20alt("A02014B400000000000000F9D514") == 32300


def test_ehs_BDS():
    assert ehs.BDS("A0001838201584F23468207CDFA5") == 'BDS20'
    assert ehs.BDS("A0001839CA3800315800007448D9") == 'BDS40'
    assert ehs.BDS("A0000691E8D9DF1AFFB7F740A137") == 'BDS44'
    assert ehs.BDS("A000139381951536E024D4CCF6B5") == 'BDS50'
    assert ehs.BDS("A000029CFFBAA11E2004727281F1") == 'BDS60'


def test_ehs_BDS20_callsign():
    assert ehs.callsign("A000083E202CC371C31DE0AA1CCF") == 'KLM1017_'
    assert ehs.callsign("A0001993202422F2E37CE038738E") == 'IBK2873_'


def test_ehs_BDS40_functions():
    assert ehs.alt40mcp("A000029C85E42F313000007047D3") == 3008
    assert ehs.alt40fms("A000029C85E42F313000007047D3") == 3008
    assert ehs.p40baro("A000029C85E42F313000007047D3") == 1020.0

def test_ehs_BDS44_functions():
    assert ehs.wind44("A0000691E8D9DF1AFFB7F740A137") == (54.0, 168.0)
    assert ehs.temp44("A0000691E8D9DF1AFFB7F740A137") == -13.4
    assert ehs.p44("A0000691E8D9DF1AFFB7F740A137") == 2029
    assert ehs.hum44("A0000691E8D9DF1AFFB7F740A137") == 85.9

def test_ehs_BDS50_functions():
    assert ehs.roll50("A000139381951536E024D4CCF6B5") == 2.1
    assert ehs.trk50("A000139381951536E024D4CCF6B5") == 114.3
    assert ehs.gs50("A000139381951536E024D4CCF6B5") == 438
    assert ehs.rtrk50("A000139381951536E024D4CCF6B5") == 0.125
    assert ehs.tas50("A000139381951536E024D4CCF6B5") == 424


def test_ehs_BDS60_functions():
    assert ehs.hdg60("A000029CFFBAA11E2004727281F1") == 180.9
    assert ehs.ias60("A000029CFFBAA11E2004727281F1") == 336
    assert ehs.mach60("A000029CFFBAA11E2004727281F1") == 0.48
    assert ehs.vr60baro("A000029CFFBAA11E2004727281F1") == 0
    assert ehs.vr60ins("A000029CFFBAA11E2004727281F1") == 3648

def test_greycode_to_altitude():
    assert modes_common.grey2alt('00000000010') == -1000
    assert modes_common.grey2alt('00000001010') == -500
    assert modes_common.grey2alt('00000011011') == -100
    assert modes_common.grey2alt('00000011010') == 0
    assert modes_common.grey2alt('00000011110') == 100
    assert modes_common.grey2alt('00000010011') == 600
    assert modes_common.grey2alt('00000110010') == 1000
    assert modes_common.grey2alt('00001001001') == 5800
    assert modes_common.grey2alt('00011100100') == 10300
    assert modes_common.grey2alt('01100011010') == 32000
    assert modes_common.grey2alt('01110000100') == 46300
    assert modes_common.grey2alt('01010101100') == 50200
    assert modes_common.grey2alt('11011110100') == 73200
    assert modes_common.grey2alt('10000000011') == 126600
    assert modes_common.grey2alt('10000000001') == 126700
