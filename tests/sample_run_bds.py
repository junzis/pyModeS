from __future__ import print_function
from pyModeS import ehs, common, bds

# === Decode sample data file ===

def bds_info(BDS, m):
    if BDS == "BDS10":
        info = [bds.bds10.ovc10(m)]

    elif BDS == "BDS17":
        info = ([i[-2:] for i in bds.bds17.cap17(m)])

    elif BDS == "BDS20":
        info = [bds.bds20.cs20(m)]

    elif BDS == "BDS40":
        info = (bds.bds40.alt40mcp(m), bds.bds40.alt40fms(m), bds.bds40.p40baro(m))

    elif BDS == "BDS44":
        info = (bds.bds44.wind44(m), bds.bds44.temp44(m), bds.bds44.p44(m), bds.bds44.hum44(m))

    elif BDS == "BDS44REV":
        info = (bds.bds44.wind44(m, rev=True), bds.bds44.temp44(m, rev=True), bds.bds44.p44(m, rev=True), bds.bds44.hum44(m, rev=True))

    elif BDS == "BDS50":
        info = (bds.bds50.roll50(m), bds.bds50.trk50(m), bds.bds50.gs50(m), bds.bds50.rtrk50(m), bds.bds50.tas50(m))

    elif BDS == "BDS60":
        info = (bds.bds60.hdg60(m), bds.bds60.ias60(m), bds.bds60.mach60(m), bds.bds60.vr60baro(m), bds.bds60.vr60ins(m))

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

        df = common.df(m)
        icao = ehs.icao(m)
        BDS = bds.infer(m)
        code = common.altcode(m) if df == 20 else common.idcode(m)

        if not BDS:
            print(ts, m, icao, df, '%5s'%code, 'UNKNOWN')
            continue

        if len(BDS.split(",")) > 1:
            print(ts, m, icao, df, '%5s' % code, end=' ')
            for i, _bds in enumerate(BDS.split(",")):
                if i == 0:
                    print(_bds, *bds_info(_bds, m))
                else:
                    print(' ' * 55, _bds, *bds_info(_bds, m))

        else:
            print(ts, m, icao, df, '%5s'%code, BDS, *bds_info(BDS, m))

if __name__ == '__main__':
    ehs_decode_all(df=20, n=100)
    ehs_decode_all(df=21, n=100)
