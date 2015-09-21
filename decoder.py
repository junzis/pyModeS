"""
This is a decoder of ABS-D date from Mode-S receiver. The inputs
    of most functions are the Hexdecial strings.

Created by  : Junzi Sun (TU Delft)
Date        : March 2015
"""

import math

MODES_CHECKSUM_TABLE = [
    0x3935ea, 0x1c9af5, 0xf1b77e, 0x78dbbf,
    0xc397db, 0x9e31e9, 0xb0e2f0, 0x587178,
    0x2c38bc, 0x161c5e, 0x0b0e2f, 0xfa7d13,
    0x82c48d, 0xbe9842, 0x5f4c21, 0xd05c14,
    0x682e0a, 0x341705, 0xe5f186, 0x72f8c3,
    0xc68665, 0x9cb936, 0x4e5c9b, 0xd8d449,
    0x939020, 0x49c810, 0x24e408, 0x127204,
    0x093902, 0x049c81, 0xfdb444, 0x7eda22,
    0x3f6d11, 0xe04c8c, 0x702646, 0x381323,
    0xe3f395, 0x8e03ce, 0x4701e7, 0xdc7af7,
    0x91c77f, 0xb719bb, 0xa476d9, 0xadc168,
    0x56e0b4, 0x2b705a, 0x15b82d, 0xf52612,
    0x7a9309, 0xc2b380, 0x6159c0, 0x30ace0,
    0x185670, 0x0c2b38, 0x06159c, 0x030ace,
    0x018567, 0xff38b7, 0x80665f, 0xbfc92b,
    0xa01e91, 0xaff54c, 0x57faa6, 0x2bfd53,
    0xea04ad, 0x8af852, 0x457c29, 0xdd4410,
    0x6ea208, 0x375104, 0x1ba882, 0x0dd441,
    0xf91024, 0x7c8812, 0x3e4409, 0xe0d800,
    0x706c00, 0x383600, 0x1c1b00, 0x0e0d80,
    0x0706c0, 0x038360, 0x01c1b0, 0x00e0d8,
    0x00706c, 0x003836, 0x001c1b, 0xfff409,
    0x000000, 0x000000, 0x000000, 0x000000,
    0x000000, 0x000000, 0x000000, 0x000000,
    0x000000, 0x000000, 0x000000, 0x000000,
    0x000000, 0x000000, 0x000000, 0x000000,
    0x000000, 0x000000, 0x000000, 0x000000,
    0x000000, 0x000000, 0x000000, 0x000000
]


def hex2bin(hexstr):
    """Convert a hexdecimal string to binary string, with zero fillings. """
    length = len(hexstr) * 4
    msgbin = bin(int(hexstr, 16))[2:]
    while ((len(msgbin)) < length):
        msgbin = '0' + msgbin
    return msgbin


def bin2int(binstr):
    return int(binstr, 2)


def hex2int(hexstr):
    return int(hexstr, 16)


def checksum(msg):
    if len(msg) == 28:
        offset = 0
    elif len(msg) == 14:
        offset = 112-56
    else:
        # raise exception
        return False

    msgbin = hex2bin(msg)
    checksum = int(msg[22:28], 16)

    crc = 0
    for i in xrange(len(msgbin)):
        if int(msgbin[i]):
            crc ^= MODES_CHECKSUM_TABLE[i+offset]

    if crc == checksum:
        return True
    else:
        return False


def get_df(msg):
    """Decode Downlink Format vaule, bits 1 to 5."""
    msgbin = hex2bin(msg)
    return bin2int(msgbin[0: 5])


def get_ca(msg):
    """Decode CA vaule, bits: 6 to 8."""
    msgbin = hex2bin(msg)
    return bin2int(msgbin[5:8])


def get_icao_addr(msg):
    """Get the ICAO 24 bits address, bytes 3 to 8. """
    return msg[2:8]


def get_tc(msg):
    """Get Type Code, bits 33 to 37 """
    msgbin = hex2bin(msg)
    return bin2int(msgbin[32:37])


def get_oe_flag(msg):
    """Check the odd/even flag. Bit 54, 0 for even, 1 for odd."""
    msgbin = hex2bin(msg)
    return msgbin[53]


def get_alt(msg):
    """Calculate the altitude from the message. Bit 41 to 52, Q-bit at 48"""
    msgbin = hex2bin(msg)
    q = msgbin[47]
    if q:
        n = bin2int(msgbin[40:47]+msgbin[48:52])
        alt = n * 25 - 1000
        return alt
    else:
        return None


def get_cprlat(msg):
    msgbin = hex2bin(msg)
    return bin2int(msgbin[54:71])


def get_cprlon(msg):
    msgbin = hex2bin(msg)
    return bin2int(msgbin[71:88])


def get_position(msg0, msg1, t0, t1):
    cprlat0 = get_cprlat(msg0)
    cprlat1 = get_cprlat(msg1)
    cprlon0 = get_cprlon(msg0)
    cprlon1 = get_cprlon(msg1)
    return cpr2position(cprlat0, cprlat1, cprlon0, cprlon1, t0, t1)


def cpr2position(cprlat0, cprlat1, cprlon0, cprlon1, t0, t1):
    '''
     This algorithm comes from:
     http://www.lll.lu/~edward/edward/adsb/DecodingADSBposition.html.

     131072 is 2^17 since CPR latitude and longitude are encoded in 17 bits.
    '''

    cprlat_even = cprlat0 / 131072.0
    cprlat_odd = cprlat1 / 131072.0
    cprlon_even = cprlon0 / 131072.0
    cprlon_odd = cprlon1 / 131072.0

    air_d_lat_even = 360.0 / 60
    air_d_lat_odd = 360.0 / 59

    # compute latitude index 'j'
    j = int(59 * cprlat_even - 60 * cprlat_odd + 0.5)

    lat_even = float(air_d_lat_even * (j % 60 + cprlat_even))
    lat_odd = float(air_d_lat_odd * (j % 59 + cprlat_odd))

    if lat_even >= 270:
        lat_even = lat_even - 360

    if lat_odd >= 270:
        lat_odd = lat_odd - 360

    # check if both are in the same latidude zone, exit if not
    if cprNL(lat_even) != cprNL(lat_odd):
        return None

    # compute ni, longitude index m, and longitude
    if (t0 > t1):
        ni = cprN(lat_even, 0)
        m = math.floor(cprlon_even * (cprNL(lat_even)-1)
                       - cprlon_odd * cprNL(lat_even) + 0.5)
        lon = (360.0 / ni) * (m % ni + cprlon_even)
        lat = lat_even
    else:
        ni = cprN(lat_odd, 1)
        m = math.floor(cprlon_even * (cprNL(lat_odd)-1)
                       - cprlon_odd * cprNL(lat_odd) + 0.5)
        lon = (360.0 / ni) * (m % ni + cprlon_odd)
        lat = lat_odd

    if lon > 180:
        lon = lon - 360

    return [lat, lon]


def get_speed_heading(msg):
    """Calculate the speed and heading."""
    msgbin = hex2bin(msg)

    v_ew_dir = bin2int(msgbin[45])
    v_ew = bin2int(msgbin[46:56])       # east-west velocity

    v_ns_dir = bin2int(msgbin[56])
    v_ns = bin2int(msgbin[57:67])       # north-south velocity

    v_ew = -1*v_ew if v_ew_dir else v_ew
    v_ns = -1*v_ns if v_ns_dir else v_ns

    # vr       = bin2int(msgbin[68:77])       # vertical rate
    # vr_dir   = bin2int(msgbin[77])

    speed = math.sqrt(v_ns*v_ns + v_ew*v_ew)    # unit in kts

    heading = math.atan2(v_ew, v_ns)
    heading = heading * 360.0 / (2 * math.pi)   # convert to degrees
    heading = heading if heading >= 0 else heading + 360     # no negative val
    return [speed, heading]


def get_callsign(msg):
    """Decode aircraft identification, aka. Callsign"""

    chars = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ#####_###############0123456789######'
    msgbin = hex2bin(msg)
    csbin = msgbin[40:96]

    cs = ''
    cs += chars[bin2int(csbin[0:6])]
    cs += chars[bin2int(csbin[6:12])]
    cs += chars[bin2int(csbin[12:18])]
    cs += chars[bin2int(csbin[18:24])]
    cs += chars[bin2int(csbin[24:30])]
    cs += chars[bin2int(csbin[30:36])]
    cs += chars[bin2int(csbin[36:42])]
    cs += chars[bin2int(csbin[42:48])]

    # clean string, remove spaces and marks, if any.
    cs = cs.replace('_', '')
    cs = cs.replace('#', '')
    return cs


def cprN(lat, is_odd):
    nl = cprNL(lat) - is_odd
    return nl if nl > 1 else 1


def cprNL(lat):
    try:
        nz = 60
        a = 1 - math.cos(math.pi * 2 / nz)
        b = math.cos(math.pi / 180.0 * abs(lat)) ** 2
        nl = 2 * math.pi / (math.acos(1 - a/b))
        return int(nl)
    except:
        # happens when latitude is +/-90 degree
        return 1
