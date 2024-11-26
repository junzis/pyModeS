from typing import Optional

import numpy as np
from textwrap import wrap


def hex2bin(hexstr: str) -> str:
    """Convert a hexadecimal string to binary string, with zero fillings."""
    num_of_bits = len(hexstr) * 4
    binstr = bin(int(hexstr, 16))[2:].zfill(int(num_of_bits))
    return binstr


def hex2int(hexstr: str) -> int:
    """Convert a hexadecimal string to integer."""
    return int(hexstr, 16)


def bin2int(binstr: str) -> int:
    """Convert a binary string to integer."""
    return int(binstr, 2)


def bin2hex(binstr: str) -> str:
    """Convert a binary string to hexadecimal string."""
    return "{0:X}".format(int(binstr, 2))


def df(msg: str) -> int:
    """Decode Downlink Format value, bits 1 to 5."""
    dfbin = hex2bin(msg[:2])
    return min(bin2int(dfbin[0:5]), 24)


def crc(msg: str, encode: bool = False) -> int:
    """Mode-S Cyclic Redundancy Check.

    Detect if bit error occurs in the Mode-S message. When encode option is on,
    the checksum is generated.

    Args:
        msg: 28 bytes hexadecimal message string
        encode: True to encode the date only and return the checksum
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


def crc_legacy(msg: str, encode: bool = False) -> int:
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


def floor(x: float) -> int:
    """Mode-S floor function.

    Defined as the greatest integer value k, such that k <= x
    For example: floor(3.6) = 3 and floor(-3.6) = -4

    """
    return int(np.floor(x))


def icao(msg: str) -> Optional[str]:
    """Calculate the ICAO address from an Mode-S message.

    Applicable only with DF4, DF5, DF20, DF21 messages.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        String: ICAO address in 6 bytes hexadecimal string

    """
    addr: Optional[str]
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


def is_icao_assigned(icao: str) -> bool:
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


def typecode(msg: str) -> Optional[int]:
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


def cprNL(lat: float) -> int:
    """NL() function in CPR decoding."""

    if np.isclose(lat, 0):
        return 59
    elif np.isclose(abs(lat), 87):
        return 2
    elif lat > 87 or lat < -87:
        return 1

    nz = 15
    a = 1 - np.cos(np.pi / (2 * nz))
    b = np.cos(np.pi / 180 * abs(lat)) ** 2
    nl = 2 * np.pi / (np.arccos(1 - a / b))
    NL = floor(nl)
    return NL


def idcode(msg: str) -> str:
    """Compute identity code (squawk) encoded in DF5 or DF21 message.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        string: squawk code

    """
    if df(msg) not in [5, 21]:
        raise RuntimeError("Message must be Downlink Format 5 or 21.")

    mbin = hex2bin(msg)
    idcodebin = mbin[19:32]

    return squawk(idcodebin)


def squawk(binstr: str) -> str:
    """Decode 13 bits identity (squawk) code.

    Args:
        binstr (String): 13 bits binary string

    Returns:
        string: squawk code

    """
    if len(binstr) != 13 or not set(binstr).issubset(set("01")):
        raise RuntimeError("Input must be 13 bits binary string")

    C1 = binstr[0]
    A1 = binstr[1]
    C2 = binstr[2]
    A2 = binstr[3]
    C4 = binstr[4]
    A4 = binstr[5]
    # X = binstr[6]
    B1 = binstr[7]
    D1 = binstr[8]
    B2 = binstr[9]
    D2 = binstr[10]
    B4 = binstr[11]
    D4 = binstr[12]

    byte1 = int(A4 + A2 + A1, 2)
    byte2 = int(B4 + B2 + B1, 2)
    byte3 = int(C4 + C2 + C1, 2)
    byte4 = int(D4 + D2 + D1, 2)

    return str(byte1) + str(byte2) + str(byte3) + str(byte4)


def altcode(msg: str) -> Optional[int]:
    """Compute altitude encoded in DF4 or DF20 message.

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        int: altitude in ft

    """
    alt: Optional[int]

    if df(msg) not in [0, 4, 16, 20]:
        raise RuntimeError("Message must be Downlink Format 0, 4, 16, or 20.")

    # Altitude code, bit 20-32
    mbin = hex2bin(msg)

    altitude_code = mbin[19:32]

    alt = altitude(altitude_code)

    return alt


def altitude(binstr: str) -> Optional[int]:
    """Decode 13 bits altitude code.

    Args:
        binstr (String): 13 bits binary string

    Returns:
        int: altitude in ft

    """
    alt: Optional[int]

    if len(binstr) != 13 or not set(binstr).issubset(set("01")):
        raise RuntimeError("Input must be 13 bits binary string")

    Mbit = binstr[6]
    Qbit = binstr[8]

    if bin2int(binstr) == 0:
        # altitude unknown or invalid
        alt = None

    elif Mbit == "0":  # unit in ft
        if Qbit == "1":  # 25ft interval
            vbin = binstr[:6] + binstr[7] + binstr[9:]
            alt = bin2int(vbin) * 25 - 1000
        if Qbit == "0":  # 100ft interval, above 50187.5ft
            C1 = binstr[0]
            A1 = binstr[1]
            C2 = binstr[2]
            A2 = binstr[3]
            C4 = binstr[4]
            A4 = binstr[5]
            # M = binstr[6]
            B1 = binstr[7]
            # Q = binstr[8]
            B2 = binstr[9]
            D2 = binstr[10]
            B4 = binstr[11]
            D4 = binstr[12]

            graystr = D2 + D4 + A1 + A2 + A4 + B1 + B2 + B4 + C1 + C2 + C4
            alt = gray2alt(graystr)

    if Mbit == "1":  # unit in meter
        vbin = binstr[:6] + binstr[7:]
        alt = int(bin2int(vbin) * 3.28084)  # convert to ft

    return alt


def gray2alt(binstr: str) -> Optional[int]:
    gc500 = binstr[:8]
    n500 = gray2int(gc500)

    # in 100-ft step must be converted first
    gc100 = binstr[8:]
    n100 = gray2int(gc100)

    if n100 in [0, 5, 6]:
        return None

    if n100 == 7:
        n100 = 5

    if n500 % 2:
        n100 = 6 - n100

    alt = (n500 * 500 + n100 * 100) - 1300
    return alt


def gray2int(binstr: str) -> int:
    """Convert greycode to binary."""
    num = bin2int(binstr)
    num ^= num >> 8
    num ^= num >> 4
    num ^= num >> 2
    num ^= num >> 1
    return num


def data(msg: str) -> str:
    """Return the data frame in the message, bytes 9 to 22."""
    return msg[8:-6]


def allzeros(msg: str) -> bool:
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


def wrongstatus(data: str, sb: int, msb: int, lsb: int) -> bool:
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


def fs(msg):
    """Decode flight status for DF 4, 5, 20, and 21.

    Args:
        msg (str): 14 hexdigits string
    Returns:
        int, str: flight status, description

    """
    msgbin = hex2bin(msg)
    fs = bin2int(msgbin[5:8])
    text = None

    if fs == 0:
        text = "no alert, no SPI, aircraft is airborne"
    elif fs == 1:
        text = "no alert, no SPI, aircraft is on-ground"
    elif fs == 2:
        text = "alert, no SPI, aircraft is airborne"
    elif fs == 3:
        text = "alert, no SPI, aircraft is on-ground"
    elif fs == 4:
        text = "alert, SPI, aircraft is airborne or on-ground"
    elif fs == 5:
        text = "no alert, SPI, aircraft is airborne or on-ground"

    return fs, text


def dr(msg):
    """Decode downlink request for DF 4, 5, 20, and 21.

    Args:
        msg (str): 14 hexdigits string
    Returns:
        int, str: downlink request, description

    """
    msgbin = hex2bin(msg)
    dr = bin2int(msgbin[8:13])

    text = None

    if dr == 0:
        text = "no downlink request"
    elif dr == 1:
        text = "request to send Comm-B message"
    elif dr == 4:
        text = "Comm-B broadcast 1 available"
    elif dr == 5:
        text = "Comm-B broadcast 2 available"
    elif dr >= 16:
        text = "ELM downlink segments available: {}".format(dr - 15)

    return dr, text


def um(msg):
    """Decode utility message for DF 4, 5, 20, and 21.

    Utility message contains interrogator identifier and reservation type.

    Args:
        msg (str): 14 hexdigits string
    Returns:
        int, str: interrogator identifier code that triggered the reply, and
        reservation type made by the interrogator
    """
    msgbin = hex2bin(msg)
    iis = bin2int(msgbin[13:17])
    ids = bin2int(msgbin[17:19])
    if ids == 0:
        ids_text = None
    if ids == 1:
        ids_text = "Comm-B interrogator identifier code"
    if ids == 2:
        ids_text = "Comm-C interrogator identifier code"
    if ids == 3:
        ids_text = "Comm-D interrogator identifier code"
    return iis, ids, ids_text
