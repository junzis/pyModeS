# Copyright (C) 2015 Junzi Sun (TU Delft)

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
The wrapper for decoding ADS-B messages
"""

from __future__ import absolute_import, print_function, division
from pyModeS.decoder import common
import pandas as pd # JoseAndresMR: I suppose you already have pandas in a common function, just change all occurrencies
# from pyModeS.decoder.bds import bds05, bds06, bds09

from pyModeS.decoder.bds.bds05 import airborne_position, airborne_position_with_ref, altitude
from pyModeS.decoder.bds.bds06 import surface_position, surface_position_with_ref, surface_velocity
from pyModeS.decoder.bds.bds08 import category, callsign
from pyModeS.decoder.bds.bds09 import airborne_velocity, altitude_diff

def df(msg):
    return common.df(msg)

def icao(msg):
    return common.icao(msg)

def typecode(msg):
    return common.typecode(msg)

def position(msg0, msg1, t0, t1, lat_ref=None, lon_ref=None):
    """Decode position from a pair of even and odd position message
    (works with both airborne and surface position messages)

    Args:
        msg0 (string): even message (28 bytes hexadecimal string)
        msg1 (string): odd message (28 bytes hexadecimal string)
        t0 (int): timestamps for the even message
        t1 (int): timestamps for the odd message

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """
    tc0 = typecode(msg0)
    tc1 = typecode(msg1)

    if (5<=tc0<=8 and 5<=tc1<=8):
        if (not lat_ref) or (not lon_ref):
            raise RuntimeError("Surface position encountered, a reference \
                               position lat/lon required. Location of \
                               receiver can be used.")
        else:
            return surface_position(msg0, msg1, t0, t1, lat_ref, lon_ref)

    elif (9<=tc0<=18 and 9<=tc1<=18):
        # Airborne position with barometric height
        return airborne_position(msg0, msg1, t0, t1)

    elif (20<=tc0<=22 and 20<=tc1<=22):
        # Airborne position with GNSS height
        return airborne_position(msg0, msg1, t0, t1)

    else:
        raise RuntimeError("incorrect or inconsistant message types")


def position_with_ref(msg, lat_ref, lon_ref):
    """Decode position with only one message,
    knowing reference nearby location, such as previously
    calculated location, ground station, or airport location, etc.
    Works with both airborne and surface position messages.
    The reference position shall be with in 180NM (airborne) or 45NM (surface)
    of the true position.

    Args:
        msg (string): even message (28 bytes hexadecimal string)
        lat_ref: previous known latitude
        lon_ref: previous known longitude

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """

    tc = typecode(msg)

    if 5<=tc<=8:
        return surface_position_with_ref(msg, lat_ref, lon_ref)

    elif 9<=tc<=18 or 20<=tc<=22:
        return airborne_position_with_ref(msg, lat_ref, lon_ref)

    else:
        raise RuntimeError("incorrect or inconsistant message types")


def altitude(msg):
    """Decode aircraft altitude

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: altitude in feet
    """

    tc = typecode(msg)

    if tc<5 or tc==19 or tc>22:
        raise RuntimeError("%s: Not a position message" % msg)

    if tc>=5 and tc<=8:
        # surface position, altitude 0
        return 0

    msgbin = common.hex2bin(msg)
    q = msgbin[47]
    if q:
        n = common.bin2int(msgbin[40:47]+msgbin[48:52])
        alt = n * 25 - 1000
        return alt
    else:
        return None


def velocity(msg):
    """Calculate the speed, heading, and vertical rate
    (handles both airborne or surface message)

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        (int, float, int, string): speed (kt), ground track or heading (degree),
            rate of climb/descend (ft/min), and speed type
            ('GS' for ground speed, 'AS' for airspeed)
    """

    if 5 <= typecode(msg) <= 8:
        return surface_velocity(msg)

    elif typecode(msg) == 19:
        return airborne_velocity(msg)

    else:
        raise RuntimeError("incorrect or inconsistant message types, expecting 4<TC<9 or TC=19")


def speed_heading(msg):
    """Get speed and ground track (or heading) from the velocity message
    (handles both airborne or surface message)

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        (int, float): speed (kt), ground track or heading (degree)
    """
    spd, trk_or_hdg, rocd, tag = velocity(msg)
    return spd, trk_or_hdg


def oe_flag(msg):
    """Check the odd/even flag. Bit 54, 0 for even, 1 for odd.
    Args:
        msg (string): 28 bytes hexadecimal message string
    Returns:
        int: 0 or 1, for even or odd frame
    """
    msgbin = common.hex2bin(msg)
    return int(msgbin[53])


def version(msg):
    """ADS-B Version

    Args:
        msg (string): 28 bytes hexadecimal message string, TC = 31

    Returns:
        int: version number
    """
    tc = typecode(msg)

    if tc != 31:
        raise RuntimeError("%s: Not a status operation message, expecting TC = 31" % msg)

    msgbin = common.hex2bin(msg)
    version = common.bin2int(msgbin[72:75])

    return version


def nic_v1(msg,nic_sup_b):
    """Calculate NIC, navigation integrity category, for ADS-B version 1

    Args:
        msg (string): 28 bytes hexadecimal message string
        nic_sup_b (int or string): NIC supplement

    Returns:
        int or string: Horizontal Radius of Containment 
        int or string: Vertical Protection Limit
    """
    if typecode(msg) < 5 or typecode(msg) > 22:
        raise RuntimeError("%s: Not a surface position message (5<TC<8), \
                           airborne position message (8<TC<19), \
                           or airborne position with GNSS height (20<TC<22)" % msg)

    tc = typecode(msg)               

    nic_df = pd.read_csv('/home/josmilrom/Libraries/pyModeS/pyModeS/decoder/adsb_ua_parameters/NIC_v1.csv', sep=',')
    nic_df_extract = nic_df[(nic_df.TC == tc) & (nic_df.NICs == nic_sup_b)]   

    Rc = nic_df_extract['Rc'][0]
    VPL = nic_df_extract['VPL'][0]
    return Rc, VPL


def nic_v2(msg, nic_a, nic_b, nic_c):
    """Calculate NIC, navigation integrity category, for ADS-B version 2

    Args:
        msg (string): 28 bytes hexadecimal message string
        nic_a (int or string): NIC supplement
        nic_b (int or srting): NIC supplement
        nic_c (int or string): NIC supplement

    Returns:
        int or string: Horizontal Radius of Containment 
    """
    if typecode(msg) < 5 or typecode(msg) > 22:
        raise RuntimeError("%s: Not a surface position message (5<TC<8) \
                           airborne position message (8<TC<19), \
                           or airborne position with GNSS height (20<TC<22)" % msg)

    tc = typecode(msg)               

    nic_df = pd.read_csv('/home/josmilrom/Libraries/pyModeS/pyModeS/decoder/adsb_ua_parameters/NIC_v2.csv', sep=',')

    if tc in range(5,9):
        nic_df_extract = [(nic_df.TC == tc) & (nic_df.NICa == nic_a) & (nic_df.NICc == nic_c)]
    elif tc in range(9,19):
        nic_df_extract = [(nic_df.TC == tc) & (nic_df.NICa == nic_a) & (nic_df.NICb == nic_b)]
    elif tc in range(20,23):
        nic_df_extract = [nic_df.TC == tc]

    Rc = nic_df_extract['Rc'][0]

    return Rc
    
    

def nic_s(msg):
    """Obtain NIC supplement bit, TC=31 message

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: NICs number (0 or 1)
    """
    tc = typecode(msg)

    if tc != 31:
        raise RuntimeError("%s: Not a status operation message, expecting TC = 31" % msg)

    msgbin = common.hex2bin(msg)
    nic_s = int(msgbin[75])

    return nic_s


def nic_a_c(msg):
    """Obtain NICa/c, navigation integrity category supplements a and c

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        (int, int): NICa and NICc number (0 or 1)
    """
    tc = typecode(msg)

    if tc != 31:
        raise RuntimeError("%s: Not a status operation message, expecting TC = 31" % msg)

    msgbin = common.hex2bin(msg)
    nic_a = int(msgbin[75])
    nic_c = int(msgbin[51])

    return nic_a, nic_c


def nic_b(msg):
    """Obtain NICb, navigation integrity category supplement-b

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: NICb number (0 or 1)
    """
    tc = typecode(msg)

    if tc < 9 or tc > 18:
        raise RuntimeError("%s: Not a airborne position message, expecting 8<TC<19" % msg)

    msgbin = common.hex2bin(msg)
    nic_b = int(msgbin[39])

    return nic_b


def nac_p(msg):
    """Calculate NACp, Navigation Accuracy Category - Position

    Args:
        msg (string): 28 bytes hexadecimal message string, TC = 29 or 31

    Returns:
        int or string: 95% horizontal accuracy bounds, Estimated Position Uncertainty
        int or string: 95% vertical accuracy bounds, Vertical Estimated Position Uncertainty
    """
    tc = typecode(msg)

    if tc not in [29, 31]:
        raise RuntimeError("%s: Not a target state and status message, \
                           or operation status message, expecting TC = 29 or 31" % msg)

    msgbin = common.hex2bin(msg)

    nacp_df = pd.read_csv('/home/josmilrom/Libraries/pyModeS/pyModeS/decoder/adsb_ua_parameters/NACp.csv', sep=',')

    if tc == 29:
        nac_p = common.bin2int(msgbin[71:75])
        nacp_df_extract = nac_p[nacp_df.NACp == nac_p]
    elif tc == 31:
        nac_p = common.bin2int(msgbin[76:80])
        nacp_df_extract = nac_p[nacp_df.NACp == nac_p]

    HFU = nacp_df_extract['HFU'][0]
    VEPU = nacp_df_extract['VEPU'][0]

    return HFU, VEPU

def nac_v(msg):
    """Calculate NACv, Navigation Accuracy Category - Velocity

    Args:
        msg (string): 28 bytes hexadecimal message string, TC = 19

    Returns:
        int or string: 95% horizontal accuracy bounds for velocity, Horizontal Figure of Merit 
        int or string: 95% vertical accuracy bounds for velocity, Vertical Figure of Merit
    """
    tc = typecode(msg)

    if tc != 19:
        raise RuntimeError("%s: Not an airborne velocity message, expecting TC = 19" % msg)

    nacv_df = pd.read_csv('/home/josmilrom/Libraries/pyModeS/pyModeS/decoder/adsb_ua_parameters/NACv.csv', sep=',')

    msgbin = common.hex2bin(msg)
    nac_v = common.bin2int(msgbin[42:45])
    nacv_df_extract = nacv_df[nacv_df.NACv == nac_v]
    HFOMr = nacv_df_extract['HFOMr'][0]
    VFOMr = nacv_df_extract['VFOMr'][0]

    return HFOMr, VFOMr


def sil(msg, version):
    """Calculate SIL, Surveillance Integrity Level

    Args:
        msg (string): 28 bytes hexadecimal message string with TC = 29, 31

    Returns:
        int or string: Probability of exceeding Horizontal Radius of Containment RCu 
        int or string: Probability of exceeding Vertical Integrity Containment Region VPL 
        string: SIL supplement based on "per hour" or "per sample"
    """
    tc = typecode(msg)

    if tc not in [29, 31]:
        raise RuntimeError("%s: Not a target state and status messag, \
                           or operation status message, expecting TC = 29 or 31" % msg)

    sil_df = pd.read_csv('/home/josmilrom/Libraries/pyModeS/pyModeS/decoder/adsb_ua_parameters/SIL.csv', sep=',')

    msgbin = common.hex2bin(msg)

    if tc == 29:
        sil = common.bin2int(msgbin[76:78])
    elif tc == 31:
        sil = common.bin2int(msg[82:84])

    sil_df_extract = sil_df[sil_df.NACv == sil]
    PR_RCu = sil_df_extract['PR_RCu'][0]
    PE_VPL = sil_df_extract['PE_VPL'][0]

    if version == 1:
        return PR_RCu, PE_VPL
    if version == 2:
        if tc == 29:
            sil_sup = common.bin2int(msgbin[39])
        elif tc == 31:
            sil_sup = common.bin2int(msgbin[86])
        
        if sil_sup == 0:
            base = "per hour"
        elif sil_sup == 1:
            base = "per sample"

        return PR_RCu, PE_VPL, base

def nuc_p(msg):
    """Calculate NUCp, Navigation Uncertainty Category - Position

    Args:
        msg (string): 28 bytes hexadecimal message string,

    Returns:
        int or string: Horizontal Protection Limit
        int or string: 95% Containment Radius - Horizontal
        int or string: 95% Containment Radius - Vertical (only for airborne position with GNSS height messages)

    """
    tc = typecode(msg)

    if typecode(msg) < 5 or typecode(msg) > 22:
        raise RuntimeError("%s: Not a surface position message (5<TC<8), \
                           airborne position message (8<TC<19), \
                           or airborne position with GNSS height (20<TC<22)" % msg)

    nucp_df = pd.read_csv('/home/josmilrom/Libraries/pyModeS/pyModeS/decoder/adsb_ua_parameters/NUCp.csv', sep=',')

    nucp_df_extract = nucp_df[nucp_df.TC == tc]
    HPL = nucp_df_extract['HPL'][0]
    RCu = nucp_df_extract['RCu'][0]

    if tc not in range(20,23):
        return HPL, RCu
    else: 
        RCv = nucp_df_extract['RCv'][0]
        return HPL, RCu, RCv

def nuc_v(msg):
    """Calculate NUCv, Navigation Uncertainty Category - Velocity

    Args:
        msg (string): 28 bytes hexadecimal message string,

    Returns:
        int or string: 95% Horizontal Velocity Error 
        int or string: 95% Vertical Velocity Error
    """
    tc = typecode(msg)

    if tc != 19:
        raise RuntimeError("%s: Not an airborne velocity message, expecting TC = 19" % msg)

    nucv_df = pd.read_csv('/home/josmilrom/Libraries/pyModeS/pyModeS/decoder/adsb_ua_parameters/NUCv.csv', sep=',')

    nucv_df_extract = nucv_df[nucv_df.TC == tc]

    HVE = nucv_df_extract['HVE'][0]
    VVE = nucv_df_extract['VVE'][0]

    return HVE, VVE