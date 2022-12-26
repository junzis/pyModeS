from pyModeS import commb, common, bds

# === Decode sample data file ===


def bds_info(BDS, m):
    if BDS == "BDS10":
        info = [commb.ovc10(m)]

    elif BDS == "BDS17":
        info = [i[-2:] for i in commb.cap17(m)]

    elif BDS == "BDS20":
        info = [commb.cs20(m)]

    elif BDS == "BDS40":
        info = (commb.selalt40mcp(m), commb.selalt40fms(m), commb.p40baro(m))

    elif BDS == "BDS44":
        info = (commb.wind44(m), commb.temp44(m), commb.p44(m), commb.hum44(m))

    elif BDS == "BDS44REV":
        info = (
            commb.wind44(m, rev=True),
            commb.temp44(m, rev=True),
            commb.p44(m, rev=True),
            commb.hum44(m, rev=True),
        )

    elif BDS == "BDS50":
        info = (
            commb.roll50(m),
            commb.trk50(m),
            commb.gs50(m),
            commb.rtrk50(m),
            commb.tas50(m),
        )

    elif BDS == "BDS60":
        info = (
            commb.hdg60(m),
            commb.ias60(m),
            commb.mach60(m),
            commb.vr60baro(m),
            commb.vr60ins(m),
        )

    else:
        info = []

    return info


def commb_decode_all(df, n=None):
    import csv

    print("===== Decode Comm-B sample data (DF=%s)=====" % df)

    f = open("tests/data/sample_data_commb_df%s.csv" % df, "rt")

    for i, r in enumerate(csv.reader(f)):
        if n and i > n:
            break

        ts = r[0]
        m = r[2]

        df = common.df(m)
        icao = common.icao(m)
        BDS = bds.infer(m)
        code = common.altcode(m) if df == 20 else common.idcode(m)

        if not BDS:
            print(ts, m, icao, df, "%5s" % code, "UNKNOWN")
            continue

        if len(BDS.split(",")) > 1:
            print(ts, m, icao, df, "%5s" % code, end=" ")
            for i, _bds in enumerate(BDS.split(",")):
                if i == 0:
                    print(_bds, *bds_info(_bds, m))
                else:
                    print(" " * 55, _bds, *bds_info(_bds, m))

        else:
            print(ts, m, icao, df, "%5s" % code, BDS, *bds_info(BDS, m))


if __name__ == "__main__":
    commb_decode_all(df=20, n=500)
    commb_decode_all(df=21, n=500)
