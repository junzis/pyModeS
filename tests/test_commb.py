from pyModeS import bds, commb
from pytest import approx

# from pyModeS import ehs, els    # deprecated


def test_bds20_callsign():
    assert bds.bds20.cs20("A000083E202CC371C31DE0AA1CCF") == "KLM1017_"
    assert bds.bds20.cs20("A0001993202422F2E37CE038738E") == "IBK2873_"

    assert commb.cs20("A000083E202CC371C31DE0AA1CCF") == "KLM1017_"
    assert commb.cs20("A0001993202422F2E37CE038738E") == "IBK2873_"


def test_bds40_functions():
    assert bds.bds40.selalt40mcp("A000029C85E42F313000007047D3") == 3008
    assert bds.bds40.selalt40fms("A000029C85E42F313000007047D3") == 3008
    assert bds.bds40.p40baro("A000029C85E42F313000007047D3") == 1020.0

    assert commb.selalt40mcp("A000029C85E42F313000007047D3") == 3008
    assert commb.selalt40fms("A000029C85E42F313000007047D3") == 3008
    assert commb.p40baro("A000029C85E42F313000007047D3") == 1020.0


def test_bds50_functions():
    msg1 = "A000139381951536E024D4CCF6B5"
    msg2 = "A0001691FFD263377FFCE02B2BF9"

    for module in [bds.bds50, commb]:
        assert module.roll50(msg1) == approx(2.1, 0.01)
        assert module.roll50(msg2) == approx(-0.35, 0.01)  # signed value
        assert module.trk50(msg1) == approx(114.258, 0.1)
        assert module.gs50(msg1) == 438
        assert module.rtrk50(msg1) == 0.125
        assert module.tas50(msg1) == 424


def test_bds60_functions():
    msg = "A00004128F39F91A7E27C46ADC21"

    for module in [bds.bds60, commb]:
        assert bds.bds60.hdg60(msg) == approx(42.71484)
        assert bds.bds60.ias60(msg) == 252
        assert bds.bds60.mach60(msg) == 0.42
        assert bds.bds60.vr60baro(msg) == -1920
        assert bds.bds60.vr60ins(msg) == -1920
