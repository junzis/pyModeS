"""Tests for pymodes._callsign 6-bit-per-char callsign decoder."""

from pymodes._callsign import decode_callsign, is_valid_callsign_char


class TestDecodeCallsign:
    def test_ezy85mh(self):
        # From v2 test_adsb_callsign:
        # msg = "8D406B902015A678D4D220AA4BDA"
        # ME = msg[8:22] = "2015A678D4D220" (56-bit field: TC[5] | CA[3] | cs[48])
        # Callsign occupies the lower 48 bits of ME (bits 8-55 in 1-indexed notation).
        # Leading and trailing whitespace is stripped.
        me = 0x2015A678D4D220
        cs_bits = me & ((1 << 48) - 1)  # lower 48 bits of the 56-bit ME
        assert decode_callsign(cs_bits) == "EZY85MH"

    def test_empty_field_returns_empty(self):
        # All-zero 48-bit field decodes to 8 '#' chars. '#' is NOT
        # whitespace, so .strip() leaves them in place — but the caller
        # (the validator) will reject such MBs upstream. This test just
        # pins the raw behaviour.
        assert decode_callsign(0) == "########"

    def test_all_spaces_strips_to_empty(self):
        # Index 32 is ASCII space. Eight spaces .strip() to "".
        spaces = (
            (32 << 42)
            | (32 << 36)
            | (32 << 30)
            | (32 << 24)
            | (32 << 18)
            | (32 << 12)
            | (32 << 6)
            | 32
        )
        assert decode_callsign(spaces) == ""

    def test_partial_fill_strips_trailing_spaces(self):
        # "AB123" followed by three trailing spaces — the three trailing
        # spaces (index 32) are stripped by .strip().
        def encode_cs(chars: str) -> int:
            # Local encoder: uses the ASCII rules inverse.
            # A-Z -> idx = ord(c) & 0x3F (i.e. ord - 0x40)
            # 0-9 -> idx = ord(c) (0x30-0x39)
            # ' ' -> idx = 32
            result = 0
            for c in chars.ljust(8, " "):
                if "A" <= c <= "Z":
                    idx = ord(c) & 0x3F
                elif "0" <= c <= "9":
                    idx = ord(c)
                elif c == " ":
                    idx = 32
                else:
                    raise ValueError(f"unencodable char {c!r}")
                result = (result << 6) | idx
            return result

        bits = encode_cs("AB123")
        assert decode_callsign(bits) == "AB123"

    def test_leading_whitespace_also_stripped(self):
        # .strip() removes leading whitespace too. A payload of
        # "   AB123 " (index 32 x3, A, B, 1, 2, 3, ' ') should return
        # "AB123".
        cs = 0
        for idx in (32, 32, 32, 1, 2, 0x31, 0x32, 0x33):
            cs = (cs << 6) | idx
        assert decode_callsign(cs) == "AB123"


class TestIsValidCallsignChar:
    def test_letters_valid(self):
        for i in range(1, 27):
            assert is_valid_callsign_char(i) is True

    def test_space_valid(self):
        assert is_valid_callsign_char(32) is True

    def test_digits_valid(self):
        for i in range(48, 58):
            assert is_valid_callsign_char(i) is True

    def test_zero_invalid(self):
        assert is_valid_callsign_char(0) is False

    def test_mid_range_invalid(self):
        for i in (27, 28, 29, 30, 31, 33, 34, 35, 36, 47):
            assert is_valid_callsign_char(i) is False

    def test_high_range_invalid(self):
        for i in range(58, 64):
            assert is_valid_callsign_char(i) is False
