from __future__ import print_function, division
import os
import sys
import curses
import numpy as np
import time
import pyModeS as pms
from threading import Lock
from client import BaseClient
from stream import Stream
from screen import Screen

LOCK = Lock()
ADSB_MSG = []
ADSB_TS = []
EHS_MSG = []
EHS_TS = []

HOST = 'sil.lr.tudelft.nl'
PORT = 30334

LAT0 = 51.9899
LON0 = 4.3754

class ModesClient(BaseClient):
    def __init__(self, host, port):
        super(ModesClient, self).__init__(host, port)

    def handle_messages(self, messages):
        local_buffer_adsb_msg = []
        local_buffer_adsb_ts = []
        local_buffer_ehs_msg = []
        local_buffer_ehs_ts = []

        for msg, t in messages:
            if len(msg) < 28:           # only process long messages
                continue

            df = pms.df(msg)

            if df == 17 or df == 18:
                local_buffer_adsb_msg.append(msg)
                local_buffer_adsb_ts.append(t)
            elif df == 20 or df == 21:
                local_buffer_ehs_msg.append(msg)
                local_buffer_ehs_ts.append(t)
            else:
                continue


        LOCK.acquire()
        ADSB_MSG.extend(local_buffer_adsb_msg)
        ADSB_TS.extend(local_buffer_adsb_ts)
        EHS_MSG.extend(local_buffer_ehs_msg)
        EHS_TS.extend(local_buffer_ehs_ts)
        LOCK.release()


sys.stdout = open(os.devnull, 'w')

client = ModesClient(host=HOST, port=PORT)
client.daemon = True
client.start()

stream = Stream(lat0=LAT0, lon0=LON0)

try:
    screen = Screen()
    screen.daemon = True
    screen.start()

    while True:
        if len(ADSB_MSG) > 200:
            LOCK.acquire()
            stream.process_raw(ADSB_TS, ADSB_MSG, EHS_TS, EHS_MSG)
            ADSB_MSG = []
            ADSB_TS = []
            EHS_MSG = []
            EHS_TS = []
            LOCK.release()

        acs = stream.get_aircraft()
        # try:
        screen.update_data(acs)
        screen.update()
        # except KeyboardInterrupt:
        #     raise
        # except:
        #     continue

except KeyboardInterrupt:
    sys.exit(0)

finally:
    curses.endwin()
