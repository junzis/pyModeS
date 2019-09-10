from __future__ import print_function
from pyModeS import adsb, ehs


# === Decode sample data file ===


def adsb_decode_all(n=None):
    print("===== Decode ADS-B sample data=====")
    import csv

    f = open("tests/data/sample_data_adsb.csv", "rt")

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


if __name__ == "__main__":
    adsb_decode_all(n=100)
