from pyModeS.c_decoder import adsb
import logging
import csv

# logging.basicConfig(level=logging.INFO)

logging.info("===== Decode ADS-B sample data=====")

f = open("tests/data/sample_data_adsb.csv", "rt")

msg0 = None
msg1 = None

for i, r in enumerate(csv.reader(f)):

    ts = int(r[0])
    m = str.encode(r[1])
    icao = adsb.icao(m)
    tc = adsb.typecode(m)
    if 1 <= tc <= 4:
        logging.info([ts, m, icao, tc, adsb.category(m), adsb.callsign(m)])
    if tc == 19:
        logging.info([ts, m, icao, tc, adsb.velocity(m)])
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
            logging.info([ts, m, icao, tc, pos, alt])
