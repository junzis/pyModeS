"""Stream beast raw data from a TCP server, convert to mode-s messages."""

import os
import sys
import time
import pyModeS as pms
import traceback
import zmq


class TcpClient(object):
    def __init__(self, host, port, datatype):
        super(TcpClient, self).__init__()
        self.host = host
        self.port = port
        self.buffer = []
        self.socket = None
        self.datatype = datatype
        if self.datatype not in ["raw", "beast", "skysense"]:
            print("datatype must be either raw, beast or skysense")
            os._exit(1)

        self.raw_pipe_in = None
        self.stop_flag = False

        self.exception_queue = None

    def connect(self):
        self.socket = zmq.Context().socket(zmq.STREAM)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.setsockopt(zmq.RCVTIMEO, 10000)
        self.socket.connect("tcp://%s:%s" % (self.host, self.port))

    def stop(self):
        self.socket.close()

    def read_raw_buffer(self):
        """ Read raw ADS-B data type.

        String strats with "*" and ends with ";". For example:
            *5d484ba898f8c6;
            *8d400cd5990d7e9a10043e5e6da0;
            *a0001498be800030aa0000c7a75f;
        """
        messages = []

        msg_stop = False
        self.current_msg = ""
        for b in self.buffer:
            if b == 59:
                msg_stop = True
                ts = time.time()
                messages.append([self.current_msg, ts])
            if b == 42:
                msg_stop = False
                self.current_msg = ""

            if (not msg_stop) and (48 <= b <= 57 or 65 <= b <= 70 or 97 <= b <= 102):
                self.current_msg = self.current_msg + chr(b)

        self.buffer = []

        return messages

    def read_beast_buffer(self):
        """Handle mode-s beast data type.

        <esc> "1" : 6 byte MLAT timestamp, 1 byte signal level,
            2 byte Mode-AC
        <esc> "2" : 6 byte MLAT timestamp, 1 byte signal level,
            7 byte Mode-S short frame
        <esc> "3" : 6 byte MLAT timestamp, 1 byte signal level,
            14 byte Mode-S long frame
        <esc> "4" : 6 byte MLAT timestamp, status data, DIP switch
            configuration settings (not on Mode-S Beast classic)
        <esc><esc>: true 0x1a
        <esc> is 0x1a, and "1", "2" and "3" are 0x31, 0x32 and 0x33

        timestamp:
        wiki.modesbeast.com/Radarcape:Firmware_Versions#The_GPS_timestamp
        """
        messages_mlat = []
        msg = []
        i = 0

        # process the buffer until the last divider <esc> 0x1a
        # then, reset the self.buffer with the remainder

        while i < len(self.buffer):
            if self.buffer[i : i + 2] == [0x1A, 0x1A]:
                msg.append(0x1A)
                i += 1
            elif (i == len(self.buffer) - 1) and (self.buffer[i] == 0x1A):
                # special case where the last bit is 0x1a
                msg.append(0x1A)
            elif self.buffer[i] == 0x1A:
                if i == len(self.buffer) - 1:
                    # special case where the last bit is 0x1a
                    msg.append(0x1A)
                elif len(msg) > 0:
                    messages_mlat.append(msg)
                    msg = []
            else:
                msg.append(self.buffer[i])
            i += 1

        # save the reminder for next reading cycle, if not empty
        if len(msg) > 0:
            reminder = []
            for i, m in enumerate(msg):
                if (m == 0x1A) and (i < len(msg) - 1):
                    # rewind 0x1a, except when it is at the last bit
                    reminder.extend([m, m])
                else:
                    reminder.append(m)
            self.buffer = [0x1A] + msg
        else:
            self.buffer = []

        # extract messages
        messages = []
        for mm in messages_mlat:
            ts = time.time()

            msgtype = mm[0]
            # print(''.join('%02X' % i for i in mm))

            if msgtype == 0x32:
                # Mode-S Short Message, 7 byte, 14-len hexstr
                msg = "".join("%02X" % i for i in mm[8:15])
            elif msgtype == 0x33:
                # Mode-S Long Message, 14 byte, 28-len hexstr
                msg = "".join("%02X" % i for i in mm[8:22])
            else:
                # Other message tupe
                continue

            if len(msg) not in [14, 28]:
                continue

            df = pms.df(msg)

            # skip incomplete message
            if df in [0, 4, 5, 11] and len(msg) != 14:
                continue
            if df in [16, 17, 18, 19, 20, 21, 24] and len(msg) != 28:
                continue

            messages.append([msg, ts])
        return messages

    def read_skysense_buffer(self):
        """Skysense stream format.

        ::

            ----------------------------------------------------------------------------------
            Field      SS MS MS MS MS MS MS MS MS MS MS MS MS MS MS TS TS TS TS TS TS RS RS RS
            ----------------------------------------------------------------------------------
            Position:   0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23
            ----------------------------------------------------------------------------------

            SS field - Start character
            Position 0:
              1 byte = 8 bits
              Start character '$'

            MS field - Payload
            Position 1 through 14:
              14 bytes = 112 bits
              Mode-S payload
              In case of DF types that only carry 7 bytes of information
                position 8 through 14 are set to 0x00.

            TS field - Time stamp
            Position 15 through 20:
              6 bytes = 48 bits
              Time stamp with fields as:

                Lock Status - Status of internal time keeping mechanism
                Equal to 1 if operating normally
                Bit 47 - 1 bit

                Time of day in UTC seconds, between 0 and 86399
                Bits 46 through 30 - 17 bits

                Nanoseconds into current second, between 0 and 999999999
                Bits 29 through 0 - 30 bits

            RS field - Signal Level
            Position 21 through 23:
              3 bytes = 24 bits
              RSSI (received signal strength indication) and relative
                noise level with fields

              RNL, Q12.4 unsigned fixed point binary with 4 fractional
                bits and 8 integer bits.
              This is and indication of the noise level of the message.
                Roughly 40 counts per 10dBm.
              Bits 23 through 12 - 12 bits

              RSSI, Q12.4 unsigned fixed point binary with 4 fractional
                bits and 8 integer bits.
              This is an indication of the signal level of the received
                message in ADC counts. Roughly 40 counts per 10dBm.
              Bits 11 through 0 - 12 bits
        """
        SS_MSGLENGTH = 24
        SS_STARTCHAR = 0x24

        if len(self.buffer) <= SS_MSGLENGTH:
            return None

        messages = []
        while len(self.buffer) > SS_MSGLENGTH:
            i = 0
            if (
                self.buffer[i] == SS_STARTCHAR
                and self.buffer[i + SS_MSGLENGTH] == SS_STARTCHAR
            ):
                i += 1
                if self.buffer[i] >> 7:
                    # Long message
                    payload = self.buffer[i : i + 14]
                else:
                    # Short message
                    payload = self.buffer[i : i + 7]
                msg = "".join("%02X" % j for j in payload)
                i += 14  # Both message types use 14 bytes
                tsbin = self.buffer[i : i + 6]
                sec = ((tsbin[0] & 0x7F) << 10) | (tsbin[1] << 2) | (tsbin[2] >> 6)
                nano = (
                    ((tsbin[2] & 0x3F) << 24)
                    | (tsbin[3] << 16)
                    | (tsbin[4] << 8)
                    | tsbin[5]
                )
                ts = sec + nano * 1.0e-9
                i += 6
                # Signal and noise level - Don't care for now
                i += 3
                self.buffer = self.buffer[SS_MSGLENGTH:]
                messages.append([msg, ts])
            else:
                self.buffer = self.buffer[1:]
        return messages

    def handle_messages(self, messages):
        """re-implement this method to handle the messages"""
        for msg, t in messages:
            print("%15.9f %s" % (t, msg))

    def run(self, raw_pipe_in=None, stop_flag=None, exception_queue=None):
        self.raw_pipe_in = raw_pipe_in
        self.exception_queue = exception_queue
        self.stop_flag = stop_flag
        self.connect()

        while True:
            try:
                received = [i for i in self.socket.recv(4096)]

                self.buffer.extend(received)
                # print(''.join(x.encode('hex') for x in self.buffer))

                if self.datatype == "beast":
                    messages = self.read_beast_buffer()
                elif self.datatype == "raw":
                    messages = self.read_raw_buffer()
                elif self.datatype == "skysense":
                    messages = self.read_skysense_buffer()

                if not messages:
                    continue
                else:
                    self.handle_messages(messages)

                # raise RuntimeError("test exception")

            except zmq.error.Again:
                continue
            except Exception as e:
                tb = traceback.format_exc()
                if self.exception_queue is not None:
                    self.exception_queue.put(tb)
                raise e


if __name__ == "__main__":
    # for testing purpose only
    host = sys.argv[1]
    port = int(sys.argv[2])
    datatype = sys.argv[3]
    client = TcpClient(host=host, port=port, datatype=datatype)
    try:
        client.run()
    finally:
        client.stop()
