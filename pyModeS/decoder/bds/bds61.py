# ------------------------------------------
#   BDS 6,1
#   ADS-B TC=28
#   Aircraft Airborne status
# ------------------------------------------

from ... import common


def is_emergency(msg: str) -> bool:
    """Check if the aircraft is reporting an emergency.

    Non-emergencies are either a subtype of zero (no information) or
    subtype of one and a value of zero (no emergency).
    Subtype = 2 indicates an ACAS RA broadcast, look in BDS 3,0

    :param msg: 28 bytes hexadecimal message string
    :return: if the aircraft has declared an emergency
    """
    if common.typecode(msg) != 28:
        raise RuntimeError(
            "%s: Not an airborne status message, expecting TC=28" % msg
        )

    mb = common.hex2bin(msg)[32:]
    subtype = common.bin2int(mb[5:8])

    if subtype == 2:
        raise RuntimeError("%s: Emergency message is ACAS-RA, not implemented")

    emergency_state = common.bin2int(mb[8:11])

    if subtype == 1 and emergency_state == 1:
        return True
    else:
        return False


def emergency_state(msg: str) -> int:
    """Decode aircraft emergency state.

    Value   Meaning
    -----   -----------------------
    0       No emergency
    1       General emergency
    2       Lifeguard/Medical
    3       Minimum fuel
    4       No communications
    5       Unlawful communications
    6-7     Reserved

    :param msg: 28 bytes hexadecimal message string
    :return: emergency state
    """

    mb = common.hex2bin(msg)[32:]
    subtype = common.bin2int(mb[5:8])

    if subtype == 2:
        raise RuntimeError("%s: Emergency message is ACAS-RA, not implemented")

    emergency_state = common.bin2int(mb[8:11])
    return emergency_state


def emergency_squawk(msg: str) -> str:
    """Decode squawk code.

    Emergency value 1: squawk 7700.
    Emergency value 4: squawk 7600.
    Emergency value 5: squawk 7500.

    :param msg: 28 bytes hexadecimal message string
    :return: aircraft squawk code
    """
    if common.typecode(msg) != 28:
        raise RuntimeError(
            "%s: Not an airborne status message, expecting TC=28" % msg
        )

    msgbin = common.hex2bin(msg)

    # construct the 13 bits Mode A ID code
    idcode = msgbin[43:56]

    squawk = common.squawk(idcode)
    return squawk
