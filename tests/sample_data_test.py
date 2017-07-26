from __future__ import print_function
from pyModeS import adsb, ehs, util


# === Decode sample data file ===

def adsb_decode_all(n=None):
    print("===== Decode all ADS-B sample data=====")
    import csv
    f = open('tests/sample_data_adsb.csv', 'rt')

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
            print(ts, m, icao, tc, adsb.category(m), adsb.callsign(m))
        if tc == 19:
            print(ts, m, icao, tc, adsb.velocity(m))
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
                print(ts, m, icao, tc, pos, alt)


def ehs_decode_all(n=None):
    print("===== Decode all Mode-S EHS sample data=====")
    import csv
    f = open('tests/sample_data_ehs.csv', 'rt')
    for i, r in enumerate(csv.reader(f)):
        if n and i > n:
            break

        ts = r[1]
        m = r[2]

        df = util.df(m)
        icao = ehs.icao(m)
        vBDS = ehs.BDS(m)
        alt = ehs.df20alt(m) if df==20 else None


        if vBDS:
            if isinstance(vBDS, list):
                print(ts, m, icao, df, alt, vBDS)
            if vBDS == "BDS20":
                print(ts, m, icao, df, alt, vBDS, ehs.callsign(m))

            if vBDS == "BDS40":
                print(ts, m, icao, df, alt, vBDS, ehs.alt40mcp(m),
                      ehs.alt40fms(m), ehs.p40baro(m))

            if vBDS == "BDS44":
                print(ts, m, icao, df, alt, vBDS, ehs.wind44(m),
                      ehs.temp44(m), ehs.p44(m), ehs.hum44(m))

            if vBDS == "BDS44REV":
                print(ts, m, icao, df, alt, vBDS, ehs.wind44(m, rev=True),
                      ehs.temp44(m, rev=True), ehs.p44(m, rev=True), ehs.hum44(m, rev=True))

            if vBDS == "BDS50":
                print(ts, m, icao, df, alt, vBDS, ehs.roll50(m), ehs.trk50(m),
                      ehs.gs50(m), ehs.rtrk50(m), ehs.tas50(m))

            if vBDS == "BDS53":
                print(ts, m, icao, df, alt, vBDS, ehs.hdg53(m), ehs.ias53(m),
                      ehs.mach53(m), ehs.tas53(m), ehs.vr53(m))

            if vBDS == "BDS60":
                print(ts, m, icao, df, alt, vBDS, ehs.hdg60(m), ehs.ias60(m),
                      ehs.mach60(m), ehs.vr60baro(m), ehs.vr60ins(m))
        else:
            print(ts, m, icao, df, alt, 'UNKNOWN')

if __name__ == '__main__':
    adsb_decode_all(100)
    ehs_decode_all(100)
