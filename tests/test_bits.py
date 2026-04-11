"""Tests for pyModeS._bits bit-extraction primitives."""

from pyModeS._altcode import altcode_to_altitude
from pyModeS._bits import crc_remainder, extract_signed, extract_unsigned
from pyModeS._idcode import idcode_to_squawk


class TestExtractUnsigned:
    def test_first_bit_set(self):
        # 8-bit value 0b10000000 = 0x80; top bit extracted as width=1 should be 1
        assert extract_unsigned(0x80, 0, 1, 8) == 1

    def test_first_bit_clear(self):
        assert extract_unsigned(0x00, 0, 1, 8) == 0

    def test_last_bit(self):
        # 8-bit value 0b00000001 = 0x01; bottom bit at start=7 should be 1
        assert extract_unsigned(0x01, 7, 1, 8) == 1

    def test_full_byte(self):
        # 8-bit 0x8D is 10001101 — extract the full 8 bits
        assert extract_unsigned(0x8D, 0, 8, 8) == 0x8D

    def test_df_extraction(self):
        # DF is bits 0-4 (top 5 bits) of a 112-bit message
        # 0x8D406B90... starts with 10001101, so top 5 bits are 10001 = 17
        msg = int("8D406B902015A678D4D220AA4BDA", 16)
        assert extract_unsigned(msg, 0, 5, 112) == 17

    def test_icao_extraction(self):
        # ICAO is bits 8-31 (24 bits) of a DF17 message
        msg = int("8D406B902015A678D4D220AA4BDA", 16)
        assert extract_unsigned(msg, 8, 24, 112) == 0x406B90

    def test_typecode_extraction(self):
        # TC is bits 32-36 (5 bits) — first 5 bits of the ME field
        msg = int("8D406B902015A678D4D220AA4BDA", 16)
        # Byte 4 of the message is 0x20 = 00100000 → first 5 bits are 00100 = 4
        assert extract_unsigned(msg, 32, 5, 112) == 4

    def test_wide_field_near_end(self):
        # 14-bit value spanning most of a 56-bit short message
        # Value 0x12345 = 0b0001_0010_0011_0100_0101 (20 bits)
        # Place at position 10, width 20, total 56
        n = 0x12345 << (56 - 10 - 20)  # shift to position 10
        assert extract_unsigned(n, 10, 20, 56) == 0x12345

    def test_zero_field(self):
        assert extract_unsigned(0, 0, 5, 112) == 0

    def test_all_ones_field(self):
        # 5 bits all set to 1 = 0b11111 = 31
        n = 0b11111 << (112 - 5)  # shift to position 0
        assert extract_unsigned(n, 0, 5, 112) == 31


class TestExtractSigned:
    def test_positive_small(self):
        # 8-bit value 5 with sign bit clear
        assert extract_signed(0b0101, 4, 4, 8) == 5

    def test_negative_from_twos_complement(self):
        # 4-bit value -3 in two's complement = 0b1101 = 13
        assert extract_signed(0b1101, 4, 4, 8) == -3

    def test_negative_boundary(self):
        # 4-bit value -8 = 0b1000 (MSB set, all others clear)
        assert extract_signed(0b1000, 4, 4, 8) == -8

    def test_positive_boundary(self):
        # 4-bit value +7 = 0b0111
        assert extract_signed(0b0111, 4, 4, 8) == 7

    def test_zero(self):
        assert extract_signed(0, 4, 4, 8) == 0

    def test_9bit_signed_roll_angle(self):
        # BDS 5,0 roll angle is a 9-bit signed field
        # -180 encoded as two's complement in 9 bits: 2^9 - 180 = 332 = 0b101001100
        n = 0b101001100 << (56 - 1 - 9)  # place at position 1
        assert extract_signed(n, 1, 9, 56) == -180


class TestCrcRemainder:
    def test_valid_df17_message(self):
        # Known valid DF17 messages from pyModeS v2 test corpus
        # These have CRC remainder 0 when computed correctly
        valid_msgs = [
            "8D406B902015A678D4D220AA4BDA",
            "8d8960ed58bf053cf11bc5932b7d",
            "8d45cab390c39509496ca9a32912",
            "8d74802958c904e6ef4ba0184d5c",
        ]
        for msg in valid_msgs:
            n = int(msg, 16)
            assert crc_remainder(n, 112) == 0, f"non-zero CRC for {msg}"

    def test_invalid_df17_has_nonzero_remainder(self):
        # Flip one bit in a known-valid message; CRC must become non-zero
        n = int("8D406B902015A678D4D220AA4BDA", 16)
        n_corrupted = n ^ (1 << 50)  # flip bit 50 (arbitrary middle bit)
        assert crc_remainder(n_corrupted, 112) != 0

    def test_df20_icao_encoded_in_crc(self):
        # For DF20/21, CRC remainder equals the ICAO address when valid
        # These are known DF20 messages from v2 test corpus
        # Format: (hex_message, expected_icao_int)
        cases = [
            ("a000029cffbaa11e2004727281f1", 0x4243D0),
            ("a000139381951536e024d4ccf6b5", 0x3C4DD2),
        ]
        for msg, expected_icao in cases:
            n = int(msg, 16)
            assert crc_remainder(n, 112) == expected_icao

    def test_short_message_56bit(self):
        # A 56-bit (short) Mode-S message can also have CRC computed
        # Construct DF11 (all-call reply) with known ICAO 406B90
        # DF=11 (5 bits), CA=5 (3 bits), AA=406B90 (24 bits), PI=24 bits
        # PI = CRC computed over DF+CA+AA
        # Build a synthetic: 5D406B90 followed by the correct parity
        df_ca_aa = 0x5D406B90 << 24  # shift left to make room for PI
        pi = crc_remainder(df_ca_aa, 56)
        full = df_ca_aa | pi
        # Recomputing over the full message should give 0
        assert crc_remainder(full, 56) == 0


class TestAltCodeDecode:
    def test_altcode_all_zero_returns_none(self):
        # All-zero altitude code means "altitude unknown or invalid"
        assert altcode_to_altitude(0) is None

    def test_altcode_25ft_interval(self):
        # Q=1, 25-ft interval. AC = 0x1030 should decode to 25000 ft.
        # Working: AC bits = 1_0000_0011_0000 (pos 0..12 MSB-first)
        # M (pos 6) = 0, Q (pos 8) = 1, so Q=1 path
        # 11 non-M non-Q bits in order (pos 0,1,2,3,4,5,7,9,10,11,12):
        # 1,0,0,0,0,0,1,0,0,0,0 = 0b10000010000 = 1040
        # altitude = 1040 * 25 - 1000 = 25000
        assert altcode_to_altitude(0x1030) == 25000

    def test_altcode_q1_zero_value(self):
        # Q=1, 11-bit value = 0 → altitude = 0*25 - 1000 = -1000 ft
        # Q is at position 8 (MSB-first), LSB index = 12 - 8 = 4
        # AC = 1 << 4 = 0x0010 (only the Q bit set, all data bits zero)
        assert altcode_to_altitude(0x0010) == -1000

    def test_altcode_100ft_gray_code_placeholder(self):
        # Q=0 path uses Gillham gray code. Phase 1 returns None for
        # Q=0 cases — full gray code support is deferred to phase 5.
        # All-zero is handled by the "unknown" check, not the Q=0 path.
        # So we test a non-zero Q=0 value.
        # AC = 0b0000001000000 (M=0, Q=0, B1=1) = 0x0040
        result = altcode_to_altitude(0x0040)
        # Phase 1 placeholder: returns None for Q=0
        assert result is None


class TestIdCodeDecode:
    def test_idcode_zero(self):
        assert idcode_to_squawk(0) == "0000"

    def test_idcode_7777(self):
        # All-ones squawk. For 7777: all A/B/C/D pulse bits set, X=0.
        # Bit positions in the 13-bit ID field (MSB-first):
        #   C1(0) A1(1) C2(2) A2(3) C4(4) A4(5) X(6)
        #   B1(7) D1(8) B2(9) D2(10) B4(11) D4(12)
        # 1111110111111 = 0x1FBF
        assert idcode_to_squawk(0x1FBF) == "7777"

    def test_idcode_1200(self):
        # Squawk 1200 — VFR code in the US.
        # A=1 (A4 A2 A1 = 0 0 1), B=2 (B4 B2 B1 = 0 1 0), C=0, D=0
        # Bit positions:
        #   C1(0)=0 A1(1)=1 C2(2)=0 A2(3)=0 C4(4)=0 A4(5)=0 X(6)=0
        #   B1(7)=0 D1(8)=0 B2(9)=1 D2(10)=0 B4(11)=0 D4(12)=0
        # = 0b0100000001000 = 0x0808
        assert idcode_to_squawk(0x0808) == "1200"

    def test_idcode_7500(self):
        # Squawk 7500 — unlawful-interference (hijack) code.
        # A=7 (1 1 1), B=5 (1 0 1), C=0, D=0
        # Bit positions:
        #   C1(0)=0 A1(1)=1 C2(2)=0 A2(3)=1 C4(4)=0 A4(5)=1 X(6)=0
        #   B1(7)=1 D1(8)=0 B2(9)=0 D2(10)=0 B4(11)=1 D4(12)=0
        # = 0b0101010100010 = 0x0AA2
        assert idcode_to_squawk(0x0AA2) == "7500"
