"""Tests for pymodes._bits bit-extraction primitives."""

from pymodes._bits import crc_remainder, extract_field, extract_signed


class TestExtractField:
    def test_first_bit_set(self):
        # 8-bit value 0b10000000 = 0x80; top bit extracted as width=1 should be 1
        assert extract_field(0x80, 0, 1, 8) == 1

    def test_first_bit_clear(self):
        assert extract_field(0x00, 0, 1, 8) == 0

    def test_last_bit(self):
        # 8-bit value 0b00000001 = 0x01; bottom bit at start=7 should be 1
        assert extract_field(0x01, 7, 1, 8) == 1

    def test_full_byte(self):
        # 8-bit 0x8D is 10001101 — extract the full 8 bits
        assert extract_field(0x8D, 0, 8, 8) == 0x8D

    def test_df_extraction(self):
        # DF is bits 0-4 (top 5 bits) of a 112-bit message
        # 0x8D406B90... starts with 10001101, so top 5 bits are 10001 = 17
        msg = int("8D406B902015A678D4D220AA4BDA", 16)
        assert extract_field(msg, 0, 5, 112) == 17

    def test_icao_extraction(self):
        # ICAO is bits 8-31 (24 bits) of a DF17 message
        msg = int("8D406B902015A678D4D220AA4BDA", 16)
        assert extract_field(msg, 8, 24, 112) == 0x406B90

    def test_typecode_extraction(self):
        # TC is bits 32-36 (5 bits) — first 5 bits of the ME field
        msg = int("8D406B902015A678D4D220AA4BDA", 16)
        # Byte 4 of the message is 0x20 = 00100000 → first 5 bits are 00100 = 4
        assert extract_field(msg, 32, 5, 112) == 4

    def test_wide_field_near_end(self):
        # 14-bit value spanning most of a 56-bit short message
        # Value 0x12345 = 0b0001_0010_0011_0100_0101 (20 bits)
        # Place at position 10, width 20, total 56
        n = 0x12345 << (56 - 10 - 20)  # shift to position 10
        assert extract_field(n, 10, 20, 56) == 0x12345

    def test_zero_field(self):
        assert extract_field(0, 0, 5, 112) == 0

    def test_all_ones_field(self):
        # 5 bits all set to 1 = 0b11111 = 31
        n = 0b11111 << (112 - 5)  # shift to position 0
        assert extract_field(n, 0, 5, 112) == 31


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
