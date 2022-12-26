import csv
import time

from pyModeS.decoder import adsb

print("===== Decode ADS-B sample data=====")

f = open("tests/data/sample_data_adsb.csv", "rt")

msg0 = None
msg1 = None

tstart = time.time()
for i, r in enumerate(csv.reader(f)):

    ts = int(r[0])
    m = r[1].encode()

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


dt = time.time() - tstart

print("Execution time: {} seconds".format(dt))
