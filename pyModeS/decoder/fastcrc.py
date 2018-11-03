GENERATOR = [int("11111111", 2), int("11111010", 2), int("00000100", 2), int("10000000", 2)]


class BytesWrapper:

    def __init__(self, hex: str):
        if len(hex) % 2 == 1:
            hex += '0'

        self._bytes = [b for b in bytes.fromhex(hex)]

    def byte_count(self) -> int:
        return len(self._bytes) - 3

    def get_bit(self, byte_index, bit_index):
        mask = 0x80 >> bit_index
        bits = self._bytes[byte_index] & mask
        return 0 if bits == 0 else 1

    def apply_matrix(self, byte_index, bit_index):
        self._bytes[byte_index] = self._bytes[byte_index] ^ (GENERATOR[0] >> bit_index)
        self._bytes[byte_index + 1] = self._bytes[byte_index + 1] ^ \
                                      (0xFF & ((GENERATOR[0] << 8 - bit_index) | (GENERATOR[1] >> bit_index)))
        self._bytes[byte_index + 2] = self._bytes[byte_index + 2] ^ \
                                      (0xFF & ((GENERATOR[1] << 8 - bit_index) | (GENERATOR[2] >> bit_index)))
        self._bytes[byte_index + 3] = self._bytes[byte_index + 3] ^ \
                                      (0xFF & ((GENERATOR[2] << 8 - bit_index) | (GENERATOR[3] >> bit_index)))

    def get_suffix(self) -> int:
        return (self._bytes[-3] << 16) | (self._bytes[-2] << 8) | self._bytes[-1]


def crc(msg: str) -> int:
    msgbin = BytesWrapper(msg)

    for byte_index in range(msgbin.byte_count()):
        for bit_index in range(8):
            b = msgbin.get_bit(byte_index, bit_index)

            if b == 1:
                msgbin.apply_matrix(byte_index, bit_index)

    result = msgbin.get_suffix()

    return result
