#!/usr/bin/env python

import os
import sys
import time
import argparse
import curses
import signal
import multiprocessing
from pyModeS.streamer.decode import Decode
from pyModeS.streamer.screen import Screen
from pyModeS.streamer.source import NetSource, RtlSdrSource  # , RtlSdrSource24


def main():

    support_rawtypes = ["raw", "beast", "skysense"]

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        help='Choose data source, "rtlsdr", "rtlsdr24" or "net"',
        required=True,
        default="net",
    )
    parser.add_argument(
        "--connect",
        help="Define server, port and data type. Supported data types are: {}".format(
            support_rawtypes
        ),
        nargs=3,
        metavar=("SERVER", "PORT", "DATATYPE"),
        default=None,
        required=False,
    )
    parser.add_argument(
        "--latlon",
        help="Receiver latitude and longitude, needed for the surface position, default none",
        nargs=2,
        metavar=("LAT", "LON"),
        default=None,
        required=False,
    )
    parser.add_argument(
        "--show-uncertainty",
        dest="uncertainty",
        help="Display uncertainty values, default off",
        action="store_true",
        required=False,
        default=False,
    )
    parser.add_argument(
        "--dumpto",
        help="Folder to dump decoded output, default none",
        required=False,
        default=None,
    )
    args = parser.parse_args()

    SOURCE = args.source
    LATLON = args.latlon
    UNCERTAINTY = args.uncertainty
    DUMPTO = args.dumpto

    if SOURCE in ["rtlsdr", "rtlsdr24"]:
        pass
    elif SOURCE == "net":
        if args.connect is None:
            print("Error: --connect argument must not be empty.")
        else:
            SERVER, PORT, DATATYPE = args.connect
            if DATATYPE not in support_rawtypes:
                print(
                    "Data type not supported, available ones are %s"
                    % support_rawtypes
                )

    else:
        print('Source must be "rtlsdr" or "net".')
        sys.exit(1)

    if DUMPTO is not None:
        # append to current folder except root is given
        if DUMPTO[0] != "/":
            DUMPTO = os.getcwd() + "/" + DUMPTO

        if not os.path.isdir(DUMPTO):
            print("Error: dump folder (%s) does not exist" % DUMPTO)
            sys.exit(1)

    # redirect all stdout to null, avoiding messing up with the screen
    sys.stdout = open(os.devnull, "w")

    raw_pipe_in, raw_pipe_out = multiprocessing.Pipe()
    ac_pipe_in, ac_pipe_out = multiprocessing.Pipe()
    exception_queue = multiprocessing.Queue()
    stop_flag = multiprocessing.Value("b", False)

    if SOURCE == "net":
        source = NetSource(host=SERVER, port=PORT, rawtype=DATATYPE)
    elif SOURCE == "rtlsdr":
        source = RtlSdrSource()
    # elif SOURCE == "rtlsdr24":
    #     source = RtlSdrSource24()

    recv_process = multiprocessing.Process(
        target=source.run, args=(raw_pipe_in, stop_flag, exception_queue)
    )

    decode = Decode(latlon=LATLON, dumpto=DUMPTO)
    decode_process = multiprocessing.Process(
        target=decode.run, args=(raw_pipe_out, ac_pipe_in, exception_queue)
    )

    screen = Screen(uncertainty=UNCERTAINTY)
    screen_process = multiprocessing.Process(
        target=screen.run, args=(ac_pipe_out, exception_queue)
    )

    def shutdown():
        stop_flag.value = True
        curses.endwin()
        sys.stdout = sys.__stdout__
        recv_process.terminate()
        decode_process.terminate()
        screen_process.terminate()
        recv_process.join()
        decode_process.join()
        screen_process.join()

    def closeall(signal, frame):
        print("KeyboardInterrupt (ID: {}). Cleaning up...".format(signal))
        shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, closeall)

    recv_process.start()
    decode_process.start()
    screen_process.start()

    while True:
        if (
            (not recv_process.is_alive())
            or (not decode_process.is_alive())
            or (not screen_process.is_alive())
        ):
            shutdown()
            while not exception_queue.empty():
                trackback = exception_queue.get()
                print(trackback)

            sys.exit(1)

        time.sleep(0.01)
