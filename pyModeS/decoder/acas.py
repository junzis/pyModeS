"""
Decoding Air-Air Surveillance (ACAS) DF=0/16

[To be implemented]
"""
from __future__ import absolute_import, print_function, division

from pyModeS import common


def threat_type(msg):
    """
    Determine the threat type indicator

    ===== =======
    Value Meaning
    ===== =======
    0     No identity data in TID
    1     TID has Mode S address (ICAO)
    2     TID has altitude, range, and bearing
    3     Not assigned
    :param msg:
    :return: indicator of threat type
    """
    mb = common.hex2bin(msg)[32:]
    tti = common.bin2int(mb[28:30])
    return tti


def threat_identity(msg):    
    mb = common.hex2bin(msg)[32:]
    tti = threat_type(msg)
    
    # The ICAO of the threat is announced
    if tti == 1:
        return common.icao(mb[30:55])
    else:
        raise RuntimeError("%s: Missing threat identity (ICAO)")
    
    
def threat_location(msg):
    """
    Get the altitude, range, and bearing of the threat
    Altitude is the Mode C altitude
    :param msg:
    :return: tuple of the Mode C altitude, range, and bearing
    """
    mb = common.hex2bin(msg)[32:]
    tti = threat_type(msg)
    
    # Altitude, range, and bearing of threat
    if tti == 2:
        grey = mb[31] + mb[32] + mb[33] + mb[34] + mb[35] + mb[36] + mb[38] + mb[38] + mb[39] + mb[40] + mb[41] + mb[42] + mb[43]
        mode_c_alt = common.gray2alt(grey)
        _range = common.bin2int(mb[44:51])
        bearing = common.bin2int(mb[51:57])
        return mode_c_alt, _range, bearing


def has_multiple_threats(msg):
    """
    Indicate if the ACAS is processing zero, one, or more than one threat
    simultaneously
    :param msg:
    :return: boolean
    """
    mb = common.bin2int(msg)[32:]

    mte = mb[27]
    ara_b1 = mb[8]

    if ara_b1 == 0 and mte == 0:
        # There are no active threats
        return False
    elif ara_b1 == 1 and mte == 0:
        # There is a single threat
        return False
    elif mte == 1:
        # There are multiple threats
        return True
    else:
        return False


def active_resolution_advisories(msg):
    mb = common.bin2int(msg)[32:]
    ara_b1 = mb[8]
    ara_b2 = mb[9]
    ara_b1 = mb[8]
