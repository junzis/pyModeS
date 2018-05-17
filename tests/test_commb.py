from pyModeS import bds, commb
from pyModeS import ehs, els    # depricated

def test_bds20_callsign():
    assert bds.bds20.cs20("A000083E202CC371C31DE0AA1CCF") == 'KLM1017_'
    assert bds.bds20.cs20("A0001993202422F2E37CE038738E") == 'IBK2873_'

    assert commb.cs20("A000083E202CC371C31DE0AA1CCF") == 'KLM1017_'
    assert commb.cs20("A0001993202422F2E37CE038738E") == 'IBK2873_'

    assert els.cs20("A000083E202CC371C31DE0AA1CCF") == 'KLM1017_'
    assert els.cs20("A0001993202422F2E37CE038738E") == 'IBK2873_'


def test_bds40_functions():
    assert bds.bds40.alt40mcp("A000029C85E42F313000007047D3") == 3008
    assert bds.bds40.alt40fms("A000029C85E42F313000007047D3") == 3008
    assert bds.bds40.p40baro("A000029C85E42F313000007047D3") == 1020.0

    assert commb.alt40mcp("A000029C85E42F313000007047D3") == 3008
    assert commb.alt40fms("A000029C85E42F313000007047D3") == 3008
    assert commb.p40baro("A000029C85E42F313000007047D3") == 1020.0

    assert ehs.alt40mcp("A000029C85E42F313000007047D3") == 3008
    assert ehs.alt40fms("A000029C85E42F313000007047D3") == 3008
    assert ehs.p40baro("A000029C85E42F313000007047D3") == 1020.0


def test_bds50_functions():
    assert bds.bds50.roll50("A000139381951536E024D4CCF6B5") == 2.1
    assert bds.bds50.roll50("A0001691FFD263377FFCE02B2BF9") == -0.4     # signed value
    assert bds.bds50.trk50("A000139381951536E024D4CCF6B5") == 114.258
    assert bds.bds50.gs50("A000139381951536E024D4CCF6B5") == 438
    assert bds.bds50.rtrk50("A000139381951536E024D4CCF6B5") == 0.125
    assert bds.bds50.tas50("A000139381951536E024D4CCF6B5") == 424

    assert commb.roll50("A000139381951536E024D4CCF6B5") == 2.1
    assert commb.roll50("A0001691FFD263377FFCE02B2BF9") == -0.4     # signed value
    assert commb.trk50("A000139381951536E024D4CCF6B5") == 114.258
    assert commb.gs50("A000139381951536E024D4CCF6B5") == 438
    assert commb.rtrk50("A000139381951536E024D4CCF6B5") == 0.125
    assert commb.tas50("A000139381951536E024D4CCF6B5") == 424

    assert ehs.roll50("A000139381951536E024D4CCF6B5") == 2.1
    assert ehs.roll50("A0001691FFD263377FFCE02B2BF9") == -0.4     # signed value
    assert ehs.trk50("A000139381951536E024D4CCF6B5") == 114.258
    assert ehs.gs50("A000139381951536E024D4CCF6B5") == 438
    assert ehs.rtrk50("A000139381951536E024D4CCF6B5") == 0.125
    assert ehs.tas50("A000139381951536E024D4CCF6B5") == 424


def test_bds60_functions():
    assert bds.bds60.hdg60("A00004128F39F91A7E27C46ADC21") == 42.715
    assert bds.bds60.ias60("A00004128F39F91A7E27C46ADC21") == 252
    assert bds.bds60.mach60("A00004128F39F91A7E27C46ADC21") == 0.42
    assert bds.bds60.vr60baro("A00004128F39F91A7E27C46ADC21") == -1920
    assert bds.bds60.vr60ins("A00004128F39F91A7E27C46ADC21") == -1920

    assert commb.hdg60("A00004128F39F91A7E27C46ADC21") == 42.715
    assert commb.ias60("A00004128F39F91A7E27C46ADC21") == 252
    assert commb.mach60("A00004128F39F91A7E27C46ADC21") == 0.42
    assert commb.vr60baro("A00004128F39F91A7E27C46ADC21") == -1920
    assert commb.vr60ins("A00004128F39F91A7E27C46ADC21") == -1920

    assert ehs.hdg60("A00004128F39F91A7E27C46ADC21") == 42.715
    assert ehs.ias60("A00004128F39F91A7E27C46ADC21") == 252
    assert ehs.mach60("A00004128F39F91A7E27C46ADC21") == 0.42
    assert ehs.vr60baro("A00004128F39F91A7E27C46ADC21") == -1920
    assert ehs.vr60ins("A00004128F39F91A7E27C46ADC21") == -1920
