"""Tests for pymodes._callsign 6-bit-per-char callsign decoder."""

from pymodes._callsign import decode_callsign


class TestDecodeCallsign:
    def test_ezy85mh(self):
        # From v2 test_adsb_callsign:
        # msg = "8D406B902015A678D4D220AA4BDA"
        # ME = msg[8:22] = "2015A678D4D220" (56-bit field: TC[5] | CA[3] | cs[48])
        # Callsign occupies the lower 48 bits of ME (bits 8-55 in 1-indexed notation).
        me = 0x2015A678D4D220
        cs_bits = me & ((1 << 48) - 1)  # lower 48 bits of the 56-bit ME
        assert decode_callsign(cs_bits) == "EZY85MH_"

    def test_strips_hash_padding(self):
        # All-zero 48-bit field decodes to 8 '#' chars which are stripped
        # by the helper (spec: "#" means unused slot).
        assert decode_callsign(0) == ""

    def test_preserves_underscore(self):
        # The v2 callsign function replaces "#" with "" but keeps "_"
        # (the character set has "_" at index 32, representing space).
        underscores = (
            (32 << 42)
            | (32 << 36)
            | (32 << 30)
            | (32 << 24)
            | (32 << 18)
            | (32 << 12)
            | (32 << 6)
            | 32
        )
        assert decode_callsign(underscores) == "________"

    def test_partial_fill(self):
        # "AB123___" — 3 chars then spaces
        def encode_cs(chars: str) -> int:
            table = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ#####_###############0123456789######"
            result = 0
            for c in chars.ljust(8, "_"):
                result = (result << 6) | table.index(c)
            return result

        bits = encode_cs("AB123")
        assert decode_callsign(bits) == "AB123___"
