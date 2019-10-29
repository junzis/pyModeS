# cython: language_level=3

cimport cython

from .. cimport common


def category(bytes msg):
    """Aircraft category number

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: category number
    """

    cdef int tc = common.typecode(msg)
    if tc < 1 or tc > 4:
        raise RuntimeError("%s: Not a identification message" % msg)

    cdef bytearray msgbin = common.hex2bin(msg)
    mebin = msgbin[32:87]
    return common.bin2int(mebin[5:8])


def callsign(bytes msg):
    """Aircraft callsign

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        string: callsign
    """

    cdef int tc = common.typecode(msg)
    if tc < 1 or tc > 4:
        raise RuntimeError("%s: Not a identification message" % msg)

    cdef bytearray _chars = bytearray(
        b"#ABCDEFGHIJKLMNOPQRSTUVWXYZ#####_###############0123456789######"
    )
    cdef unsigned char[:] chars = _chars
    cdef bytearray msgbin = common.hex2bin(msg)
    cdef bytearray csbin = msgbin[40:96]

    cdef bytearray _cs = bytearray(8)
    cdef unsigned char[:] cs = _cs
    cs[0] = chars[common.bin2int(csbin[0:6])]
    cs[1] = chars[common.bin2int(csbin[6:12])]
    cs[2] = chars[common.bin2int(csbin[12:18])]
    cs[3] = chars[common.bin2int(csbin[18:24])]
    cs[4] = chars[common.bin2int(csbin[24:30])]
    cs[5] = chars[common.bin2int(csbin[30:36])]
    cs[6] = chars[common.bin2int(csbin[36:42])]
    cs[7] = chars[common.bin2int(csbin[42:48])]

    # clean string, remove spaces and marks, if any.
    # cs = cs.replace('_', '')
    return _cs.decode().replace("#", "")
