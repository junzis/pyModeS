import numpy as np
from textwrap import wrap


def hex2bin(hexstr):
    """Convert a hexdecimal string to binary string, with zero fillings."""
    num_of_bits = len(hexstr) * 4
    binstr = bin(int(hexstr, 16))[2:].zfill(int(num_of_bits))
    return binstr


def hex2int(hexstr):
    """Convert a hexdecimal string to integer."""
    return int(hexstr, 16)


def bin2int(binstr):
    """Convert a binary string to integer."""
    return int(binstr, 2)


def bin2hex(binstr):
    """Convert a binary string to hexdecimal string."""
    return "{0:X}".format(int(binstr, 2))


def df(msg):
    """Decode Downlink Format value, bits 1 to 5."""
    dfbin = hex2bin(msg[:2])
    return min(bin2int(dfbin[0:5]), 24)


def crc(msg, encode=False):
    """Mode-S Cyclic Redundancy Check.

    Detect if bit error occurs in the Mode-S message. When encode option is on,
    the checksum is generated.

    Args:
        msg (string): 28 bytes hexadecimal message string
        encode (bool): True to encode the date only and return the checksum
    Returns:
        int: message checksum, or partity bits (encoder)

    """
    # the CRC generator
    G = [int("11111111", 2), int("11111010", 2), int("00000100", 2), int("10000000", 2)]

    if encode:
        msg = msg[:-6] + "000000"

    msgbin = hex2bin(msg)
    msgbin_split = wrap(msgbin, 8)
    mbytes = list(map(bin2int, msgbin_split))

    for ibyte in range(len(mbytes) - 3):
        for ibit in range(8):
            mask = 0x80 >> ibit
            bits = mbytes[ibyte] & mask

            if bits > 0:
                mbytes[ibyte] = mbytes[ibyte] ^ (G[0] >> ibit)
                mbytes[ibyte + 1] = mbytes[ibyte + 1] ^ (
                    0xFF & ((G[0] << 8 - ibit) | (G[1] >> ibit))
                )
                mbytes[ibyte + 2] = mbytes[ibyte + 2] ^ (
                    0xFF & ((G[1] << 8 - ibit) | (G[2] >> ibit))
                )
                mbytes[ibyte + 3] = mbytes[ibyte + 3] ^ (
                    0xFF & ((G[2] << 8 - ibit) | (G[3] >> ibit))
                )

    result = (mbytes[-3] << 16) | (mbytes[-2] << 8) | mbytes[-1]

    return result


def crc_legacy(msg, encode=False):
    """Mode-S Cyclic Redundancy Check. (Legacy code, 2x slow)."""
    # the polynominal generattor code for CRC [1111111111111010000001001]
    generator = np.array(
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1]
    )
    ng = len(generator)

    msgnpbin = np.array([int(i) for i in hex2bin(msg)])

    if encode:
        msgnpbin[-24:] = [0] * 24

    # loop all bits, except last 24 piraty bits
    for i in range(len(msgnpbin) - 24):
        if msgnpbin[i] == 0:
            continue

        # perform XOR, when 1
        msgnpbin[i : i + ng] = np.bitwise_xor(msgnpbin[i : i + ng], generator)

    # last 24 bits
    msgbin = np.array2string(msgnpbin[-24:], separator="")[1:-1]
    reminder = bin2int(msgbin)

    return reminder


def floor(x):
    """Mode-S floor function.

    Defined as the greatest integer value k, such that k <= x
    For example: floor(3.6) = 3 and floor(-3.6) = -4

    """
    return int(np.floor(x))


def icao(msg):
    """Calculate the ICAO address from an Mode-S message.

    Applicable only with DF4, DF5, DF20, DF21 messages.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        String: ICAO address in 6 bytes hexadecimal string

    """
    DF = df(msg)

    if DF in (11, 17, 18):
        addr = msg[2:8]
    elif DF in (0, 4, 5, 16, 20, 21):
        c0 = crc(msg, encode=True)
        c1 = int(msg[-6:], 16)
        addr = "%06X" % (c0 ^ c1)
    else:
        addr = None

    return addr


def is_icao_assigned(icao):
    """Check whether the ICAO address is assigned (Annex 10, Vol 3)."""
    if (icao is None) or (not isinstance(icao, str)) or (len(icao) != 6):
        return False

    icaoint = int(icao, 16)

    if 0x200000 < icaoint < 0x27FFFF:
        return False  # AFI
    if 0x280000 < icaoint < 0x28FFFF:
        return False  # SAM
    if 0x500000 < icaoint < 0x5FFFFF:
        return False  # EUR, NAT
    if 0x600000 < icaoint < 0x67FFFF:
        return False  # MID
    if 0x680000 < icaoint < 0x6F0000:
        return False  # ASIA
    if 0x900000 < icaoint < 0x9FFFFF:
        return False  # NAM, PAC
    if 0xB00000 < icaoint < 0xBFFFFF:
        return False  # CAR
    if 0xD00000 < icaoint < 0xDFFFFF:
        return False  # future
    if 0xF00000 < icaoint < 0xFFFFFF:
        return False  # future

    return True


def typecode(msg):
    """Type code of ADS-B message

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: type code number
    """
    if df(msg) not in (17, 18):
        return None

    tcbin = hex2bin(msg[8:10])
    return bin2int(tcbin[0:5])


def cprNL(lat):
    """NL() function in CPR decoding."""

    if np.isclose(lat, 0):
        return 59
    elif np.isclose(abs(lat), 87):
        return 2
    elif lat > 87 or lat < -87:
        return 1

    nz = 15
    a = 1 - np.cos(np.pi / (2 * nz))
    b = np.cos(np.pi / 180.0 * abs(lat)) ** 2
    nl = 2 * np.pi / (np.arccos(1 - a / b))
    NL = floor(nl)
    return NL


def idcode(msg):
    """Compute identity (squawk code).

    Applicable only for DF5 or DF21 messages, bit 20-32.
    credit: @fbyrkjeland

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        string: squawk code

    """
    if df(msg) not in [5, 21]:
        raise RuntimeError("Message must be Downlink Format 5 or 21.")

    mbin = hex2bin(msg)

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

    byte1 = int(A4 + A2 + A1, 2)
    byte2 = int(B4 + B2 + B1, 2)
    byte3 = int(C4 + C2 + C1, 2)
    byte4 = int(D4 + D2 + D1, 2)

    return str(byte1) + str(byte2) + str(byte3) + str(byte4)


def altcode(msg):
    """Compute the altitude.

    Applicable only for DF4 or DF20 message, bit 20-32.
    credit: @fbyrkjeland

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: altitude in ft

    """
    if df(msg) not in [0, 4, 16, 20]:
        raise RuntimeError("Message must be Downlink Format 0, 4, 16, or 20.")

    # Altitude code, bit 20-32
    mbin = hex2bin(msg)

    mbit = mbin[25]  # M bit: 26
    qbit = mbin[27]  # Q bit: 28

    if mbit == "0":  # unit in ft
        if qbit == "1":  # 25ft interval
            vbin = mbin[19:25] + mbin[26] + mbin[28:32]
            alt = bin2int(vbin) * 25 - 1000
        if qbit == "0":  # 100ft interval, above 50175ft
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

            graystr = D2 + D4 + A1 + A2 + A4 + B1 + B2 + B4 + C1 + C2 + C4
            alt = gray2alt(graystr)

    if mbit == "1":  # unit in meter
        vbin = mbin[19:25] + mbin[26:31]
        alt = int(bin2int(vbin) * 3.28084)  # convert to ft

    return alt


def gray2alt(codestr):
    gc500 = codestr[:8]
    n500 = gray2int(gc500)

    # in 100-ft step must be converted first
    gc100 = codestr[8:]
    n100 = gray2int(gc100)

    if n100 in [0, 5, 6]:
        return None

    if n100 == 7:
        n100 = 5

    if n500 % 2:
        n100 = 6 - n100

    alt = (n500 * 500 + n100 * 100) - 1300
    return alt


def gray2int(graystr):
    """Convert greycode to binary."""
    num = bin2int(graystr)
    num ^= num >> 8
    num ^= num >> 4
    num ^= num >> 2
    num ^= num >> 1
    return num


def data(msg):
    """Return the data frame in the message, bytes 9 to 22."""
    return msg[8:-6]


def allzeros(msg):
    """Check if the data bits are all zeros.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        bool: True or False

    """
    d = hex2bin(data(msg))

    if bin2int(d) > 0:
        return False
    else:
        return True


def wrongstatus(data, sb, msb, lsb):
    """Check if the status bit and field bits are consistency.

    This Function is used for checking BDS code versions.

    """
    # status bit, most significant bit, least significant bit
    status = int(data[sb - 1])
    value = bin2int(data[msb - 1 : lsb])

    if not status:
        if value != 0:
            return True

    return False
