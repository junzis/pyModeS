import os, sys, inspect
currentdir = os.path.dirname(os.path.abspath(
                inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

import pyModeS as pms
from pyModeS import adsb
from pyModeS import ehs


# === TEST ADS-B package ===

def test_adsb_icao():
    assert adsb.icao("8D406B902015A678D4D220AA4BDA") == "406B90"


def test_adsb_category():
    assert adsb.category("8D406B902015A678D4D220AA4BDA") == 5


def test_adsb_callsign():
    assert adsb.callsign("8D406B902015A678D4D220AA4BDA") == "EZY85MH_"


def test_adsb_position():
    pos = adsb.position("8D40058B58C901375147EFD09357",
                        "8D40058B58C904A87F402D3B8C59",
                        1446332400, 1446332405)
    assert pos == (49.81755, 6.08442)


def test_adsb_alt():
    assert adsb.altitude("8D40058B58C901375147EFD09357") == 39000


def test_adsb_velocity():
    vgs = adsb.velocity("8D485020994409940838175B284F")
    vas = adsb.velocity("8DA05F219B06B6AF189400CBC33F")
    assert vgs == (159, 182.9, -263, 'GS')
    assert vas == (376, 244.0, -274, 'AS')


def test_nic():
    assert adsb.nic('8D3C70A390AB11F55B8C57F65FE6') == 0
    assert adsb.nic('8DE1C9738A4A430B427D219C8225') == 1
    assert adsb.nic('8D44058880B50006B1773DC2A7E9') == 2
    assert adsb.nic('8D44058881B50006B1773DC2A7E9') == 3
    assert adsb.nic('8D4AB42A78000640000000FA0D0A') == 4
    assert adsb.nic('8D4405887099F5D9772F37F86CB6') == 5
    assert adsb.nic('8D4841A86841528E72D9B472DAC2') == 6
    assert adsb.nic('8D44057560B9760C0B840A51C89F') == 7
    assert adsb.nic('8D40621D58C382D690C8AC2863A7') == 8
    assert adsb.nic('8F48511C598D04F12CCF82451642') == 9
    assert adsb.nic('8DA4D53A50DBF8C6330F3B35458F') == 10
    assert adsb.nic('8D3C4ACF4859F1736F8E8ADF4D67') == 11


# === TEST Mode-S EHS package ===

def test_ehs_icao():
    assert ehs.icao("A0001839CA3800315800007448D9") == '400940'
    assert ehs.icao("A000139381951536E024D4CCF6B5") == '3C4DD2'
    assert ehs.icao("A000029CFFBAA11E2004727281F1") == '4243D0'


def test_ehs_BDS():
    assert ehs.BDS("A0001838201584F23468207CDFA5") == 'BDS20'
    assert ehs.BDS("A0001839CA3800315800007448D9") == 'BDS40'
    assert ehs.BDS("A000139381951536E024D4CCF6B5") == 'BDS50'
    assert ehs.BDS("A000029CFFBAA11E2004727281F1") == 'BDS60'
    assert ehs.BDS("A0281838CAE9E12FA03FFF2DDDE5") is None


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


# === Decode sample data file ===

def adsb_decode_all(n=None):
    print "===== Decode all ADS-B sample data====="
    import csv
    f = open('adsb.csv', 'rt')

    msg0 = None
    msg1 = None

    for i, r in enumerate(csv.reader(f)):
        if n and i > n:
            break

        ts = r[0]
        m = r[1]
        icao = adsb.icao(m)
        tc = adsb.typecode(m)
        if 1 <= tc <= 4:
            print ts, m, icao, tc, adsb.category(m), adsb.callsign(m)
        if tc == 19:
            print ts, m, icao, tc, adsb.velocity(m)
        if 5 <= tc <= 18:
            if adsb.oe_flag(m):
                msg1 = m
                t1 = ts
            else:
                msg0 = m
                t0 = ts

            if msg0 and msg1:
                pos = adsb.position(msg0, msg1, t0, t1)
                alt = adsb.altitude(m)
                print ts, m, icao, tc, pos, alt


def ehs_decode_all(n=None):
    print "===== Decode all Mode-S EHS sample data====="
    import csv
    f = open('ehs.csv', 'rt')
    for i, r in enumerate(csv.reader(f)):
        if n and i > n:
            break

        ts = r[1]
        m = r[2]
        icao = ehs.icao(m)
        vBDS = ehs.BDS(m)

        if vBDS:
            if vBDS == "BDS20":
                print ts, m, icao, vBDS, ehs.callsign(m)

            if vBDS == "BDS40":
                print ts, m, icao, vBDS, ehs.alt_mcp(m), \
                      ehs.alt_fms(m), ehs.pbaro(m)

            if vBDS == "BDS50":
                print ts, m, icao, vBDS, ehs.roll(m), ehs.track(m), \
                      ehs.gs(m), ehs.rtrack(m), ehs.tas(m)

            if vBDS == "BDS60":
                print ts, m, icao, vBDS, ehs.heading(m), ehs.ias(m), \
                      ehs.mach(m), ehs.baro_vr(m), ehs.ins_vr(m)
        else:
            print ts, m, icao, vBDS

if __name__ == '__main__':
    adsb_decode_all(100)
    ehs_decode_all(100)
