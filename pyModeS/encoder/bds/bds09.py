# ------------------------------------------
#   BDS 0,9
#   ADS-B TC=19
#   Aircraft Airborn velocity
# ------------------------------------------

import numpy as np


def me09(speed, angle, vertical_rate, **kwargs):
    spd = speed
    agl = angle
    vr = vertical_rate

    tc = kwargs.get("typecode")
    intent = kwargs.get("intent_change", 0)
    ifr = kwargs.get("ifr_capability", 1)
    navq = kwargs.get("navigation_quality", 0)
    supersonic = kwargs.get("supersonic", False)
    spd_type = kwargs.get("speed_type", "gs").lower()
    vr_source = kwargs.get("vertical_rate_source", "baro").lower()
    alt_diff = kwargs.get("gnss_baro_alt_diff", 0)

    if tc != 19:
        raise Exception("Typecode must be 19.")

    if intent not in (0, 1):
        raise Exception("Intent change flag must be 0 or 1.")

    if ifr not in (0, 1):
        raise Exception("IFR capability flag must be 0 or 1.")

    if type(supersonic) != bool:
        raise Exception("Subsonic flag must be True or False.")

    if navq > 7:
        raise Exception("Navigation quality indicator must be smaller than 8.")

    if spd_type not in ["gs", "tas"]:
        raise Exception("Speed type must be 'gs', 'ias', or 'tas'.")

    if vr_source not in ["baro", "gnss"]:
        raise Exception("Vertical rate source must be 'baro' or 'gnss'.")

    me_bin = ""

    # typecode
    me_bin += "{0:05b}".format(tc)

    # sub-type
    if supersonic:
        if spd_type == "gs":
            me_bin += "010"
        else:
            me_bin += "100"
    else:
        if spd_type == "gs":
            me_bin += "001"
        else:
            me_bin += "011"

    # intent, ifr, navigation quality
    me_bin += str(intent) + str(ifr) + "{0:03b}".format(navq)

    # speed and angle part
    if spd_type == "gs":
        vx = spd * np.sin(np.radians(agl))
        vy = spd * np.cos(np.radians(agl))

        if supersonic:
            vx /= 4
            vy /= 4

        vx = int(round(vx))
        vy = int(round(vy))

        sew = "0" if vx >= 0 else "1"
        sns = "0" if vy >= 0 else "1"
        vew = "{0:010b}".format(min(abs(vx), 1023) + 1)
        vns = "{0:010b}".format(min(abs(vy), 1023) + 1)

        me_bin += sew + vew + sns + vns

    elif spd_type == "ias" or spd_type == "tas":
        hdg = int(round(agl * 1024 / 360))
        hdg = min(hdg, 1023)

        air_type = "1" if spd_type == "tas" else "0"

        if supersonic:
            spd /= 4

        spd = min(int(round(spd)), 1023)

        me_bin += "1" + "{0:010b}".format(hdg) + air_type + "{0:010b}".format(spd)

    # vertical rate source
    me_bin += "1" if vr_source == "baro" else "0"

    # vertical rate
    me_bin += "0" if vr > 0 else "1"
    vr = int(round((abs(vr) / 64 + 1)))
    vr = min(vr, 511)
    me_bin += "{0:09b}".format(vr)

    # reserved
    me_bin += "00"

    # altitude difference
    me_bin += "1" if alt_diff < 0 else "0"
    alt_diff = int(round(abs(alt_diff) / 25 + 1))
    alt_diff = min(alt_diff, 127)
    me_bin += "{0:07b}".format(alt_diff)
    print(me_bin)

    # convert to hexdigits
    me_hex = "{0:04X}".format(int(me_bin, 2))

    return me_hex
