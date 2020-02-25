import sys
import time
import pandas as pd
from tqdm import tqdm
from pyModeS.decoder import adsb

fin = sys.argv[1]

df = pd.read_csv(fin, names=["ts", "df", "icao", "msg"])
df_adsb = df[df["df"] == 17].copy()

total = df_adsb.shape[0]


def native():

    from pyModeS.decoder import common

    # airborne position
    m_air_0 = None
    m_air_1 = None

    # surface position
    m_surf_0 = None
    m_surf_1 = None

    for i, r in tqdm(df_adsb.iterrows(), total=total):
        ts = r.ts
        m = r.msg

        downlink_format = common.df(m)
        crc = common.crc(m)
        icao = adsb.icao(m)
        tc = adsb.typecode(m)

        if 1 <= tc <= 4:
            category = adsb.category(m)
            callsign = adsb.callsign(m)
        if tc == 19:
            velocity = adsb.velocity(m)

        if 5 <= tc <= 8:
            if adsb.oe_flag(m):
                m_surf_1 = m
                t1 = ts
            else:
                m_surf_0 = m
                t0 = ts

            if m_surf_0 and m_surf_1:
                position = adsb.surface_position(
                    m_surf_0, m_surf_1, t0, t1, 50.01, 4.35
                )
                altitude = adsb.altitude(m)

        if 9 <= tc <= 18:
            if adsb.oe_flag(m):
                m_air_1 = m
                t1 = ts
            else:
                m_air_0 = m
                t0 = ts

            if m_air_0 and m_air_1:
                position = adsb.position(m_air_0, m_air_1, t0, t1)
                altitude = adsb.altitude(m)


def cython():

    from pyModeS.decoder import c_common as common

    # airborne position
    m_air_0 = None
    m_air_1 = None

    # surface position
    m_surf_0 = None
    m_surf_1 = None

    for i, r in tqdm(df_adsb.iterrows(), total=total):
        ts = r.ts
        m = r.msg

        downlink_format = common.df(m)
        crc = common.crc(m)
        icao = adsb.icao(m)
        tc = adsb.typecode(m)

        if 1 <= tc <= 4:
            category = adsb.category(m)
            callsign = adsb.callsign(m)
        if tc == 19:
            velocity = adsb.velocity(m)

        if 5 <= tc <= 8:
            if adsb.oe_flag(m):
                m_surf_1 = m
                t1 = ts
            else:
                m_surf_0 = m
                t0 = ts

            if m_surf_0 and m_surf_1:
                position = adsb.surface_position(
                    m_surf_0, m_surf_1, t0, t1, 50.01, 4.35
                )
                altitude = adsb.altitude(m)

        if 9 <= tc <= 18:
            if adsb.oe_flag(m):
                m_air_1 = m
                t1 = ts
            else:
                m_air_0 = m
                t0 = ts

            if m_air_0 and m_air_1:
                position = adsb.position(m_air_0, m_air_1, t0, t1)
                altitude = adsb.altitude(m)


if __name__ == "__main__":
    t1 = time.time()
    native()
    dt1 = time.time() - t1

    t2 = time.time()
    cython()
    dt2 = time.time() - t2
