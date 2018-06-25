from __future__ import absolute_import, print_function, division
import numpy as np
import time
from pyModeS.decoder import adsb, ehs

class Stream():
    def __init__(self, lat0, lon0):

        self.acs = dict()

        self.cache_new_acs = False
        self.__new_acs = set()

        self.lat0 = lat0
        self.lon0 = lon0

        self.t = 0
        self.cache_timeout = 60     # seconds


    def process_raw(self, adsb_ts, adsb_msgs, ehs_ts, ehs_msgs, tnow=None):
        """process a chunk of adsb and ehs messages recieved in the same
        time period.
        """
        if tnow is None:
            tnow = time.time()

        self.t = tnow

        local_updated_acs_buffer = []

        # process adsb message
        for t, msg in zip(adsb_ts, adsb_msgs):
            icao = adsb.icao(msg)
            tc = adsb.typecode(msg)

            if icao not in self.acs:
                self.acs[icao] = {
                    'lat': None,
                    'lon': None,
                    'alt': None,
                    'gs': None,
                    'trk': None,
                    'roc': None,
                    'tas': None,
                    'ias': None,
                    'mach': None,
                    'hdg': None,
                    'adsb_version' : None,    
                    'nic_s' : None,
                    'nic_a' : None,
                    'nic_b' : None,
                    'nic_c' : None
                }

            self.acs[icao]['t'] = t

            if 1 <= tc <= 4:
                self.acs[icao]['callsign'] = adsb.callsign(msg)

            if (5 <= tc <= 8) or (tc == 19):
                vdata = adsb.velocity(msg)
                if vdata is None:
                    continue

                spd, trk, roc, tag = vdata
                if tag != 'GS':
                    continue
                if (spd is None) or (trk is None):
                    continue

                self.acs[icao]['gs'] = spd
                self.acs[icao]['trk'] = trk
                self.acs[icao]['roc'] = roc
                self.acs[icao]['tv'] = t

            if (5 <= tc <= 18):
                oe = adsb.oe_flag(msg)
                self.acs[icao][oe] = msg
                self.acs[icao]['t'+str(oe)] = t

                if ('tpos' in self.acs[icao]) and (t - self.acs[icao]['tpos'] < 180):
                    # use single message decoding
                    rlat = self.acs[icao]['lat']
                    rlon = self.acs[icao]['lon']
                    latlon = adsb.position_with_ref(msg, rlat, rlon)
                elif ('t0' in self.acs[icao]) and ('t1' in self.acs[icao]) and \
                     (abs(self.acs[icao]['t0'] - self.acs[icao]['t1']) < 10):
                    # use multi message decoding
                    try:
                        latlon = adsb.position(
                            self.acs[icao][0],
                            self.acs[icao][1],
                            self.acs[icao]['t0'],
                            self.acs[icao]['t1'],
                            self.lat0, self.lon0
                            )
                    except:
                        # mix of surface and airborne position message
                        continue
                else:
                    latlon = None

                if latlon is not None:
                    self.acs[icao]['tpos'] = t
                    self.acs[icao]['lat'] = latlon[0]
                    self.acs[icao]['lon'] = latlon[1]
                    self.acs[icao]['alt'] = adsb.altitude(msg)
                    # local_updated_acs_buffer.append(icao)acs[icao]['adsb_version']
                    local_updated_acs_buffer.append(acs[icao]['adsb_version'])

            # Uncertainty & accuracy
            if (5 <= tc <= 8):
                if self.acs[icao]['adsb_version']  == 1:
                    if self.acs[icao]['nic_s'] != None:
                        self.nic = adsb.nic_v1(msg,self.acs[icao]['nic_s'])
                elif self.acs[icao]['adsb_version']  == 2:
                    if self.acs[icao]['nic_a'] != None and self.acs[icao]['nic_b'] != None:
                        self.nic = adsb.nic_v2(msg,self.nic_a,self.acs[icao]['nic_b'],self.acs[icao]['nic_c'])
            if (9 <= tc <= 18):
                if self.acs[icao]['adsb_version']  == 1:
                    if self.acs[icao]['nic_s'] != None:
                        self.nic = adsb.nic_v1(msg,self.acs[icao]['nic_s'])
                elif self.acs[icao]['adsb_version']  == 2:
                    self.acs[icao]['nic_b'] = adsb.nic_b(msg)
                    if self.acs[icao]['nic_a'] != None and self.acs[icao]['nic_b'] != None:
                        self.nic = adsb.nic_v2(msg,self.acs[icao]['nic_a'],self.nic_b,self.acs[icao]['nic_c'])
            if tc == 19:
                self.acs[icao]['nac_v'] = adsb.nac_v(msg)
            if (20 <= tc <= 22):
                if self.acs[icao]['adsb_version']  == 1:
                    if self.acs[icao]['nic_s'] != None:
                        self.nic = adsb.nic_v1(msg,self.acs[icao]['nic_s'])
                elif self.acs[icao]['adsb_version']  == 2:
                    if self.acs[icao]['nic_a'] != None and self.acs[icao]['nic_b'] != None:
                        self.nic = adsb.nic_v2(msg,self.acs[icao]['nic_a'],self.acs[icao]['nic_b'],self.acs[icao]['nic_c'])
            if tc == 29:
                if self.acs[icao]['adsb_version'] != None:
                    self.acs[icao]['sil'] = adsb.sil(msg,self.acs[icao]['adsb_version'])
                self.acs[icao]['nac_p'] = adsb.nac_p(msg)
            if tc == 31:
                self.acs[icao]['adsb_version']  = adsb.version(msg)
                self.acs[icao]['sil'] = adsb.version(msg)
                self.acs[icao]['nac_p'] = adsb.nac_p(msg)
                if self.acs[icao]['adsb_version']  == 1:
                    self.acs[icao]['nic_s'] = adsb.nic_s(msg)
                elif self.acs[icao]['adsb_version']  == 2:
                    self.acs[icao]['nic_a'] , self.acs[icao]['nic_c'] = adsb.nic_a_and_c(msg)


                

        # process ehs message
        for t, msg in zip(ehs_ts, ehs_msgs):
            icao = ehs.icao(msg)

            if icao not in self.acs:
                continue

            bds = ehs.BDS(msg)

            if bds == 'BDS50':
                tas = ehs.tas50(msg)

                if tas:
                    self.acs[icao]['t50'] = t
                    self.acs[icao]['tas'] = tas

            elif bds == 'BDS60':
                ias = ehs.ias60(msg)
                hdg = ehs.hdg60(msg)
                mach = ehs.mach60(msg)

                if ias or hdg or mach:
                    self.acs[icao]['t60'] = t
                if ias:
                    self.acs[icao]['ias'] = ias
                if hdg:
                    self.acs[icao]['hdg'] = hdg
                if mach:
                    self.acs[icao]['mach'] = mach

        # clear up old data
        for icao in list(self.acs.keys()):
            if self.t - self.acs[icao]['t'] > self.cache_timeout:
                del self.acs[icao]
                continue

        if self.cache_new_acs:
            self.add_new_aircraft(local_updated_acs_buffer)

        return

    def get_aircraft(self):
        """all aircraft that are stored in memeory"""
        acs = self.acs
        icaos = list(acs.keys())
        for icao in icaos:
            if acs[icao]['lat'] is None:
                acs.pop(icao)
        return acs

    def add_new_aircraft(self, acs):
        """add new aircraft to the list"""
        self.__new_acs.update(acs)
        return

    def get_new_aircraft(self):
        """update aircraft from last iteration"""
        newacs = dict()
        for ac in self.__new_acs:
            newacs[ac] = self.acs[ac]
        return newacs

    def reset_new_aircraft(self):
        """reset the updated icao buffer once been read"""
        self.__new_acs = set()