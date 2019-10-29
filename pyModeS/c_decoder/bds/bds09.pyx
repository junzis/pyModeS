# cython: language_level=3

cimport cython

from ..common cimport char_to_int, typecode, hex2bin, bin2int
from libc.math cimport atan2, sqrt, pi, NAN as nan

def airborne_velocity(bytes msg, bint rtn_sources=False):
    """Calculate the speed, track (or heading), and vertical rate

    Args:
        msg (string): 28 bytes hexadecimal message string
        rtn_source (boolean): If the function will return
            the sources for direction of travel and vertical
            rate. This will change the return value from a four
            element array to a six element array.

    Returns:
        (int, float, int, string, string, string): speed (kt),
            ground track or heading (degree),
            rate of climb/descent (ft/min), speed type
            ('GS' for ground speed, 'AS' for airspeed),
            direction source ('true_north' for ground track / true north
            as refrence, 'mag_north' for magnetic north as reference),
            rate of climb/descent source ('Baro' for barometer, 'GNSS'
            for GNSS constellation).
    """

    if typecode(msg) != 19:
        raise RuntimeError("%s: Not a airborne velocity message, expecting TC=19" % msg)

    cdef bytearray mb = hex2bin(msg)[32:]

    cdef int subtype = bin2int(mb[5:8])

    if bin2int(mb[14:24]) == 0 or bin2int(mb[25:35]) == 0:
        return None

    cdef int v_ew_sign, v_ew, v_ns_sign, v_ns
    cdef double spd, trk, trk_or_hdg, hdg

    if subtype in (1, 2):
        v_ew_sign = -1 if mb[13] == 49 else 1  # "1"
        v_ew = bin2int(mb[14:24]) - 1  # east-west velocity
        if subtype == 2:  # Supersonic
            v_ew *= 4

        v_ns_sign = -1 if mb[24] == 49 else 1  # "1"
        v_ns = bin2int(mb[25:35]) - 1  # north-south velocity
        if subtype == 2:  # Supersonic
            v_ns *= 4

        v_we = v_ew_sign * v_ew
        v_sn = v_ns_sign * v_ns

        spd = sqrt(v_sn * v_sn + v_we * v_we)  # unit in kts
        # spd = int(spd)

        trk = atan2(v_we, v_sn)
        # trk = math.degrees(trk)  # convert to degrees
        trk = trk * 180 / pi
        trk = trk if trk >= 0 else trk + 360  # no negative val

        tag = "GS"
        trk_or_hdg = round(trk, 2)
        dir_type = "true_north"

    else:
        if mb[13] == 48:  # "0"
            hdg = nan
        else:
            hdg = bin2int(mb[14:24]) / 1024.0 * 360.0
            hdg = round(hdg, 2)

        trk_or_hdg = hdg

        spd = bin2int(mb[25:35])
        spd = nan if spd == 0 else spd - 1
        if subtype == 4:  # Supersonic
            spd *= 4

        if mb[24] == 48:  # "0"
            tag = "IAS"
        else:
            tag = "TAS"

        dir_type = "mag_north"

    vr_source = "GNSS" if mb[35] == 48 else "Baro"  # "0"
    vr_sign = -1 if mb[36] == 49 else 1  # "1"
    vr = bin2int(mb[37:46])
    rocd = None if vr == 0 else int(vr_sign * (vr - 1) * 64)

    if rtn_sources:
        return int(spd), trk_or_hdg, rocd, tag, dir_type, vr_source
    else:
        return int(spd), trk_or_hdg, rocd, tag


def altitude_diff(bytes msg):
    """Decode the differece between GNSS and barometric altitude

    Args:
        msg (string): 28 bytes hexadecimal message string, TC=19

    Returns:
        int: Altitude difference in ft. Negative value indicates GNSS altitude
            below barometric altitude.
    """
    cdef int tc = typecode(msg)

    if tc != 19:
        raise RuntimeError("%s: Not a airborne velocity message, expecting TC=19" % msg)

    cdef bytearray msgbin = hex2bin(msg)
    cdef int sign = -1 if char_to_int(msgbin[80]) else 1
    cdef int value = bin2int(msgbin[81:88])

    if value == 0 or value == 127:
        return None
    else:
        return sign * (value - 1) * 25  # in ft.
