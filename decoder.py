""" 
This is a decoder of ABS-D date from Mode-S receiver. The inputs 
    of most functions are the Hexdecial strings.

Created by  : Junzi Sun (TU Delft)
Date        : March 2015
"""

import math

def hex2bin(hexstr):
    """Convert a hexdecimal string to binary string, with zero fillings. """
    length = len(hexstr) * 4
    msgbin = bin(int(hexstr, 16))[2:]
    while ((len(msgbin)) < length):
        msgbin = '0' + msgbin
    return msgbin

def bin2int(msgbin):
    return int(msgbin, 2)

def get_df(msg):
    """Decode Downlink Format vaule, bits 1 to 5."""
    msgbin = hex2bin(msg)
    return bin2int( msgbin[0:5] )

def get_ca(msg):        
    """Decode CA vaule, bits: 6 to 8."""
    msgbin = hex2bin(msg)
    return bin2int( msgbin[5:8] )

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
    cprlat_odd  = cprlat1 / 131072.0
    cprlon_even = cprlon0 / 131072.0
    cprlon_odd  = cprlon0 / 131072.0

    air_d_lat_even = 360.0 / 60 
    air_d_lat_odd = 360.0 / 59 

    # compute latitude index 'j'
    j = int(59 * cprlat_even - 60 * cprlat_odd + 0.5)

    lat_even = float(air_d_lat_even * (j % 60 + cprlat_even))
    lat_odd  = float(air_d_lat_odd  * (j % 59 + cprlat_odd))

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
      m = math.floor( cprlon_even * (cprNL(lat_even)-1) - cprlon_odd * cprNL(lat_even) + 0.5 ) 
      lon = (360.0 / ni) * (m % ni + cprlon_even)
      lat = lat_even
    else:
      ni = cprN(lat_odd, 1)
      m = math.floor( cprlon_even * (cprNL(lat_odd)-1) - cprlon_odd * cprNL(lat_odd) + 0.5 ) 
      lon = (360.0 / ni) * (m % ni + cprlon_odd)
      lat = lat_odd

    if lon > 180:
        lon = lon - 360 

    return [lat, lon]


def get_speed_heading(msg):
    """Calculate the speed and heading."""
    msgbin = hex2bin(msg)

    v_ew_dir = bin2int(msgbin[45])
    v_ew     = bin2int(msgbin[46:56])       # east-west velocity

    v_ns_dir = bin2int(msgbin[56])
    v_ns     = bin2int(msgbin[57:67])       # north-south velocity

    v_ew = -1*v_ew if v_ew_dir else v_ew
    v_ns = -1*v_ns if v_ns_dir else v_ns

    # vr       = bin2int(msgbin[68:77])       # vertical rate
    # vr_dir   = bin2int(msgbin[77])

    speed = math.sqrt(v_ns*v_ns + v_ew*v_ew)    # unit in kts

    heading = math.atan2(v_ew, v_ns)
    heading = heading * 360.0 / (2 * math.pi)   #convert to degrees
    heading = heading if heading >= 0 else heading + 360     # no negative val
    return [speed, heading]

def get_callsign(msg):
    """Decode aircraft identification, aka. Callsign"""
    
    charset = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ#####_###############0123456789######'
    msgbin = hex2bin(msg)
    csbin = msgbin[40:96]

    cs = ''
    cs += charset[ bin2int(csbin[0:6]) ]
    cs += charset[ bin2int(csbin[6:12]) ]
    cs += charset[ bin2int(csbin[12:18]) ]
    cs += charset[ bin2int(csbin[18:24]) ]
    cs += charset[ bin2int(csbin[24:30]) ]
    cs += charset[ bin2int(csbin[30:36]) ]
    cs += charset[ bin2int(csbin[36:42]) ]
    cs += charset[ bin2int(csbin[42:48]) ]

    # clean string, remove spaces and marks, if any.
    cs = cs.replace('_', '')
    cs = cs.replace('#', '')
    return cs


def cprN (lat, isodd):
    nl = cprNL(lat) - isodd
    return nl if nl > 1 else 1


def cprNL(lat):
    """Lookup table to convert the latitude to index. """
    if lat < 0 : lat = -lat             # Table is simmetric about the equator.
    if lat < 10.47047130 : return 59
    if lat < 14.82817437 : return 58
    if lat < 18.18626357 : return 57
    if lat < 21.02939493 : return 56
    if lat < 23.54504487 : return 55
    if lat < 25.82924707 : return 54
    if lat < 27.93898710 : return 53
    if lat < 29.91135686 : return 52
    if lat < 31.77209708 : return 51
    if lat < 33.53993436 : return 50
    if lat < 35.22899598 : return 49
    if lat < 36.85025108 : return 48
    if lat < 38.41241892 : return 47
    if lat < 39.92256684 : return 46
    if lat < 41.38651832 : return 45
    if lat < 42.80914012 : return 44
    if lat < 44.19454951 : return 43
    if lat < 45.54626723 : return 42
    if lat < 46.86733252 : return 41
    if lat < 48.16039128 : return 40
    if lat < 49.42776439 : return 39
    if lat < 50.67150166 : return 38
    if lat < 51.89342469 : return 37
    if lat < 53.09516153 : return 36
    if lat < 54.27817472 : return 35
    if lat < 55.44378444 : return 34
    if lat < 56.59318756 : return 33
    if lat < 57.72747354 : return 32
    if lat < 58.84763776 : return 31
    if lat < 59.95459277 : return 30
    if lat < 61.04917774 : return 29
    if lat < 62.13216659 : return 28
    if lat < 63.20427479 : return 27
    if lat < 64.26616523 : return 26
    if lat < 65.31845310 : return 25
    if lat < 66.36171008 : return 24
    if lat < 67.39646774 : return 23
    if lat < 68.42322022 : return 22
    if lat < 69.44242631 : return 21
    if lat < 70.45451075 : return 20
    if lat < 71.45986473 : return 19
    if lat < 72.45884545 : return 18
    if lat < 73.45177442 : return 17
    if lat < 74.43893416 : return 16
    if lat < 75.42056257 : return 15
    if lat < 76.39684391 : return 14
    if lat < 77.36789461 : return 13
    if lat < 78.33374083 : return 12
    if lat < 79.29428225 : return 11
    if lat < 80.24923213 : return 10
    if lat < 81.19801349 : return 9
    if lat < 82.13956981 : return 8
    if lat < 83.07199445 : return 7
    if lat < 83.99173563 : return 6
    if lat < 84.89166191 : return 5
    if lat < 85.75541621 : return 4
    if lat < 86.53536998 : return 3
    if lat < 87.00000000 : return 2
    else : return 1
