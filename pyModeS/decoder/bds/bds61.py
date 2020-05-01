# ------------------------------------------
#   BDS 6,1
#   ADS-B TC=28
#   Aircraft Airborne status
# ------------------------------------------

from __future__ import absolute_import, print_function, division

from pyModeS import common


def is_emergency(msg):
    """
    Check if the aircraft is reporting an emergency
    Non-emergencies are either a subtype of zero (no information) or
    subtype of one and a value of zero (no emergency).
    Subtype = 2 indicates an ACAS RA broadcast, look in BDS 3,0
    :param msg:
    :return: if the aircraft has declared an emergency
    """
    if common.typecode(msg) != 28:
        raise RuntimeError("%s: Not an airborne status message, expecting TC=28" % msg)

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:8])
    emergency_state = common.bin2int(mb[8:11])

    if subtype == 2:
        raise RuntimeError("%s: Emergency message is ACAS-RA, not implemented")

    if subtype == 0:
        return False
    elif subtype == 1 and emergency_state == 0:
        return False
    else:
        return True


def emergency(msg):
    """
    Return the aircraft emergency

    ===== =======
    Value Meaning
    ===== =======
    1     General emergency
    2     Lifeguard/Medical
    3     Minimum fuel
    4     No communications
    5     Unlawful communications
    6     Reserved
    7     Reserved
    :param msg:
    :return: If the aircraft has declared an emergency, the type
    """
    if not is_emergency(msg):
        raise RuntimeError("%s: Aircraft not declared an emergency" % msg)
    else:
        mb = common.hex2bin(msg)[32:]

        subtype = common.bin2int(mb[5:8])
        emergency_state = common.bin2int(mb[8:11])

        return emergency_state


def emergency_squawk(msg):
    """
    Squawk code of the transmitting aircraft
    Emergency value 1 will be squawk 7700
    Emergency value 4 will be squawk 7600
    Emergency value 5 will be squawk 7500
    :param msg:
    :return: aircraft squawk code
    """
    if common.typecode(msg) != 28:
        raise RuntimeError("%s: Not an airborne status message, expecting TC=28" % msg)

    mb = common.hex2bin(msg)[32:]
    C1 = mb[11]
    A1 = mb[12]
    C2 = mb[13]
    A2 = mb[14]
    C4 = mb[15]
    A4 = mb[16]
    B1 = mb[17]
    D1 = mb[18]
    B2 = mb[19]
    D2 = mb[20]
    B4 = mb[21]
    D4 = mb[22]

    byte1 = int(A4 + A2 + A1, 2)
    byte2 = int(B4 + B2 + B1, 2)
    byte3 = int(C4 + C2 + C1, 2)
    byte4 = int(D4 + D2 + D1, 2)
    return str(byte1) + str(byte2) + str(byte3) + str(byte4)
