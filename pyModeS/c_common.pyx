# cython: language_level=3

cimport cython
from cpython cimport array
from cpython.bytes cimport PyBytes_GET_SIZE
from cpython.bytearray cimport PyByteArray_GET_SIZE

from libc.math cimport abs, cos, acos, fabs, M_PI as pi, floor as c_floor


cdef int char_to_int(unsigned char binstr):
    if 48 <= binstr <= 57:  # 0 to 9
        return binstr - 48
    if 97 <= binstr <= 102: # a to f
        return binstr - 97 + 10
    if 65 <= binstr <= 70: # A to F
        return binstr - 65 + 10
    return 0

cdef unsigned char int_to_char(unsigned char i):
    if i < 10:
        return 48 + i  # "0" + i
    return 97 - 10 + i  # "a" - 10 + i

@cython.boundscheck(False)
@cython.overflowcheck(False)
cpdef str hex2bin(str hexstr):
    """Convert a hexadecimal string to binary string, with zero fillings."""
    # num_of_bits = len(hexstr) * 4
    cdef hexbytes = bytes(hexstr.encode())
    cdef Py_ssize_t len_hexstr = PyBytes_GET_SIZE(hexbytes)
    # binstr = bin(int(hexbytes, 16))[2:].zfill(int(num_of_bits))
    cdef bytearray _binstr = bytearray(4 * len_hexstr)
    cdef unsigned char[:] binstr = _binstr
    cdef unsigned char int_
    cdef Py_ssize_t i
    for i in range(len_hexstr):
        int_ = char_to_int(hexbytes[i])
        binstr[4*i] = int_to_char((int_  >> 3) & 1)
        binstr[4*i+1] = int_to_char((int_ >> 2) & 1)
        binstr[4*i+2] = int_to_char((int_ >> 1) & 1)
        binstr[4*i+3] = int_to_char((int_) & 1)
    return _binstr.decode()

@cython.boundscheck(False)
cpdef long bin2int(str binstr):
    """Convert a binary string to integer."""
    # return int(binstr, 2)
    cdef bytearray binbytes = bytearray(binstr.encode())
    cdef Py_ssize_t len_ = PyByteArray_GET_SIZE(binbytes)
    cdef long cumul = 0
    cdef unsigned char[:] v_binstr = binbytes
    for i in range(len_):
        cumul = 2*cumul + char_to_int(v_binstr[i])
    return cumul

@cython.boundscheck(False)
cpdef long hex2int(str hexstr):
    """Convert a binary string to integer."""
    # return int(hexstr, 2)
    cdef bytearray binbytes = bytearray(hexstr.encode())
    cdef Py_ssize_t len_ = PyByteArray_GET_SIZE(binbytes)
    cdef long cumul = 0
    cdef unsigned char[:] v_hexstr = binbytes
    for i in range(len_):
        cumul = 16*cumul + char_to_int(v_hexstr[i])
    return cumul

@cython.boundscheck(False)
cpdef str bin2hex(str binstr):
    return "{0:X}".format(int(binstr, 2))


@cython.boundscheck(False)
cpdef unsigned char df(str msg):
    """Decode Downlink Format value, bits 1 to 5."""
    cdef str dfbin = hex2bin(msg[:2])
    # return min(bin2int(dfbin[0:5]), 24)
    cdef long df = bin2int(dfbin[0:5])
    if df > 24:
        return 24
    return df

# the CRC generator
# G = [int("11111111", 2), int("11111010", 2), int("00000100", 2), int("10000000", 2)]
cdef array.array _G = array.array('l', [0b11111111, 0b11111010, 0b00000100, 0b10000000])

@cython.boundscheck(False)
@cython.wraparound(False)
cpdef long crc(str msg, bint encode=False):
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
    # G = [int("11111111", 2), int("11111010", 2), int("00000100", 2), int("10000000", 2)]
    # cdef array.array _G = array.array('l', [0b11111111, 0b11111010, 0b00000100, 0b10000000])
    cdef long[4] G = _G

    # msgbin_split = wrap(msgbin, 8)
    # mbytes = list(map(bin2int, msgbin_split))
    cdef bytearray _msgbin = bytearray(hex2bin(msg).encode())
    cdef unsigned char[:] msgbin = _msgbin

    cdef Py_ssize_t len_msgbin = PyByteArray_GET_SIZE(_msgbin)
    cdef Py_ssize_t len_mbytes = len_msgbin // 8
    cdef Py_ssize_t i

    if encode:
        for i in range(len_msgbin - 24, len_msgbin):
            msgbin[i] = 0

    cdef array.array _mbytes = array.array(
        'l', [bin2int(_msgbin[8*i:8*i+8].decode()) for i in range(len_mbytes)]
    )

    cdef long[:] mbytes = _mbytes

    cdef long bits, mask
    cdef Py_ssize_t ibyte, ibit

    for ibyte in range(len_mbytes - 3):
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

    cdef long result = (mbytes[len_mbytes-3] << 16) | (mbytes[len_mbytes-2] << 8) | mbytes[len_mbytes-1]

    return result



cpdef long floor(double x):
    """Mode-S floor function.

    Defined as the greatest integer value k, such that k <= x
    For example: floor(3.6) = 3 and floor(-3.6) = -4

    """
    return <long> c_floor(x)

cpdef str icao(str msg):
    """Calculate the ICAO address from an Mode-S message."""
    cdef unsigned char DF = df(msg)
    cdef long c0, c1

    if DF in (11, 17, 18):
        addr = msg[2:8]
    elif DF in (0, 4, 5, 16, 20, 21):
        c0 = crc(msg, encode=True)
        c1 = hex2int(msg[-6:])
        addr = "%06X" % (c0 ^ c1)
    else:
        addr = None

    return addr


cpdef bint is_icao_assigned(str icao):
    """Check whether the ICAO address is assigned (Annex 10, Vol 3)."""
    if (icao is None) or (not isinstance(icao, str)) or (len(icao) != 6):
        return False

    cdef long icaoint = hex2int(icao)

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

@cython.boundscheck(False)
@cython.wraparound(False)
cpdef int typecode(str msg):
    """Type code of ADS-B message"""
    if df(msg) not in (17, 18):
        return -1
        # return None

    cdef str tcbin = hex2bin(msg[8:10])
    return bin2int(tcbin[0:5])

@cython.cdivision(True)
cpdef int cprNL(double lat):
    """NL() function in CPR decoding."""

    if abs(lat) <= 1e-08:
        return 59
    elif abs(abs(lat) - 87) <= 1e-08 + 1e-05 * 87:
        return 2
    elif lat > 87 or lat < -87:
        return 1

    cdef int nz = 15
    cdef double a = 1 - cos(pi / (2 * nz))
    cdef double b = cos(pi / 180 * fabs(lat)) ** 2
    cdef double nl = 2 * pi / (acos(1 - a / b))
    NL = floor(nl)
    return NL

@cython.boundscheck(False)
@cython.wraparound(False)
cpdef str idcode(str msg):
    """Compute identity (squawk code)."""
    if df(msg) not in [5, 21]:
        raise RuntimeError("Message must be Downlink Format 5 or 21.")

    squawk_code = squawk(hex2bin(msg)[19:32])
    return squawk_code


@cython.boundscheck(False)
@cython.wraparound(False)
cpdef str squawk(str binstr):
    """Compute identity (squawk code)."""

    if len(binstr) != 13 or set(binstr) != set('01'):
        raise RuntimeError("Input must be 13 bits binary string")

    cdef bytearray _mbin = bytearray(binstr.encode())
    cdef unsigned char[:] mbin = _mbin

    cdef bytearray _idcode = bytearray(4)
    cdef unsigned char[:] idcode = _idcode

    cdef unsigned char C1 = mbin[0]
    cdef unsigned char A1 = mbin[1]
    cdef unsigned char C2 = mbin[2]
    cdef unsigned char A2 = mbin[3]
    cdef unsigned char C4 = mbin[4]
    cdef unsigned char A4 = mbin[5]
    # X = mbin[6]
    cdef unsigned char B1 = mbin[7]
    cdef unsigned char D1 = mbin[8]
    cdef unsigned char B2 = mbin[9]
    cdef unsigned char D2 = mbin[10]
    cdef unsigned char B4 = mbin[11]
    cdef unsigned char D4 = mbin[12]

    idcode[0] = int_to_char((char_to_int(A4)*2 + char_to_int(A2))*2 + char_to_int(A1))
    idcode[1] = int_to_char((char_to_int(B4)*2 + char_to_int(B2))*2 + char_to_int(B1))
    idcode[2] = int_to_char((char_to_int(C4)*2 + char_to_int(C2))*2 + char_to_int(C1))
    idcode[3] = int_to_char((char_to_int(D4)*2 + char_to_int(D2))*2 + char_to_int(D1))

    return _idcode.decode()


@cython.boundscheck(False)
@cython.wraparound(False)
cpdef int altcode(str msg):
    """Compute the altitude."""
    if df(msg) not in [0, 4, 16, 20]:
        raise RuntimeError("Message must be Downlink Format 0, 4, 16, or 20.")

    alt = altitude(hex2bin(msg)[19:32])
    return alt


@cython.boundscheck(False)
@cython.wraparound(False)
cpdef int altitude(str binstr):

    if len(binstr) != 13 or not set(binstr).issubset(set("01")):
        raise RuntimeError("Input must be 13 bits binary string")

    cdef bytearray _mbin = bytearray(binstr.encode())
    cdef unsigned char[:] mbin = _mbin

    cdef char Mbit = binstr[6]
    cdef char Qbit = binstr[8]

    cdef int alt = 0
    cdef bytearray vbin
    cdef bytearray _graybytes = bytearray(11)
    cdef unsigned char[:] graybytes = _graybytes

    if bin2int(binstr) == 0:
        # altitude unknown or invalid
        alt = -9999

    elif Mbit == 48:  # unit in ft, "0" -> 48
        if Qbit == 49:  # 25ft interval, "1" -> 49
            vbin = _mbin[:6] + _mbin[7:8] + _mbin[9:]
            alt = bin2int(vbin.decode()) * 25 - 1000
        if Qbit == 48:  # 100ft interval, above 50175ft, "0" -> 48
            graybytes[8] = mbin[0]
            graybytes[2] = mbin[1]
            graybytes[9] = mbin[2]
            graybytes[3] = mbin[3]
            graybytes[10] = mbin[4]
            graybytes[4] = mbin[5]
            # M = mbin[6]
            graybytes[5] = mbin[7]
            # Q = mbin[8]
            graybytes[6] = mbin[9]
            graybytes[0] = mbin[10]
            graybytes[7] = mbin[11]
            graybytes[1] = mbin[12]

            alt = gray2alt(_graybytes.decode())

    elif Mbit == 49:  # unit in meter, "1" -> 49
        vbin = _mbin[:6] + _mbin[7:]
        alt = int(bin2int(vbin.decode()) * 3.28084)  # convert to ft

    return alt


cpdef int gray2alt(str codestr):
    cdef str gc500 = codestr[:8]
    cdef int n500 = gray2int(gc500)

    # in 100-ft step must be converted first
    cdef str gc100 = codestr[8:]
    cdef int n100 = gray2int(gc100)

    if n100 in [0, 5, 6]:
        return -1
        #return None

    if n100 == 7:
        n100 = 5

    if n500 % 2:
        n100 = 6 - n100

    alt = (n500 * 500 + n100 * 100) - 1300
    return alt


cdef int gray2int(str graystr):
    """Convert greycode to binary."""
    cdef int num = bin2int(graystr)
    num ^= num >> 8
    num ^= num >> 4
    num ^= num >> 2
    num ^= num >> 1
    return num


cpdef str data(str msg):
    """Return the data frame in the message, bytes 9 to 22."""
    return msg[8:-6]


cpdef bint allzeros(str msg):
    """Check if the data bits are all zeros."""
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
