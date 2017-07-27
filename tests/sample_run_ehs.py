from __future__ import print_function
from pyModeS import adsb, ehs, util


# === Decode sample data file ===

def bds_info(BDS, m):
    if BDS == "BDS17":
        info = ([i[-2:] for i in ehs.cap17(m)])

    elif BDS == "BDS20":
        info = ehs.callsign(m)

    elif BDS == "BDS40":
        info = (ehs.alt40mcp(m), ehs.alt40fms(m), ehs.p40baro(m))

    elif BDS == "BDS44":
        info = (ehs.wind44(m), ehs.temp44(m), ehs.p44(m), ehs.hum44(m))

    elif BDS == "BDS44REV":
        info = (ehs.wind44(m, rev=True), ehs.temp44(m, rev=True), ehs.p44(m, rev=True), ehs.hum44(m, rev=True))

    elif BDS == "BDS50":
        info = (ehs.roll50(m), ehs.trk50(m), ehs.gs50(m), ehs.rtrk50(m), ehs.tas50(m))

    elif BDS == "BDS53":
        info = (ehs.hdg53(m), ehs.ias53(m), ehs.mach53(m), ehs.tas53(m), ehs.vr53(m))

    elif BDS == "BDS60":
        info = (ehs.hdg60(m), ehs.ias60(m), ehs.mach60(m), ehs.vr60baro(m), ehs.vr60ins(m))

    else:
        info = None

    return info


def ehs_decode_all(df, n=None):
    import csv

    print("===== Decode EHS sample data (DF=%s)=====" % df)

    f = open('tests/data/sample_data_ehs_df%s.csv' % df, 'rt')


    for i, r in enumerate(csv.reader(f)):
        if n and i > n:
            break

        ts = r[0]
        m = r[2]

        df = util.df(m)
        icao = ehs.icao(m)
        BDS = ehs.BDS(m)
        code = ehs.df20alt(m) if df==20 else ehs.df21id(m)

        if not BDS:
            print(ts, m, icao, df, '%5s'%code, 'UNKNOWN')
            continue

        if isinstance(BDS, list):
            print(ts, m, icao, df, '%5s'%code, end=' ')
            for i, bds in enumerate(BDS):
                if i == 0:
                    print(bds, *bds_info(bds, m))
                else:
                    print(' '*55, bds, *bds_info(bds, m))

        else:
            print(ts, m, icao, df, '%5s'%code, BDS, *bds_info(BDS, m))

if __name__ == '__main__':
    ehs_decode_all(df=20, n=100)
    ehs_decode_all(df=21, n=100)
