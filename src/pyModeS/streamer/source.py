import pyModeS as pms
from pyModeS.extra.tcpclient import TcpClient
from pyModeS.extra.rtlreader import RtlReader


class NetSource(TcpClient):
    def __init__(self, host, port, rawtype):
        super(NetSource, self).__init__(host, port, rawtype)
        self.reset_local_buffer()

    def reset_local_buffer(self):
        self.local_buffer_adsb_msg = []
        self.local_buffer_adsb_ts = []
        self.local_buffer_commb_msg = []
        self.local_buffer_commb_ts = []

    def handle_messages(self, messages):

        if self.stop_flag.value is True:
            self.stop()
            return

        for msg, t in messages:
            if len(msg) < 28:  # only process long messages
                continue

            df = pms.df(msg)

            if df == 17 or df == 18:
                self.local_buffer_adsb_msg.append(msg)
                self.local_buffer_adsb_ts.append(t)
            elif df == 20 or df == 21:
                self.local_buffer_commb_msg.append(msg)
                self.local_buffer_commb_ts.append(t)
            else:
                continue

        if len(self.local_buffer_adsb_msg) > 1:
            self.raw_pipe_in.send(
                {
                    "adsb_ts": self.local_buffer_adsb_ts,
                    "adsb_msg": self.local_buffer_adsb_msg,
                    "commb_ts": self.local_buffer_commb_ts,
                    "commb_msg": self.local_buffer_commb_msg,
                }
            )
            self.reset_local_buffer()


class RtlSdrSource(RtlReader):
    def __init__(self):
        super(RtlSdrSource, self).__init__()
        self.reset_local_buffer()

    def reset_local_buffer(self):
        self.local_buffer_adsb_msg = []
        self.local_buffer_adsb_ts = []
        self.local_buffer_commb_msg = []
        self.local_buffer_commb_ts = []

    def handle_messages(self, messages):

        if self.stop_flag.value is True:
            self.stop()
            return

        for msg, t in messages:
            if len(msg) < 28:  # only process long messages
                continue

            df = pms.df(msg)

            if df == 17 or df == 18:
                self.local_buffer_adsb_msg.append(msg)
                self.local_buffer_adsb_ts.append(t)
            elif df == 20 or df == 21:
                self.local_buffer_commb_msg.append(msg)
                self.local_buffer_commb_ts.append(t)
            else:
                continue

        if len(self.local_buffer_adsb_msg) > 1:
            self.raw_pipe_in.send(
                {
                    "adsb_ts": self.local_buffer_adsb_ts,
                    "adsb_msg": self.local_buffer_adsb_msg,
                    "commb_ts": self.local_buffer_commb_ts,
                    "commb_msg": self.local_buffer_commb_msg,
                }
            )
            self.reset_local_buffer()
