from __future__ import absolute_import, print_function, division
import numpy as np
import time
import pyModeS as pms

class Stream():
    def __init__(self, lat0, lon0):

        self.acs = dict()

        self.cache_new_acs = False
        self.__new_acs = set()

        self.lat0 = lat0
        self.lon0 = lon0

        self.t = 0
        self.cache_timeout = 60     # seconds


    def process_raw(self, adsb_ts, adsb_msgs, commb_ts, commb_msgs, tnow=None):
        """process a chunk of adsb and commb messages recieved in the same
        time period.
        """
        if tnow is None:
            tnow = time.time()

        self.t = tnow

        local_updated_acs_buffer = []

        # process adsb message
        for t, msg in zip(adsb_ts, adsb_msgs):
            icao = pms.icao(msg)
            tc = pms.adsb.typecode(msg)

            if icao not in self.acs:
                self.acs[icao] = {
                    'live': None,
                    'call': None,
                    'lat': None,
                    'lon': None,
                    'alt': None,
                    'gs': None,
                    'trk': None,
                    'roc': None,
                    'tas': None,
                    'roll': None,
                    'ias': None,
                    'mach': None,
                    'hdg': None,
                    'ver' : None,
                    'HPL' : None,
                    'RCu' : None,
                    'RCv' : None,
                    'HVE' : None,
                    'VVE' : None,
                    'Rc' : None,
                    'VPL' : None,
                    'EPU' : None,
                    'VEPU' : None,
                    'HFOMr' : None,
                    'VFOMr' : None,
                    'PE_RCu' : None,
                    'PE_VPL' : None,
                }

            self.acs[icao]['t'] = t
            self.acs[icao]['live'] = int(t)

            if 1 <= tc <= 4:
                self.acs[icao]['call'] = pms.adsb.callsign(msg)

            if (5 <= tc <= 8) or (tc == 19):
                vdata = pms.adsb.velocity(msg)
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
                oe = pms.adsb.oe_flag(msg)
                self.acs[icao][oe] = msg
                self.acs[icao]['t'+str(oe)] = t

                if ('tpos' in self.acs[icao]) and (t - self.acs[icao]['tpos'] < 180):
                    # use single message decoding
                    rlat = self.acs[icao]['lat']
                    rlon = self.acs[icao]['lon']
                    latlon = pms.adsb.position_with_ref(msg, rlat, rlon)
                elif ('t0' in self.acs[icao]) and ('t1' in self.acs[icao]) and \
                     (abs(self.acs[icao]['t0'] - self.acs[icao]['t1']) < 10):
                    # use multi message decoding
                    # try:
                    latlon = pms.adsb.position(
                        self.acs[icao][0],
                        self.acs[icao][1],
                        self.acs[icao]['t0'],
                        self.acs[icao]['t1'],
                        self.lat0, self.lon0
                        )
                    # except:
                    #     # mix of surface and airborne position message
                    #     continue
                else:
                    latlon = None

                if latlon is not None:
                    self.acs[icao]['tpos'] = t
                    self.acs[icao]['lat'] = latlon[0]
                    self.acs[icao]['lon'] = latlon[1]
                    self.acs[icao]['alt'] = pms.adsb.altitude(msg)
                    local_updated_acs_buffer.append(icao)

            # Uncertainty & accuracy
            ac = self.acs[icao]

            if 9 <= tc <= 18:
                ac['nic_bc'] = pms.adsb.nic_b(msg)

            if (5 <= tc <= 8) or (9 <= tc <= 18) or (20 <= tc <= 22):
                ac['HPL'], ac['RCu'], ac['RCv'] = pms.adsb.nuc_p(msg)

                if (ac['ver'] == 1) and ('nic_s' in ac.keys()):
                    ac['Rc'], ac['VPL'] = pms.adsb.nic_v1(msg, ac['nic_s'])
                elif (ac['ver'] == 2) and ('nic_a' in ac.keys()) and ('nic_bc' in ac.keys()):
                    ac['Rc'] = pms.adsb.nic_v2(msg, ac['nic_a'], ac['nic_bc'])

            if tc == 19:
                ac['HVE'], ac['VVE'] = pms.adsb.nuc_v(msg)
                if ac['ver'] in [1, 2]:
                    ac['HFOMr'], ac['VFOMr'] = pms.adsb.nac_v(msg)

            if tc == 29:
                ac['PE_RCu'], ac['PE_VPL'], ac['base'] = pms.adsb.sil(msg, ac['ver'])
                ac['EPU'], ac['VEPU'] = pms.adsb.nac_p(msg)

            if tc == 31:
                ac['ver']  = pms.adsb.version(msg)
                ac['EPU'], ac['VEPU'] = pms.adsb.nac_p(msg)
                ac['PE_RCu'], ac['PE_VPL'], ac['sil_base'] = pms.adsb.sil(msg, ac['ver'])

                if ac['ver']  == 1:
                    ac['nic_s'] = pms.adsb.nic_s(msg)
                elif ac['ver']  == 2:
                    ac['nic_a'], ac['nic_bc'] = pms.adsb.nic_a_c(msg)


        # process commb message
        for t, msg in zip(commb_ts, commb_msgs):
            icao = pms.icao(msg)

            if icao not in self.acs:
                continue

            bds = pms.bds.infer(msg)

            if bds == 'BDS50':
                tas = pms.commb.tas50(msg)
                roll = pms.commb.roll50(msg)

                self.acs[icao]['t50'] = t
                if tas:
                    self.acs[icao]['tas'] = tas
                if roll:
                    self.acs[icao]['roll'] = roll

            elif bds == 'BDS60':
                ias = pms.commb.ias60(msg)
                hdg = pms.commb.hdg60(msg)
                mach = pms.commb.mach60(msg)

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
            if self.t - self.acs[icao]['live'] > self.cache_timeout:
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
            if ac in self.acs:
                newacs[ac] = self.acs[ac]
        return newacs

    def reset_new_aircraft(self):
        """reset the updated icao buffer once been read"""
        self.__new_acs = set()
