"""
Decoding Air-Air Surveillance (ACAS) DF=0/16

[To be implemented]
"""

from pyModeS import common


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
