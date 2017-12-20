'''
Stream beast raw data from a TCP server, convert to mode-s messages
'''
from __future__ import print_function, division
import sys
import socket
import time
from threading import Thread

if (sys.version_info > (3, 0)):
    PY_VERSION = 3
else:
    PY_VERSION = 2

class BaseClient(Thread):
    def __init__(self, host, port):
        Thread.__init__(self)
        self.host = host
        self.port = port
        self.buffer = []


    def connect(self):
        while True:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)    # 10 second timeout
                s.connect((self.host, self.port))
                print("Server connected - %s:%s" % (self.host, self.port))
                print("collecting ADS-B messages...")
                return s
            except socket.error as err:
                print("Socket connection error: %s. reconnecting..." % err)
                time.sleep(3)

    def read_beast_buffer(self):
        '''
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
        '''

        messages_mlat = []
        msg = []
        i = 0

        # process the buffer until the last divider <esc> 0x1a
        # then, reset the self.buffer with the remainder

        while i < len(self.buffer):
            if (self.buffer[i:i+2] == [0x1a, 0x1a]):
                msg.append(0x1a)
                i += 1
            elif (i == len(self.buffer) - 1) and (self.buffer[i] == 0x1a):
                # special case where the last bit is 0x1a
                msg.append(0x1a)
            elif self.buffer[i] == 0x1a:
                if i == len(self.buffer) - 1:
                    # special case where the last bit is 0x1a
                    msg.append(0x1a)
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
                if (m == 0x1a) and (i < len(msg)-1):
                    # rewind 0x1a, except when it is at the last bit
                    reminder.extend([m, m])
                else:
                    reminder.append(m)
            self.buffer = [0x1a] + msg
        else:
            self.buffer = []

        # extract messages
        messages = []
        for mm in messages_mlat:
            msgtype = mm[0]
            # print(''.join('%02X' % i for i in mm))

            if msgtype == 0x32:
                # Mode-S Short Message, 7 byte, 14-len hexstr
                msg = ''.join('%02X' % i for i in mm[8:15])
            elif msgtype == 0x33:
                # Mode-S Long Message, 14 byte, 28-len hexstr
                msg = ''.join('%02X' % i for i in mm[8:22])
            else:
                # Other message tupe
                continue

            if len(msg) not in [14, 28]:
                # incomplete message
                continue

            ts = time.time()

            messages.append([msg, ts])
        return messages

    def handle_messages(self, messages):
        """re-implement this method to handle the messages"""
        for msg, t in messages:
            print("%f %s" % (t, msg))

    def run(self):
        sock = self.connect()

        while True:
            try:
                received = sock.recv(1024)

                if PY_VERSION == 2:
                    received = [ord(i) for i in received]

                self.buffer.extend(received)
                # print(''.join(x.encode('hex') for x in self.buffer))

                # process self.buffer when it is longer enough
                # if len(self.buffer) < 2048:
                #     continue
                # -- Removed!! Cause delay in low data rate scenario --

                messages = self.read_beast_buffer()

                if not messages:
                    continue
                else:
                    self.handle_messages(messages)

                time.sleep(0.001)
            except Exception as e:
                print("Unexpected Error:", e)

                try:
                    sock = self.connect()
                except Exception as e:
                    print("Unexpected Error:", e)



if __name__ == '__main__':
    # for testing purpose only
    host = sys.argv[1]
    port = int(sys.argv[2])
    client = BaseClient(host=host, port=port)
    client.daemon = True
    client.run()
