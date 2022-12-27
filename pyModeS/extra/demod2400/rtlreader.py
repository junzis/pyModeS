import time
import traceback
import numpy as np
import pyModeS as pms
from pyModeS.extra.demod2400 import demod2400


try:
    import rtlsdr  # type: ignore
except ImportError:
    print(
        "------------------------------------------------------------------------"
    )
    print(
        "! Warning: pyrtlsdr not installed (required for using RTL-SDR devices) !"
    )
    print(
        "------------------------------------------------------------------------"
    )

modes_frequency = 1090e6
sampling_rate = 2.4e6
buffer_size = 16 * 16384
read_size = buffer_size / 2


class RtlReader(object):
    def __init__(self, **kwargs):
        super(RtlReader, self).__init__()
        self.signal_buffer = []  # amplitude of the sample only
        self.sdr = rtlsdr.RtlSdr()
        self.sdr.sample_rate = sampling_rate
        self.sdr.center_freq = modes_frequency
        self.sdr.gain = "auto"

        self.debug = kwargs.get("debug", False)
        self.raw_pipe_in = None
        self.stop_flag = False
        self.exception_queue = None

    def _process_buffer(self):
        """process raw IQ data in the buffer"""

        # Mode S messages
        messages = []

        data = (np.array(self.signal_buffer) * 65535).astype(np.uint16)

        for s in demod2400(data, self.timestamp):
            if s["payload"] is None:
                idx = s["index"]
                # reset the buffer
                self.signal_buffer = self.signal_buffer[idx:]
                self.timestamp = s["timestamp"]
                break
            if self._check_msg(s["payload"]):
                messages.append([s["payload"], time.time()])  # s["timestamp"]])
            if self.debug:
                self._debug_msg(s["payload"])

        self.timestamp = s["timestamp"]
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
            print(msg, pms.icao(msg), df, pms.crc(msg))
            print(pms.tell(msg))
        elif df in [20, 21] and msglen == 28:
            print(msg, pms.icao(msg), df)
        elif df in [4, 5, 11] and msglen == 14:
            print(msg, pms.icao(msg), df)
        else:
            # print("[*]", msg)
            pass

    def _read_callback(self, data, rtlsdr_obj):
        amp = np.absolute(data)
        self.signal_buffer.extend(amp.tolist())

        if len(self.signal_buffer) >= buffer_size:
            messages = self._process_buffer()
            self.handle_messages(messages)

    def handle_messages(self, messages):
        """re-implement this method to handle the messages"""
        for msg, t in messages:
            # print("%15.9f %s" % (t, msg))
            pass

    def stop(self, *args, **kwargs):
        self.sdr.close()

    def run(self, raw_pipe_in=None, stop_flag=None, exception_queue=None):
        self.raw_pipe_in = raw_pipe_in
        self.exception_queue = exception_queue
        self.stop_flag = stop_flag

        try:
            # raise RuntimeError("test exception")
            self.timestamp = time.time()

            while True:
                data = self.sdr.read_samples(read_size)
                self._read_callback(data, None)

        except Exception as e:
            tb = traceback.format_exc()
            if self.exception_queue is not None:
                self.exception_queue.put(tb)
            raise e


if __name__ == "__main__":
    import signal

    rtl = RtlReader()
    signal.signal(signal.SIGINT, rtl.stop)

    rtl.debug = True
    rtl.run()
