from __future__ import print_function, division
import os
import sys
import argparse
import curses
import numpy as np
import time
from threading import Lock
from pyModeS.decoder import util
from pyModeS.extra.beastclient import BaseClient
from pyModeS.streamer.stream import Stream
from pyModeS.streamer.screen import Screen

LOCK = Lock()
ADSB_MSG = []
ADSB_TS = []
EHS_MSG = []
EHS_TS = []

parser = argparse.ArgumentParser()
parser.add_argument('--server', help='server address or IP', required=True)
parser.add_argument('--port', help='Raw beast port', required=True)
parser.add_argument('--lat0', help='Latitude of receiver', required=True)
parser.add_argument('--lon0', help='Longitude of receiver', required=True)
args = parser.parse_args()

SERVER = args.server
PORT = int(args.port)
LAT0 = float(args.lat0)     # 51.9899 for TU Delft
LON0 = float(args.lon0)     # 4.3754

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

            df = util.df(msg)

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

client = ModesClient(host=SERVER, port=PORT)
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
