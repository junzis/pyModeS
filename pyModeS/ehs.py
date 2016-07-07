"""
A python package for decoding ModeS (DF20, DF21) messages.

Copyright (C) 2016 Junzi Sun (TU Delft)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from . import util
from .util import crc


def df(msg):
    """Get the downlink format (DF) number
    Args:
        msg (String): 28 bytes hexadecimal message string
    Returns:
        int: DF number
    """
    return util.df(msg)


def data(msg):
    """Return the data frame in the message, bytes 9 to 22"""
    return msg[8:22]


def icao(msg):
    """Calculate the ICAO address from an Mode-S message
        with DF4, DF5, DF20, DF21
    Args:
        msg (String): 28 bytes hexadecimal message string
    Returns:
        String: ICAO address in 6 bytes hexadecimal string
    """

    if df(msg) not in (4, 5, 20, 21):
        # raise RuntimeError("Message DF must be in (4, 5, 20, 21)")
        return None

    c0 = util.bin2int(crc(msg, encode=True))
    c1 = util.hex2int(msg[-6:])
    icao = '%06X' % (c0 ^ c1)
    return icao


def checkbits(data, sb, msb, lsb):
    """Check if the status bit and field bits are consistency. This Function
        is used for checking BDS code versions.
    """
    # status bit, most significant bit, least significant bit
    status = int(data[sb-1])
    value = util.bin2int(data[msb-1:lsb])

    if not status:
        if value != 0:
            return False

    return True


# ------------------------------------------
# DF 20/21, BDS 2,0
# ------------------------------------------

def isBDS20(msg):
    """Check if a message is likely to be BDS code 2,0
    Args:
        msg (String): 28 bytes hexadecimal message string
    Returns:
        bool: True or False
    """
    # status bit 1, 14, and 27
    d = util.hex2bin(data(msg))

    result = True

    if util.bin2int(d[0:4]) != 2 or util.bin2int(d[4:8]) != 0:
        result &= False

    cs = callsign(msg)

    if '#' in cs:
        result &= False

    return result


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
# DF 20/21, BDS 4,0
# ------------------------------------------

def isBDS40(msg):
    """Check if a message is likely to be BDS code 4,0
    Args:
        msg (String): 28 bytes hexadecimal message string
    Returns:
        bool: True or False
    """
    # status bit 1, 14, and 27
    d = util.hex2bin(data(msg))

    result = True

    result = result & checkbits(d, 1, 2, 13) \
        & checkbits(d, 14, 15, 26) & checkbits(d, 27, 28, 39)

    # bits 40-47 and 52-53 shall all be zero
    if util.bin2int(d[39:47]) != 0:
        result &= False

    if util.bin2int(d[51:53]) != 0:
        result &= False

    return result


def alt_mcp(msg):
    """Selected altitude, MCP/FCU
    Args:
        msg (String): 28 bytes hexadecimal message (BDS40) string
    Returns:
        int: altitude in feet
    """
    d = util.hex2bin(data(msg))
    alt = util.bin2int(d[1:13]) * 16    # ft
    return alt


def alt_fms(msg):
    """Selected altitude, FMS
    Args:
        msg (String): 28 bytes hexadecimal message (BDS40) string
    Returns:
        int: altitude in feet
    """
    d = util.hex2bin(data(msg))
    alt = util.bin2int(d[14:26]) * 16    # ft
    return alt


def pbaro(msg):
    """Barometric pressure setting
    Args:
        msg (String): 28 bytes hexadecimal message (BDS40) string
    Returns:
        float: pressure in millibar
    """
    d = util.hex2bin(data(msg))
    p = util.bin2int(d[27:39]) * 0.1 + 800    # millibar
    return p


# ------------------------------------------
# DF 20/21, BDS 5,0
# ------------------------------------------

def isBDS50(msg):
    """Check if a message is likely to be BDS code 5,0
    Args:
        msg (String): 28 bytes hexadecimal message string
    Returns:
        bool: True or False
    """
    # status bit 1, 12, 24, 35, 46
    d = util.hex2bin(data(msg))

    result = True

    result = result & checkbits(d, 1, 3, 11) & checkbits(d, 12, 13, 23) \
        & checkbits(d, 24, 25, 34) & checkbits(d, 35, 36, 45) \
        & checkbits(d, 46, 47, 56)

    if d[2:11] == "000000000":
        result &= True
    else:
        if abs(roll(msg)) > 30:
            result &= False

    if gs(msg) > 500:
        result &= False

    if tas(msg) > 500:
        result &= False

    if abs(tas(msg) - gs(msg)) > 100:
        result &= False

    return result


def roll(msg):
    """Aircraft roll angle
    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string
    Returns:
        float: angle in degrees,
               negative->left wing down, positive->right wing down
    """
    d = util.hex2bin(data(msg))
    sign = int(d[1])    # 1 -> left wing down
    value = util.bin2int(d[2:11]) * 45 / 256.0    # degree
    angle = -1 * value if sign else value
    return round(angle, 1)


def track(msg):
    """True track angle
    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string
    Returns:
        float: angle in degrees to true north (from 0 to 360)
    """
    d = util.hex2bin(data(msg))
    sign = int(d[12])   # 1 -> west
    value = util.bin2int(d[13:23]) * 90 / 512.0    # degree
    angle = 360 - value if sign else value
    return round(angle, 1)


def gs(msg):
    """Aircraft ground speed
    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string
    Returns:
        int: ground speed in knots
    """
    d = util.hex2bin(data(msg))
    spd = util.bin2int(d[24:34]) * 2    # kts
    return spd


def rtrack(msg):
    """Track angle rate
    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string
    Returns:
        float: angle rate in degrees/second
    """
    d = util.hex2bin(data(msg))
    sign = int(d[35])    # 1 -> minus
    value = util.bin2int(d[36:45]) * 8 / 256.0    # degree / sec
    angle = -1 * value if sign else value
    return round(angle, 3)


def tas(msg):
    """Aircraft true airspeed
    Args:
        msg (String): 28 bytes hexadecimal message (BDS50) string
    Returns:
        int: true airspeed in knots
    """
    d = util.hex2bin(data(msg))
    spd = util.bin2int(d[46:56]) * 2   # kts
    return spd


# ------------------------------------------
# DF 20/21, BDS 6,0
# ------------------------------------------

def isBDS60(msg):
    """Check if a message is likely to be BDS code 6,0
    Args:
        msg (String): 28 bytes hexadecimal message string
    Returns:
        bool: True or False
    """
    # status bit 1, 13, 24, 35, 46
    d = util.hex2bin(data(msg))

    result = True

    result = result & checkbits(d, 1, 2, 12) & checkbits(d, 13, 14, 23) \
        & checkbits(d, 24, 25, 34) & checkbits(d, 35, 36, 45) \
        & checkbits(d, 46, 47, 56)

    if not (1 < ias(msg) < 500):
        result &= False

    if not (0.0 < mach(msg) < 1.0):
        result &= False

    if abs(baro_vr(msg)) > 5000:
        result &= False

    if abs(ins_vr(msg)) > 5000:
        result &= False

    return result


def heading(msg):
    """Megnetic heading of aircraft
    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string
    Returns:
        float: heading in degrees to megnetic north (from 0 to 360)
    """
    d = util.hex2bin(data(msg))
    sign = int(d[1])    # 1 -> west
    value = util.bin2int(d[2:12]) * 90 / 512.0  # degree
    hdg = 360 - value if sign else value
    return round(hdg, 1)


def ias(msg):
    """Indicated airspeed
    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string
    Returns:
        int: indicated airspeed in knots
    """
    d = util.hex2bin(data(msg))
    ias = util.bin2int(d[13:23])    # kts
    return ias


def mach(msg):
    """Aircraft MACH number
    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string
    Returns:
        float: MACH number
    """
    d = util.hex2bin(data(msg))
    mach = util.bin2int(d[24:34]) * 2.048 / 512.0
    return round(mach, 3)


def baro_vr(msg):
    """Vertical rate from barometric measurement
    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string
    Returns:
        int: vertical rate in feet/minutes
    """
    d = util.hex2bin(data(msg))
    sign = d[35]    # 1 -> minus
    value = util.bin2int(d[36:45]) * 32   # feet/min
    roc = -1*value if sign else value
    return roc


def ins_vr(msg):
    """Vertical rate messured by onbard equiments (IRS, AHRS)
    Args:
        msg (String): 28 bytes hexadecimal message (BDS60) string
    Returns:
        int: vertical rate in feet/minutes
    """
    d = util.hex2bin(data(msg))
    sign = d[46]    # 1 -> minus
    value = util.bin2int(d[47:56]) * 32   # feet/min
    roc = -1*value if sign else value
    return roc


def BDS(msg):
    """Estimate the most likely BDS code of an message
    Args:
        msg (String): 28 bytes hexadecimal message string
    Returns:
        String|None: Version: "BDS40", "BDS50", or "BDS60". Or None, if nothing
            matched
    """
    is2 = isBDS20(msg)
    is4 = isBDS40(msg)
    is5 = isBDS50(msg)
    is6 = isBDS60(msg)
    if is2 and not is4 and not is5 and not is6:
        return "BDS20"
    elif not is2 and is4 and not is5 and not is6:
        return "BDS40"
    elif not is2 and not is4 and is5 and not is6:
        return "BDS50"
    elif not is2 and not is4 and not is5 and is6:
        return "BDS60"
    else:
        return None
