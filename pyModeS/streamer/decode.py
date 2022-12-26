import os
import time
import traceback
import datetime
import csv
import pyModeS as pms


class Decode:
    def __init__(self, latlon=None, dumpto=None):

        self.acs = dict()

        if latlon is not None:
            self.lat0 = float(latlon[0])
            self.lon0 = float(latlon[1])
        else:
            self.lat0 = None
            self.lon0 = None

        self.t = 0
        self.cache_timeout = 60  # seconds

        if dumpto is not None and os.path.isdir(dumpto):
            self.dumpto = dumpto
        else:
            self.dumpto = None

    def process_raw(self, adsb_ts, adsb_msg, commb_ts, commb_msg, tnow=None):
        """process a chunk of adsb and commb messages received in the same
        time period.
        """
        if tnow is None:
            tnow = time.time()

        self.t = tnow

        local_updated_acs_buffer = []
        output_buffer = []

        # process adsb message
        for t, msg in zip(adsb_ts, adsb_msg):
            icao = pms.icao(msg)
            tc = pms.adsb.typecode(msg)

            if icao not in self.acs:
                self.acs[icao] = {
                    "live": None,
                    "call": None,
                    "lat": None,
                    "lon": None,
                    "alt": None,
                    "gs": None,
                    "trk": None,
                    "roc": None,
                    "tas": None,
                    "roll": None,
                    "rtrk": None,
                    "ias": None,
                    "mach": None,
                    "hdg": None,
                    "ver": None,
                    "HPL": None,
                    "RCu": None,
                    "RCv": None,
                    "HVE": None,
                    "VVE": None,
                    "Rc": None,
                    "VPL": None,
                    "EPU": None,
                    "VEPU": None,
                    "HFOMr": None,
                    "VFOMr": None,
                    "PE_RCu": None,
                    "PE_VPL": None,
                }

            self.acs[icao]["t"] = t
            self.acs[icao]["live"] = int(t)

            if 1 <= tc <= 4:
                cs = pms.adsb.callsign(msg)
                self.acs[icao]["call"] = cs
                output_buffer.append([t, icao, "cs", cs])

            if (5 <= tc <= 8) or (tc == 19):
                vdata = pms.adsb.velocity(msg)
                if vdata is None:
                    continue

                spd, trk, roc, tag = vdata
                if tag != "GS":
                    continue
                if (spd is None) or (trk is None):
                    continue

                self.acs[icao]["gs"] = spd
                self.acs[icao]["trk"] = trk
                self.acs[icao]["roc"] = roc
                self.acs[icao]["tv"] = t

                output_buffer.append([t, icao, "gs", spd])
                output_buffer.append([t, icao, "trk", trk])
                output_buffer.append([t, icao, "roc", roc])

            if 5 <= tc <= 18:
                oe = pms.adsb.oe_flag(msg)
                self.acs[icao][oe] = msg
                self.acs[icao]["t" + str(oe)] = t

                if ("tpos" in self.acs[icao]) and (t - self.acs[icao]["tpos"] < 180):
                    # use single message decoding
                    rlat = self.acs[icao]["lat"]
                    rlon = self.acs[icao]["lon"]
                    latlon = pms.adsb.position_with_ref(msg, rlat, rlon)
                elif (
                    ("t0" in self.acs[icao])
                    and ("t1" in self.acs[icao])
                    and (abs(self.acs[icao]["t0"] - self.acs[icao]["t1"]) < 10)
                ):
                    # use multi message decoding
                    try:
                        latlon = pms.adsb.position(
                            self.acs[icao][0],
                            self.acs[icao][1],
                            self.acs[icao]["t0"],
                            self.acs[icao]["t1"],
                            self.lat0,
                            self.lon0,
                        )
                    except:
                        # mix of surface and airborne position message
                        continue
                else:
                    latlon = None

                if latlon is not None:
                    self.acs[icao]["tpos"] = t
                    self.acs[icao]["lat"] = latlon[0]
                    self.acs[icao]["lon"] = latlon[1]

                    alt = pms.adsb.altitude(msg)
                    self.acs[icao]["alt"] = alt

                    output_buffer.append([t, icao, "lat", latlon[0]])
                    output_buffer.append([t, icao, "lon", latlon[1]])
                    output_buffer.append([t, icao, "alt", alt])

                    local_updated_acs_buffer.append(icao)

            # Uncertainty & accuracy
            ac = self.acs[icao]

            if 9 <= tc <= 18:
                ac["nic_bc"] = pms.adsb.nic_b(msg)

            if (5 <= tc <= 8) or (9 <= tc <= 18) or (20 <= tc <= 22):
                ac["HPL"], ac["RCu"], ac["RCv"] = pms.adsb.nuc_p(msg)

                if (ac["ver"] == 1) and ("nic_s" in ac.keys()):
                    ac["Rc"], ac["VPL"] = pms.adsb.nic_v1(msg, ac["nic_s"])
                elif (
                    (ac["ver"] == 2)
                    and ("nic_a" in ac.keys())
                    and ("nic_bc" in ac.keys())
                ):
                    ac["Rc"] = pms.adsb.nic_v2(msg, ac["nic_a"], ac["nic_bc"])

            if tc == 19:
                ac["HVE"], ac["VVE"] = pms.adsb.nuc_v(msg)
                if ac["ver"] in [1, 2]:
                    ac["HFOMr"], ac["VFOMr"] = pms.adsb.nac_v(msg)

            if tc == 29:
                ac["PE_RCu"], ac["PE_VPL"], ac["base"] = pms.adsb.sil(msg, ac["ver"])
                ac["EPU"], ac["VEPU"] = pms.adsb.nac_p(msg)

            if tc == 31:
                ac["ver"] = pms.adsb.version(msg)
                ac["EPU"], ac["VEPU"] = pms.adsb.nac_p(msg)
                ac["PE_RCu"], ac["PE_VPL"], ac["sil_base"] = pms.adsb.sil(
                    msg, ac["ver"]
                )

                if ac["ver"] == 1:
                    ac["nic_s"] = pms.adsb.nic_s(msg)
                elif ac["ver"] == 2:
                    ac["nic_a"], ac["nic_bc"] = pms.adsb.nic_a_c(msg)

        # process commb message
        for t, msg in zip(commb_ts, commb_msg):
            icao = pms.icao(msg)

            if icao not in self.acs:
                continue

            self.acs[icao]["live"] = int(t)

            bds = pms.bds.infer(msg)

            if bds == "BDS50":
                roll50 = pms.commb.roll50(msg)
                trk50 = pms.commb.trk50(msg)
                rtrk50 = pms.commb.rtrk50(msg)
                gs50 = pms.commb.gs50(msg)
                tas50 = pms.commb.tas50(msg)

                self.acs[icao]["t50"] = t
                if tas50:
                    self.acs[icao]["tas"] = tas50
                    output_buffer.append([t, icao, "tas50", tas50])
                if roll50:
                    self.acs[icao]["roll"] = roll50
                    output_buffer.append([t, icao, "roll50", roll50])
                if rtrk50:
                    self.acs[icao]["rtrk"] = rtrk50
                    output_buffer.append([t, icao, "rtrk50", rtrk50])

                if trk50:
                    output_buffer.append([t, icao, "trk50", trk50])
                if gs50:
                    output_buffer.append([t, icao, "gs50", gs50])

            elif bds == "BDS60":
                ias60 = pms.commb.ias60(msg)
                hdg60 = pms.commb.hdg60(msg)
                mach60 = pms.commb.mach60(msg)
                roc60baro = pms.commb.vr60baro(msg)
                roc60ins = pms.commb.vr60ins(msg)

                if ias60 or hdg60 or mach60:
                    self.acs[icao]["t60"] = t
                if ias60:
                    self.acs[icao]["ias"] = ias60
                    output_buffer.append([t, icao, "ias60", ias60])
                if hdg60:
                    self.acs[icao]["hdg"] = hdg60
                    output_buffer.append([t, icao, "hdg60", hdg60])
                if mach60:
                    self.acs[icao]["mach"] = mach60
                    output_buffer.append([t, icao, "mach60", mach60])

                if roc60baro:
                    output_buffer.append([t, icao, "roc60baro", roc60baro])
                if roc60ins:
                    output_buffer.append([t, icao, "roc60ins", roc60ins])

        # clear up old data
        for icao in list(self.acs.keys()):
            if self.t - self.acs[icao]["live"] > self.cache_timeout:
                del self.acs[icao]
                continue

        if self.dumpto is not None:
            dh = str(datetime.datetime.now().strftime("%Y%m%d_%H"))
            fn = self.dumpto + "/pymodes_dump_%s.csv" % dh
            output_buffer.sort(key=lambda x: x[0])
            with open(fn, "a") as f:
                writer = csv.writer(f)
                writer.writerows(output_buffer)

        return

    def get_aircraft(self):
        """all aircraft that are stored in memory"""
        acs = self.acs
        return acs

    def run(self, raw_pipe_out, ac_pipe_in, exception_queue):
        local_buffer = []
        while True:
            try:
                while raw_pipe_out.poll():
                    data = raw_pipe_out.recv()
                    local_buffer.append(data)

                for data in local_buffer:
                    self.process_raw(
                        data["adsb_ts"],
                        data["adsb_msg"],
                        data["commb_ts"],
                        data["commb_msg"],
                    )
                local_buffer = []

                acs = self.get_aircraft()
                ac_pipe_in.send(acs)
                time.sleep(0.001)

            except Exception as e:
                tb = traceback.format_exc()
                exception_queue.put((e, tb))
