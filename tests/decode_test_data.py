# If you get import error run with ipython
from pyModeS import adsb
from pyModeS import ehs


# === Decode sample data file ===

def adsb_decode_all(n=None):
    print "===== Decode all ADS-B sample data====="
    import csv
    f = open('tests/adsb.csv', 'rt')

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
    f = open('tests/ehs.csv', 'rt')
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
