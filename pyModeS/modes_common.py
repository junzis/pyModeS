from __future__ import absolute_import, print_function, division
from . import util


def icao(msg):
    """Calculate the ICAO address from an Mode-S message
    with DF4, DF5, DF20, DF21

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        String: ICAO address in 6 bytes hexadecimal string
    """

    if util.df(msg) not in (4, 5, 20, 21):
        # raise RuntimeError("Message DF must be in (4, 5, 20, 21)")
        return None

    c0 = util.bin2int(util.crc(msg, encode=True))
    c1 = util.hex2int(msg[-6:])
    addr = '%06X' % (c0 ^ c1)
    return addr


def idcode(msg):
    """Computes identity (squawk code) from DF5 or DF21 message, bit 20-32.
    credit: @fbyrkjeland

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        string: squawk code
    """

    if util.df(msg) not in [5, 21]:
        raise RuntimeError("Message must be Downlink Format 5 or 21.")

    mbin = util.hex2bin(msg)

    C1 = mbin[19]
    A1 = mbin[20]
    C2 = mbin[21]
    A2 = mbin[22]
    C4 = mbin[23]
    A4 = mbin[24]
    # _ = mbin[25]
    B1 = mbin[26]
    D1 = mbin[27]
    B2 = mbin[28]
    D2 = mbin[29]
    B4 = mbin[30]
    D4 = mbin[31]

    byte1 = int(A4+A2+A1, 2)
    byte2 = int(B4+B2+B1, 2)
    byte3 = int(C4+C2+C1, 2)
    byte4 = int(D4+D2+D1, 2)

    return str(byte1) + str(byte2) + str(byte3) + str(byte4)


def altcode(msg):
    """Computes the altitude from DF4 or DF20 message, bit 20-32.
    credit: @fbyrkjeland

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: altitude in ft
    """

    if util.df(msg) not in [4, 20]:
        raise RuntimeError("Message must be Downlink Format 4 or 20.")

    # Altitude code, bit 20-32
    mbin = util.hex2bin(msg)

    mbit = mbin[25]   # M bit: 26
    qbit = mbin[27]   # Q bit: 28


    if mbit == '0':         # unit in ft
        if qbit == '1':     # 25ft interval
            vbin = mbin[19:25] + mbin[26] + mbin[28:32]
            alt = util.bin2int(vbin) * 25 - 1000
        if qbit == '0':     # 100ft interval, above 50175ft
            C1 = mbin[19]
            A1 = mbin[20]
            C2 = mbin[21]
            A2 = mbin[22]
            C4 = mbin[23]
            A4 = mbin[24]
            # _ = mbin[25]
            B1 = mbin[26]
            # D1 = mbin[27]     # always zero
            B2 = mbin[28]
            D2 = mbin[29]
            B4 = mbin[30]
            D4 = mbin[31]

            graystr =  D2 + D4 + A1 + A2 + A4 + B1 + B2 + B4 + C1 + C2 + C4
            alt = gray2alt(graystr)

    if mbit == '1':         # unit in meter
        vbin = mbin[19:25] + mbin[26:31]
        alt = int(util.bin2int(vbin) * 3.28084)  # convert to ft

    return alt

def gray2alt(codestr):
    gc500 = codestr[:8]
    n500 = util.gray2int(gc500)

    # in 100-ft step must be converted first
    gc100 = codestr[8:]
    n100 = util.gray2int(gc100)

    if n100 in [0, 5, 6]:
        return None

    if n100 == 7:
        n100 = 5

    if n500%2:
        n100 = 6 - n100

    alt = (n500*500 + n100*100) - 1300
    return alt
