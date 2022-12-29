"""
Decoding Air-Air Surveillance (ACAS) DF=0/16
"""

from __future__ import annotations

from .. import common
import warnings

warnings.simplefilter("always", UserWarning)


def isACAS(msg: str) -> bool:
    """Check if the message is an ACAS coordination message.

    :param msg: 28 hexdigits string
    :return: if VDS is 3,1
    """
    mv = common.hex2bin(common.data(msg))

    vds = mv[0:8]
    if vds == "00110000":
        return True
    else:
        return False


def rac(msg: str) -> None | str:
    """Resolution Advisory Complement.

    :param msg: 28 hexdigits string
    :return: RACs
    """
    if not isACAS(msg):
        warnings.warn("Not an ACAS coordination message.")
        return None

    RAC = []

    mv = common.hex2bin(common.data(msg))

    if mv[22] == "1":
        RAC.append("do not pass below")

    if mv[23] == "1":
        RAC.append("do not pass above")

    if mv[24] == "1":
        RAC.append("do not pass left")

    if mv[25] == "1":
        RAC.append("do not pass right")

    return "; ".join(RAC)


def rat(msg: str) -> None | int:
    """RA terminated indicator

    Mode S transponder is still required to report RA 18 seconds after
    it is terminated by ACAS. Hence, the RAT filed is used.

    :param msg: 28 hexdigits string
    :return: if RA has been terminated
    """
    if not isACAS(msg):
        warnings.warn("Not an ACAS coordination message.")
        return None

    mv = common.hex2bin(common.data(msg))
    mte = int(mv[26])
    return mte


def mte(msg: str) -> None | int:
    """Multiple threat encounter.

    :param msg: 28 hexdigits string
    :return: if there are multiple threats
    """
    if not isACAS(msg):
        warnings.warn("Not an ACAS coordination message.")
        return None

    mv = common.hex2bin(common.data(msg))
    mte = int(mv[27])
    return mte


def ara(msg: str) -> None | str:
    """Decode active resolution advisory.

    :param msg: 28 bytes hexadecimal message string
    :return: RA charactristics
    """
    if not isACAS(msg):
        warnings.warn("Not an ACAS coordination message.")
        return None
    mv = common.hex2bin(common.data(msg))

    mte = int(mv[27])

    ara_b1 = int(mv[8])
    ara_b2 = int(mv[9])
    ara_b3 = int(mv[10])
    ara_b4 = int(mv[11])
    ara_b5 = int(mv[12])
    ara_b6 = int(mv[14])
    ara_b7 = int(mv[15])
    # ACAS III are bits 15-22

    RA = []

    if ara_b1 == 1:
        if ara_b2:
            RA.append("corrective")
        else:
            RA.append("preventive")

        if ara_b3:
            RA.append("downward sense")
        else:
            RA.append("upward sense")

        if ara_b4:
            RA.append("increased rate")

        if ara_b5:
            RA.append("sense reversal")

        if ara_b6:
            RA.append("altitude crossing")

        if ara_b7:
            RA.append("positive")
        else:
            RA.append("vertical speed limit")

    if ara_b1 == 0 and mte == 1:
        if ara_b2:
            RA.append("requires a correction in the upward sense")

        if ara_b3:
            RA.append("requires a positive climb")

        if ara_b4:
            RA.append("requires a correction in downward sense")

        if ara_b5:
            RA.append("requires a positive descent")

        if ara_b6:
            RA.append("requires a crossing")

        if ara_b7:
            RA.append("requires a sense reversal")

    return "; ".join(RA)
