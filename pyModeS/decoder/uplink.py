from typing import Optional
from .. import common
from textwrap import wrap


def uplink_icao(msg: str) -> str:
    "Calculate the ICAO address from a Mode-S interrogation (uplink message)"
    p_gen = 0xFFFA0480 << ((len(msg) - 14) * 4)
    data = int(msg[:-6], 16)
    PA = int(msg[-6:], 16)
    ad = 0
    topbit = 0b1 << (len(msg) * 4 - 25)
    for j in range(0, len(msg) * 4, 1):
        if data & topbit:
            data ^= p_gen
        data = (data << 1) + ((PA >> 23) & 1)
        PA = PA << 1
        if j > (len(msg) * 4 - 26):
            ad = ad + ((data >> (len(msg) * 4 - 25)) & 1)
            ad = ad << 1
    return "%06X" % (ad >> 2)


def uf(msg: str) -> int:
    """Decode Uplink Format value, bits 1 to 5."""
    ufbin = common.hex2bin(msg[:2])
    return min(common.bin2int(ufbin[0:5]), 24)


def bds(msg: str) -> Optional[str]:
    "Decode requested BDS register from selective (Roll Call) interrogation."
    UF = uf(msg)
    msgbin = common.hex2bin(msg)
    msgbin_split = wrap(msgbin, 8)
    mbytes = list(map(common.bin2int, msgbin_split))

    if UF in {4, 5, 20, 21}:

        di = mbytes[1] & 0x7  # DI - Designator Identification
        RR = mbytes[1] >> 3 & 0x1F
        if RR > 15:
            BDS1 = RR - 16
            if di == 7:
                RRS = mbytes[2] & 0x0F
                BDS2 = RRS
            elif di == 3:
                RRS = ((mbytes[2] & 0x1) << 3) | ((mbytes[3] & 0xE0) >> 5)
                BDS2 = RRS
            else:
                # for other values of DI, the BDS2 is assumed 0
                # (as per ICAO Annex 10 Vol IV)
                BDS2 = 0

            return str(format(BDS1,"X")) + str(format(BDS2,"X"))
        else:
            return None
    else:
        return None


def pr(msg: str) -> Optional[int]:
    """Decode PR (probability of reply) field from All Call interrogation.
    Interpretation:
    0 signifies reply with probability of 1
    1 signifies reply with probability of 1/2
    2 signifies reply with probability of 1/4
    3 signifies reply with probability of 1/8
    4 signifies reply with probability of 1/16
    5, 6, 7 not assigned
    8 signifies disregard lockout, reply with probability of 1
    9 signifies disregard lockout, reply with probability of 1/2
    10 signifies disregard lockout, reply with probability of 1/4
    11 signifies disregard lockout, reply with probability of 1/8
    12 signifies disregard lockout, reply with probability of 1/16
    13, 14, 15 not assigned.
    """
    msgbin = common.hex2bin(msg)
    msgbin_split = wrap(msgbin, 8)
    mbytes = list(map(common.bin2int, msgbin_split))
    if uf(msg) == 11:
        return ((mbytes[0] & 0x7) << 1) | ((mbytes[1] & 0x80) >> 7)
    else:
        return None


def ic(msg: str) -> Optional[str]:
    """Decode IC (interrogator code) from a ground-based interrogation."""

    UF = uf(msg)
    msgbin = common.hex2bin(msg)
    msgbin_split = wrap(msgbin, 8)
    mbytes = list(map(common.bin2int, msgbin_split))
    IC = None
    if UF == 11:

        codeLabel = mbytes[1] & 0x7
        icField = (mbytes[1] >> 3) & 0xF

        # Store the Interogator Code
        ic_switcher = {
            0: "II" + str(icField),
            1: "SI" + str(icField),
            2: "SI" + str(icField + 16),
            3: "SI" + str(icField + 32),
            4: "SI" + str(icField + 48),
        }
        IC = ic_switcher.get(codeLabel, "")

    if UF in {4, 5, 20, 21}:
        di = mbytes[1] & 0x7
        RR = mbytes[1] >> 3 & 0x1F
        if RR > 15:
            BDS1 = RR - 16  # noqa: F841
        if di == 0 or di == 1 or di == 7:
            # II
            II = (mbytes[2] >> 4) & 0xF
            IC = "II" + str(II)
        elif di == 3:
            # SI
            SI = (mbytes[2] >> 2) & 0x3F
            IC = "SI" + str(SI)
    return IC


def lockout(msg):
    """Decode the lockout command from selective (Roll Call) interrogation."""
    msgbin = common.hex2bin(msg)
    msgbin_split = wrap(msgbin, 8)
    mbytes = list(map(common.bin2int, msgbin_split))

    if uf(msg) in {4, 5, 20, 21}:
        lockout = False
        di = mbytes[1] & 0x7
        if di == 7:
            # LOS
            if ((mbytes[3] & 0x40) >> 6) == 1:
                lockout = True
        elif di == 3:
            # LSS
            if ((mbytes[2] & 0x2) >> 1) == 1:
                lockout = True
        return lockout
    else:
        return None


def uplink_fields(msg):
    """Decode individual fields of a ground-based interrogation."""
    msgbin = common.hex2bin(msg)
    msgbin_split = wrap(msgbin, 8)
    mbytes = list(map(common.bin2int, msgbin_split))
    PR = ""
    IC = ""
    lockout = False
    di = ""
    RR = ""
    RRS = ""
    BDS = ""
    if uf(msg) == 11:

        # Probability of Reply decoding

        PR = ((mbytes[0] & 0x7) << 1) | ((mbytes[1] & 0x80) >> 7)

        #  Get cl and ic bit fields from the data
        #  Decode the SI or II interrogator code
        codeLabel = mbytes[1] & 0x7
        icField = (mbytes[1] >> 3) & 0xF

        # Store the Interogator Code
        ic_switcher = {
            0: "II" + str(icField),
            1: "SI" + str(icField),
            2: "SI" + str(icField + 16),
            3: "SI" + str(icField + 32),
            4: "SI" + str(icField + 48),
        }
        IC = ic_switcher.get(codeLabel, "")

    if uf(msg) in {4, 5, 20, 21}:
        # Decode the DI and get the lockout information conveniently
        # (LSS or LOS)

        # DI - Designator Identification
        di = mbytes[1] & 0x7
        RR = mbytes[1] >> 3 & 0x1F
        if RR > 15:
            BDS1 = RR - 16
            BDS2 = 0
        if di == 0 or di == 1:
            # II
            II = (mbytes[2] >> 4) & 0xF
            IC = "II" + str(II)
        elif di == 7:
            # LOS
            if ((mbytes[3] & 0x40) >> 6) == 1:
                lockout = True
            # II
            II = (mbytes[2] >> 4) & 0xF
            IC = "II" + str(II)
            RRS = mbytes[2] & 0x0F
            BDS2 = RRS
        elif di == 3:
            # LSS
            if ((mbytes[2] & 0x2) >> 1) == 1:
                lockout = True
            # SI
            SI = (mbytes[2] >> 2) & 0x3F
            IC = "SI" + str(SI)
            RRS = ((mbytes[2] & 0x1) << 3) | ((mbytes[3] & 0xE0) >> 5)
            BDS2 = RRS
        if RR > 15:
            BDS = str(format(BDS1,"X")) + str(format(BDS2,"X"))
            
    return {
        "DI": di,
        "IC": IC,
        "LOS": lockout,
        "PR": PR,
        "RR": RR,
        "RRS": RRS,
        "BDS": BDS,
    }
