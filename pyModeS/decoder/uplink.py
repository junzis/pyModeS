from pyModeS import common


def uplink_icao(msg):
    """Calculate the ICAO address from a Mode-S interrogation (uplink message)"""
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


def uf(msg):
    """Decode Uplink Format value, bits 1 to 5."""
    ufbin = common.hex2bin(msg[:2])
    return min(common.bin2int(ufbin[0:5]), 24)
