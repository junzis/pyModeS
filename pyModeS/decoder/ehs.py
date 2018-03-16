# Copyright (C) 2016 Junzi Sun (TU Delft)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
A python package for decoding ModeS (DF20, DF21) messages.
"""

from __future__ import absolute_import, print_function, division
import numpy as np
from pyModeS.decoder import util, modes
from pyModeS.extra import aero

def icao(msg):
    return modes.icao(msg)

def data(msg):
    """Return the data frame in the message, bytes 9 to 22"""
    return msg[8:22]

def allzeros(msg):
    """check if the data bits are all zeros

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """
    d = util.hex2bin(data(msg))

    if util.bin2int(d) > 0:
        return False
    else:
        return True

def wrongstatus(data, sb, msb, lsb):
    """Check if the status bit and field bits are consistency. This Function
    is used for checking BDS code versions.
    """

    # status bit, most significant bit, least significant bit
    status = int(data[sb-1])
    value = util.bin2int(data[msb-1:lsb])

    if not status:
        if value != 0:
            return True

    return False


# ------------------------------------------
# BDS 1,0
# Data link capability report
# ------------------------------------------

def isBDS10(msg):
    """Check if a message is likely to be BDS code 1,0

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = util.hex2bin(data(msg))

    # first 8 bits must be 0x10
    if d[0:8] != '00010000':
        return False

    # bit 10 to 14 are reserved
    if util.bin2int(d[9:14]) != 0:
        return False

    # overlay capabilty conflict
    if d[14] == '1' and util.bin2int(d[16:23]) < 5:
        return False
    if d[14] == '0' and util.bin2int(d[16:23]) > 4:
        return False

    return True

def ovc10(msg):
    """Return the overlay control capability

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: Whether the transponder is OVC capable
    """
    d = util.hex2bin(data(msg))

    return int(d[14])

# ------------------------------------------
# BDS 1,7
# Common usage GICB capability report
# ------------------------------------------

def isBDS17(msg):
    """Check if a message is likely to be BDS code 1,7

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = util.hex2bin(data(msg))

    if util.bin2int(d[28:56]) != 0:
        return False

    caps = cap17(msg)

    # basic BDS codes for ADS-B shall be supported
    #   assuming ADS-B out is installed (2017EU/2020US mandate)
    if not set(['BDS05', 'BDS06', 'BDS09', 'BDS20']).issubset(caps):
        return False

    return True

def cap17(msg):
    """Extract capacities from BDS 1,7 message

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        list: list of suport BDS codes
    """
    allbds = ['05', '06', '07', '08', '09', '0A', '20', '21', '40', '41',
              '42', '43', '44', '45', '48', '50', '51', '52', '53', '54',
              '55', '56', '5F', '60', 'NA', 'NA', 'E1', 'E2']

    d = util.hex2bin(data(msg))
    idx = [i for i, v in enumerate(d[:28]) if v=='1']
    capacity = ['BDS'+allbds[i] for i in idx if allbds[i] is not 'NA']

    return capacity


# ------------------------------------------
# BDS 2,0
# Aircraft identification
# ------------------------------------------

def isBDS20(msg):
    """Check if a message is likely to be BDS code 2,0

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = util.hex2bin(data(msg))

    # status bit 1, 14, and 27

    if util.bin2int(d[0:4]) != 2 or util.bin2int(d[4:8]) != 0:
        return False

    cs = callsign(msg)

    if '#' in cs:
        return False

    return True


def callsign(msg):
    """Aircraft callsign

    Args:
        msg (String): 28 bytes hexadecimal message (BDS40) string

    Returns:
        string: callsign, max. 8 chars
    """
    chars = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ#####_###############0123456789######'

    d = util.hex2bin(data(msg))

    cs = ''
    cs += chars[util.bin2int(d[8:14])]
    cs += chars[util.bin2int(d[14:20])]
    cs += chars[util.bin2int(d[20:26])]
    cs += chars[util.bin2int(d[26:32])]
    cs += chars[util.bin2int(d[32:38])]
    cs += chars[util.bin2int(d[38:44])]
    cs += chars[util.bin2int(d[44:50])]
    cs += chars[util.bin2int(d[50:56])]

    return cs


# ------------------------------------------
# BDS 4,0
# Selected vertical intention
# ------------------------------------------

def isBDS40(msg):
    """Check if a message is likely to be BDS code 4,0

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = util.hex2bin(data(msg))

    # status bit 1, 14, and 27

    if wrongstatus(d, 1, 2, 13):
        return False

    if wrongstatus(d, 14, 15, 26):
        return False

    if wrongstatus(d, 27, 28, 39):
        return False

    # bits 40-47 and 52-53 shall all be zero

    if util.bin2int(d[39:47]) != 0:
        return False

    if util.bin2int(d[51:53]) != 0:
        return False

    return True


def alt40mcp(msg):
    """Selected altitude, MCP/FCU

    Args:
        msg (String): 28 bytes hexadecimal message (BDS40) string

    Returns:
        int: altitude in feet
    """
    d = util.hex2bin(data(msg))

    if d[0] == '0':
        return None

    alt = util.bin2int(d[1:13]) * 16    # ft
    return alt


def alt40fms(msg):
    """Selected altitude, FMS

    Args:
        msg (String): 28 bytes hexadecimal message (BDS40) string

    Returns:
        int: altitude in feet
    """
    d = util.hex2bin(data(msg))

    if d[13] == '0':
        return None

    alt = util.bin2int(d[14:26]) * 16    # ft
    return alt


def p40baro(msg):
    """Barometric pressure setting

    Args:
        msg (String): 28 bytes hexadecimal message (BDS40) string

    Returns:
        float: pressure in millibar
    """
    d = util.hex2bin(data(msg))

    if d[26] == '0':
        return None

    p = util.bin2int(d[27:39]) * 0.1 + 800    # millibar
    return p


# ------------------------------------------
# BDS 4,4
# Meteorological routine air report
# ------------------------------------------

def isBDS44(msg, rev=False):
    """Check if a message is likely to be BDS code 4,4
    Meteorological routine air report

    Args:
        msg (String): 28 bytes hexadecimal message string
        rev (bool): using revised version

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = util.hex2bin(data(msg))


    if not rev:
        # status bit 5, 35, 47, 50
        if wrongstatus(d, 5, 6, 23):
            return False

        if wrongstatus(d, 35, 36, 46):
            return False

        if wrongstatus(d, 47, 48, 49):
            return False

        if wrongstatus(d, 50, 51, 56):
            return False

        # Bits 1-4 indicate source, values > 4 reserved and should not occur
        if util.bin2int(d[0:4]) > 4:
            return False
    else:
        # status bit 5, 15, 24, 36, 49
        if wrongstatus(d, 5, 6, 14):
            return False

        if wrongstatus(d, 15, 16, 23):
            return False

        if wrongstatus(d, 24, 25, 35):
            return False

        if wrongstatus(d, 36, 37, 47):
            return False

        if wrongstatus(d, 49, 50, 56):
            return False

        # Bits 1-4 are reserved and should be zero
        if util.bin2int(d[0:4]) != 0:
            return False

    vw = wind44(msg, rev=rev)
    if vw is not None and vw[0] > 250:
        return False

    if temp44(msg):
        if temp44(msg) > 60 or temp44(msg) < -80:
            return False

    elif temp44(msg) == 0:
        return False

    return True


def wind44(msg, rev=False):
    """reported wind speed and direction

    Args:
        msg (String): 28 bytes hexadecimal message (BDS44) string
        rev (bool): using revised version

    Returns:
        (int, float): speed (kt), direction (degree)
    """
    d = util.hex2bin(data(msg))

    if not rev:
        status = int(d[4])
        if not status:
            return None

        speed = util.bin2int(d[5:14])   # knots
        direction = util.bin2int(d[14:23]) * 180.0 / 256.0  # degree

    else:
        spd_status = int(d[4])
        dir_status = int(d[14])

        if (not spd_status) or (not dir_status):
            return None

        speed = util.bin2int(d[5:14])   # knots
        direction = util.bin2int(d[15:23]) * 180.0 / 128.0  # degree

    return round(speed, 0), round(direction, 1)


def temp44(msg, rev=False):
    """reported air temperature

    Args:
        msg (String): 28 bytes hexadecimal message (BDS44) string
        rev (bool): using revised version

    Returns:
        float: tmeperature in Celsius degree
    """
    d = util.hex2bin(data(msg))

    if not rev:
        # if d[22] == '0':
        #     return None

        sign = int(d[23])
        value = util.bin2int(d[24:34])

        if sign:
            value = value - 1024

        temp = value * 0.125   # celsius
        temp = round(temp, 1)
    else:
        # if d[23] == '0':
        #     return None

        sign = int(d[24])
        value = util.bin2int(d[25:35])

        if sign:
            value = value - 1024

        temp = value * 0.125   # celsius
        temp = round(temp, 1)

    return -1*temp if sign else temp


def p44(msg, rev=False):
    """reported average static pressure

    Args:
        msg (String): 28 bytes hexadecimal message (BDS44) string
        rev (bool): using revised version

    Returns:
        int: static pressure in hPa
    """
    d = util.hex2bin(data(msg))

    if not rev:
        if d[34] == '0':
            return None

        p = util.bin2int(d[35:46])    # hPa

    else:
        if d[35] == '0':
            return None

        p = util.bin2int(d[36:47])    # hPa

    return p


def hum44(msg, rev=False):
    """reported humidity

    Args:
        msg (String): 28 bytes hexadecimal message (BDS44) string
        rev (bool): using revised version

    Returns:
        float: percentage of humidity, [0 - 100] %
    """
    d = util.hex2bin(data(msg))

    if not rev:
        if d[49] == '0':
            return None

        hm = util.bin2int(d[50:56]) * 100.0 / 64    # %

    else:
        if d[48] == '0':
            return None

        hm = util.bin2int(d[49:56])    # %

    return round(hm, 1)


# ------------------------------------------
# BDS 5,0
# Track and turn report
# ------------------------------------------

def isBDS50(msg):
    """Check if a message is likely to be BDS code 5,0
    (Track and turn report)

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = util.hex2bin(data(msg))

    # status bit 1, 12, 24, 35, 46

    if wrongstatus(d, 1, 3, 11):
        return False

    if wrongstatus(d, 12, 13, 23):
        return False

    if wrongstatus(d, 24, 25, 34):
        return False

    if wrongstatus(d, 35, 36, 45):
        return False

    if wrongstatus(d, 46, 47, 56):
        return False

    if d[2:11] != "000000000":
        roll = abs(roll50(msg))
        if roll and roll > 60:
            return False

    gs = gs50(msg)
    if gs is not None and gs > 600:
        return False

    tas = tas50(msg)
    if tas is not None and tas > 500:
        return False

    if (gs is not None) and (tas is not None) and (abs(tas - gs) > 200):
        return False

    return True


def roll50(msg):
    """Roll angle, BDS 5,0 message

    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string

    Returns:
        float: angle in degrees,
               negative->left wing down, positive->right wing down
    """
    d = util.hex2bin(data(msg))

    if d[0] == '0':
        return None

    sign = int(d[1])    # 1 -> left wing down
    value = util.bin2int(d[2:11])

    if sign:
        value = value - 512

    angle = value * 45.0 / 256.0    # degree
    return round(angle, 1)


def trk50(msg):
    """True track angle, BDS 5,0 message

    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string

    Returns:
        float: angle in degrees to true north (from 0 to 360)
    """
    d = util.hex2bin(data(msg))

    if d[11] == '0':
        return None

    sign = int(d[12])   # 1 -> west
    value = util.bin2int(d[13:23])

    if sign:
        value = value - 1024

    trk = value * 90.0 / 512.0

    # convert from [-180, 180] to [0, 360]
    if trk < 0:
        trk = 360 + trk

    return round(trk, 3)


def gs50(msg):
    """Ground speed, BDS 5,0 message

    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string

    Returns:
        int: ground speed in knots
    """
    d = util.hex2bin(data(msg))

    if d[23] == '0':
        return None

    spd = util.bin2int(d[24:34]) * 2    # kts
    return spd


def rtrk50(msg):
    """Track angle rate, BDS 5,0 message

    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string

    Returns:
        float: angle rate in degrees/second
    """
    d = util.hex2bin(data(msg))

    if d[34] == '0':
        return None

    if d[36:45] == "111111111":
        return None

    sign = int(d[35])    # 1 -> negative value, two's complement
    value = util.bin2int(d[36:45])
    if sign:
        value = value - 512

    angle = value * 8.0 / 256.0    # degree / sec
    return round(angle, 3)


def tas50(msg):
    """Aircraft true airspeed, BDS 5,0 message

    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string

    Returns:
        int: true airspeed in knots
    """
    d = util.hex2bin(data(msg))

    if d[45] == '0':
        return None

    tas = util.bin2int(d[46:56]) * 2   # kts
    return tas


# ------------------------------------------
# BDS 5,3
# Air-referenced state vector
# ------------------------------------------

def isBDS53(msg):
    """Check if a message is likely to be BDS code 5,3
    (Air-referenced state vector)

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = util.hex2bin(data(msg))

    # status bit 1, 13, 24, 34, 47

    if wrongstatus(d, 1, 3, 12):
        return False

    if wrongstatus(d, 13, 14, 23):
        return False

    if wrongstatus(d, 24, 25, 33):
        return False

    if wrongstatus(d, 34, 35, 46):
        return False

    if wrongstatus(d, 47, 49, 56):
        return False

    ias = ias53(msg)
    if ias is not None and ias > 500:
        return False

    mach = mach53(msg)
    if mach is not None and mach > 1:
        return False

    tas = tas53(msg)
    if tas is not None and tas > 500:
        return False

    vr = vr53(msg)
    if vr is not None and abs(vr) > 8000:
        return False

    return True


def hdg53(msg):
    """Magnetic heading, BDS 5,3 message

    Args:
        msg (String): 28 bytes hexadecimal message (BDS53) string

    Returns:
        float: angle in degrees to true north (from 0 to 360)
    """
    d = util.hex2bin(data(msg))

    if d[0] == '0':
        return None

    sign = int(d[1])    # 1 -> west
    value = util.bin2int(d[2:12])

    if sign:
        value = value - 1024

    hdg = value * 90.0 / 512.0   # degree

    # convert from [-180, 180] to [0, 360]
    if hdg < 0:
        hdg = 360 + hdg

    return round(hdg, 3)


def ias53(msg):
    """Indicated airspeed, DBS 5,3 message

    Args:
        msg (String): 28 bytes hexadecimal message

    Returns:
        int: indicated arispeed in knots
    """
    d = util.hex2bin(data(msg))

    if d[12] == '0':
        return None

    ias = util.bin2int(d[13:23])    # knots
    return ias


def mach53(msg):
    """MACH number, DBS 5,3 message

    Args:
        msg (String): 28 bytes hexadecimal message

    Returns:
        float: MACH number
    """
    d = util.hex2bin(data(msg))

    if d[23] == '0':
        return None

    mach = util.bin2int(d[24:33]) * 0.008
    return round(mach, 3)


def tas53(msg):
    """Aircraft true airspeed, BDS 5,3 message

    Args:
        msg (String): 28 bytes hexadecimal message

    Returns:
        float: true airspeed in knots
    """
    d = util.hex2bin(data(msg))

    if d[33] == '0':
        return None

    tas = util.bin2int(d[34:46]) * 0.5   # kts
    return round(tas, 1)

def vr53(msg):
    """Vertical rate

    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string

    Returns:
        int: vertical rate in feet/minutes
    """
    d = util.hex2bin(data(msg))

    if d[46] == '0':
        return None

    sign = int(d[47])    # 1 -> negative value, two's complement
    value = util.bin2int(d[48:56])

    if value == 0 or value == 255:  # all zeros or all ones
        return 0

    value = value - 256 if sign else value
    roc = value * 64     # feet/min

    return roc


# ------------------------------------------
# BDS 6,0
# ------------------------------------------

def isBDS60(msg):
    """Check if a message is likely to be BDS code 6,0

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False
    """

    if allzeros(msg):
        return False

    d = util.hex2bin(data(msg))

    # status bit 1, 13, 24, 35, 46

    if wrongstatus(d, 1, 2, 12):
        return False

    if wrongstatus(d, 13, 14, 23):
        return False

    if wrongstatus(d, 24, 25, 34):
        return False

    if wrongstatus(d, 35, 36, 45):
        return False

    if wrongstatus(d, 46, 47, 56):
        return False

    ias = ias60(msg)
    if ias is not None and ias > 500:
        return False

    mach = mach60(msg)
    if mach is not None and mach > 1:
        return False

    vr_baro = vr60baro(msg)
    if vr_baro is not None and abs(vr_baro) > 6000:
        return False

    vr_ins = vr60ins(msg)
    if vr_ins is not None and abs(vr_ins) > 6000:
        return False

    return True


def hdg60(msg):
    """Megnetic heading of aircraft

    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string

    Returns:
        float: heading in degrees to megnetic north (from 0 to 360)
    """
    d = util.hex2bin(data(msg))

    if d[0] == '0':
        return None

    sign = int(d[1])    # 1 -> west
    value = util.bin2int(d[2:12])

    if sign:
        value = value - 1024

    hdg = value * 90 / 512.0  # degree

    # convert from [-180, 180] to [0, 360]
    if hdg < 0:
        hdg = 360 + hdg

    return round(hdg, 3)


def ias60(msg):
    """Indicated airspeed

    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string

    Returns:
        int: indicated airspeed in knots
    """
    d = util.hex2bin(data(msg))

    if d[12] == '0':
        return None

    ias = util.bin2int(d[13:23])    # kts
    return ias


def mach60(msg):
    """Aircraft MACH number

    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string

    Returns:
        float: MACH number
    """
    d = util.hex2bin(data(msg))

    if d[23] == '0':
        return None

    mach = util.bin2int(d[24:34]) * 2.048 / 512.0
    return round(mach, 3)


def vr60baro(msg):
    """Vertical rate from barometric measurement, this value may be very noisy.

    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string

    Returns:
        int: vertical rate in feet/minutes
    """
    d = util.hex2bin(data(msg))

    if d[34] == '0':
        return None

    sign = int(d[35])    # 1 -> negative value, two's complement
    value = util.bin2int(d[36:45])

    if value == 0 or value == 511:  # all zeros or all ones
        return 0

    value = value - 512 if sign else value

    roc = value * 32   # feet/min
    return roc


def vr60ins(msg):
    """Vertical rate messured by onbard equiments (IRS, AHRS)

    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string

    Returns:
        int: vertical rate in feet/minutes
    """
    d = util.hex2bin(data(msg))

    if d[45] == '0':
        return None

    sign = int(d[46])    # 1 -> negative value, two's complement
    value = util.bin2int(d[47:56])

    if value == 0 or value == 511:  # all zeros or all ones
        return 0

    value = value - 512 if sign else value

    roc = value * 32   # feet/min
    return roc


def isBDS50or60(msg, spd_ref, trk_ref, alt_ref):
    """Use reference ground speed and trk to determine BDS50 and DBS60

    Args:
        msg (String): 28 bytes hexadecimal message string
        spd_ref (float): reference speed (ADS-B ground speed), kts
        trk_ref (float): reference track (ADS-B track angle), deg
        alt_ref (float): reference altitude (ADS-B altitude), ft

    Returns:
        String or None: BDS version, or possible versions, or None if nothing matches.
    """
    def vxy(v, angle):
        vx = v * np.sin(np.deg2rad(angle))
        vy = v * np.cos(np.deg2rad(angle))
        return vx, vy

    if not (isBDS50(msg) and isBDS60(msg)):
        return None

    h50 = trk50(msg)
    v50 = gs50(msg)
    h50 = np.nan if h50 is None else h50
    v50 = np.nan if v50 is None else v50


    h60 = hdg60(msg)
    m60 = mach60(msg)
    i60 = ias60(msg)
    h60 = np.nan if h60 is None else h60
    m60 = np.nan if m60 is None else m60
    i60 = np.nan if i60 is None else i60

    XY5 = vxy(v50*aero.kts, h50)
    XY6m = vxy(aero.mach2tas(m60, alt_ref*aero.ft), h60)
    XY6i = vxy(aero.cas2tas(i60*aero.kts, alt_ref*aero.ft), h60)

    allbds = ['BDS50', 'BDS60', 'BDS60']

    X = np.array([XY5, XY6m, XY6i])
    Mu = np.array(vxy(spd_ref*aero.kts, trk_ref*aero.kts))

    # compute Mahalanobis distance matrix
    # Cov = [[20**2, 0], [0, 20**2]]
    # mmatrix = np.sqrt(np.dot(np.dot(X-Mu, np.linalg.inv(Cov)), (X-Mu).T))
    # dist = np.diag(mmatrix)

    # since the covariance matrix is identity matrix,
    #     M-dist is same as eculidian distance
    dist = np.linalg.norm(X-Mu, axis=1)
    BDS = allbds[np.nanargmin(dist)]

    return BDS


def BDS(msg):
    """Estimate the most likely BDS code of an message

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        String or None: BDS version, or possible versions, or None if nothing matches.
    """

    if allzeros(msg):
        return None

    is10 = isBDS10(msg)
    is17 = isBDS17(msg)
    is20 = isBDS20(msg)
    is40 = isBDS40(msg)
    is44 = isBDS44(msg)
    is44rev = isBDS44(msg, rev=True)
    is50 = isBDS50(msg)
    is53 = isBDS53(msg)
    is60 = isBDS60(msg)

    allbds = np.array([
        "BDS10", "BDS17", "BDS20", "BDS40", "BDS44", "BDS44REV",
        "BDS50", "BDS53", "BDS60"
    ])

    isBDS = [is10, is17, is20, is40, is44, is44rev, is50, is53, is60]

    bds = ','.join(sorted(allbds[isBDS]))

    if len(bds) == 0:
        return None
    else:
        return bds
