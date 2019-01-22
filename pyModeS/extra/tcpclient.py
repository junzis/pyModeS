'''
Stream beast raw data from a TCP server, convert to mode-s messages
'''
from __future__ import print_function, division
import os
import sys
import socket
import time
from threading import Thread

if (sys.version_info > (3, 0)):
    PY_VERSION = 3
else:
    PY_VERSION = 2

class BaseClient(Thread):
    def __init__(self, host, port, rawtype):
        Thread.__init__(self)
        self.host = host
        self.port = port
        self.buffer = []
        self.rawtype = rawtype
        if self.rawtype not in ['avr', 'beast', 'skysense']:
            print("rawtype must be either avr, beast or skysense")
            os._exit(1)

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


    def read_avr_buffer(self):
        # -- testing --
        # for b in self.buffer:
        #     print(chr(b), b)

        # Append message with 0-9,A-F,a-f, until stop sign

        messages = []

        msg_stop = False
        for b in self.buffer:
            if b == 59:
                msg_stop = True
                ts = time.time()
                messages.append([self.current_msg, ts])
            if b == 42:
                msg_stop = False
                self.current_msg = ''

            if (not msg_stop) and (48<=b<=57 or 65<=b<=70 or 97<=b<=102):
                self.current_msg = self.current_msg + chr(b)

        self.buffer = []

        return messages

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
            ts = time.time()

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

            messages.append([msg, ts])
        return messages

    def read_skysense_buffer(self):
        """
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
        Postion 1 through 14:
          14 bytes = 112 bits
          Mode-S payload
          In case of DF types that only carry 7 bytes of information position 8 through 14 are set to 0x00.
        
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
         RSSI (received signal strength indication) and relative noise level with fields
        
         RNL, Q12.4 unsigned fixed point binary with 4 fractional bits and 8 integer bits.
         This is and indication of the noise level of the message. Roughly 40 counts per 10dBm.
         Bits 23 through 12 - 12 bits 
        
         RSSI, Q12.4 unsigned fixed point binary with 4 fractional bits and 8 integer bits.
         This is an indication of the signal level of the received message in ADC counts. Roughly 40 counts per 10dBm.
         Bits 11 through 0 - 12 bits   
        """
        SS_MSGLENGTH = 24
        SS_STARTCHAR = 0x24

        if len(self.buffer) <= SS_MSGLENGTH:
            return None

        messages = []
        while len(self.buffer) > SS_MSGLENGTH:
            i = 0
            if self.buffer[i] == SS_STARTCHAR and self.buffer[i+SS_MSGLENGTH] == SS_STARTCHAR:
                i += 1
                if (self.buffer[i]>>7):
                    #Long message
                    payload = self.buffer[i:i+14]
                else:
                    #Short message
                    payload = self.buffer[i:i+7]
                msg = ''.join('%02X' % j for j in payload)
                i += 14 #Both message types use 14 bytes
                tsbin = self.buffer[i:i+6]
                sec   = ( (tsbin[0] & 0x7f) << 10) | (tsbin[1] << 2 ) | (tsbin[2] >> 6)
                nano  = ( (tsbin[2] & 0x3f) << 24) | (tsbin[3] << 16) | (tsbin[4] << 8) | tsbin[5]
                ts = sec + nano*1.0e-9
                i += 6
                #Signal and noise level - Don't care for now
                i += 3
                self.buffer = self.buffer[SS_MSGLENGTH:]
                messages.append( [msg,ts] )
            else:
                self.buffer = self.buffer[1:]  
        return messages

    def handle_messages(self, messages):
        """re-implement this method to handle the messages"""
        for msg, t in messages:
            print("%15.9f %s" % (t, msg))

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

                if self.rawtype == 'beast':
                    messages = self.read_beast_buffer()
                elif self.rawtype == 'avr':
                    messages = self.read_avr_buffer()
                elif self.rawtype == 'skysense':
                    messages = self.read_skysense_buffer()

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
    rawtype = sys.argv[3]
    client = BaseClient(host=host, port=port, rawtype=rawtype)
    client.daemon = True
    client.run()
