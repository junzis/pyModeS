import sys
import numpy as np
import pyModeS as pms
from rtlsdr import RtlSdr
from threading import Thread
import time

amplitude_threshold = 0.2
modes_sample_rate = 2e6
modes_frequency = 1090e6
buffer_size = 1024 * 100
read_size = 1024 * 8
pbits = 8
fbits = 112
preamble = "1010000101000000"


class RtlReader(Thread):
    def __init__(self, debug=False):
        super(RtlReader, self).__init__()
        self.signal_buffer = np.array([])
        self.debug = debug
        self.sdr = RtlSdr()
        self.sdr.sample_rate = modes_sample_rate
        self.sdr.center_freq = modes_frequency
        self.sdr.gain = "auto"
        # sdr.freq_correction = 75

    def _process_buffer(self):
        messages = []

        pulses_array = np.where(self.signal_buffer < amplitude_threshold, 0, 1)
        pulses = "".join(str(x) for x in pulses_array)

        i = 0
        while i < len(pulses):
            if pulses[i] == 0:
                i += 1
                continue

            if pulses[i : i + pbits * 2] == preamble:
                frame_start = i + pbits * 2
                frame_end = i + pbits * 2 + (fbits + 1) * 2
                frame_pulses = pulses[frame_start:frame_end]

                msgbin = ""
                for j in range(0, len(frame_pulses), 2):
                    p2 = frame_pulses[j : j + 2]
                    if p2 == "10":
                        c = "1"
                    elif p2 == "01":
                        c = "0"
                    elif p2 == "11":
                        a2 = self.signal_buffer[
                            frame_start + j : frame_start + j + 2
                        ]
                        if a2[0] > a2[1]:
                            c = "1"
                        else:
                            c = "0"
                    elif p2 == "00":
                        break
                    else:
                        msgbin = ""
                        break
                    msgbin += c

                # advance i with a jump
                i = frame_start + j

                if len(msgbin) > 0:
                    msghex = pms.bin2hex(msgbin)
                    if self._check_msg(msghex):
                        messages.append([msghex, time.time()])
                    if self.debug:
                        self._debug_msg(msghex)

            elif i > len(self.signal_buffer) - pbits * 2 - fbits * 2:
                break
            else:
                i += 1

        # keep reminder of buffer for next iteration
        self.signal_buffer = self.signal_buffer[i:]
        return messages

    def _check_msg(self, msg):
        df = pms.df(msg)
        msglen = len(msg)
        if df == 17 and msglen == 28:
            if pms.crc(msg) == 0:
                return True
        elif df in [20, 21] and msglen == 28:
            return True
        elif df in [4, 5, 11] and msglen == 14:
            return True

    def _debug_msg(self, msg):
        df = pms.df(msg)
        msglen = len(msg)
        if df == 17 and msglen == 28:
            print(msg, pms.icao(msg), pms.crc(msg))
        elif df in [20, 21] and msglen == 28:
            print(msg, pms.icao(msg))
        elif df in [4, 5, 11] and msglen == 14:
            print(msg, pms.icao(msg))
        else:
            print("[*]", msg)
            pass

    def _read_callback(self, data, rtlsdr_obj):
        self.signal_buffer = np.concatenate(
            (self.signal_buffer, np.absolute(data))
        )

        if len(self.signal_buffer) >= buffer_size:
            try:
                messages = self._process_buffer()
                self.handle_messages(messages)
            except KeyboardInterrupt:
                sys.exit(1)

    def handle_messages(self, messages):
        """re-implement this method to handle the messages"""
        for msg, t in messages:
            pass
            # print("%15.9f %s" % (t, msg))

    def run(self):
        self.sdr.read_samples_async(self._read_callback, read_size)
        # while True:
        #     data = self.sdr.read_samples(read_size)
        #     self._read_callback(data, None)


if __name__ == "__main__":
    rtl = RtlReader()
    rtl.debug = True
    # rtl.daemon = True
    rtl.start()
