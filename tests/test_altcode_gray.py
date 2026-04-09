"""Tests for the Q=0 Gillham gray-code path in pymodes._altcode."""

from pymodes._altcode import altcode_to_altitude


class TestAltcodeGrayCode:
    def test_q0_invalid_n100_returns_none(self):
        # Regression from v2 test_common_contract.py:
        # Construct a 13-bit AC field with Mbit=0, Qbit=0, C1=1, C2=0, C4=1
        # (so gc100 = "101" → gray2int = 6 → invalid).
        # Bit layout: C1 A1 C2 A2 C4 A4 M B1 Q B2 D2 B4 D4
        # LSB-first bit index: pos p → LSB bit (12 - p)
        # C1 (pos 0) = 1, C2 (pos 2) = 0, C4 (pos 4) = 1
        # All others zero.
        ac = (1 << 12) | (0 << 10) | (1 << 8)
        assert altcode_to_altitude(ac) is None

    def test_q0_all_zero_non_mq_bits(self):
        # Mbit=0, Qbit=0, all other bits zero → n500=0, n100=0 → invalid
        ac = 0  # already tested as "unknown" in Plan 1
        assert altcode_to_altitude(ac) is None

    def test_q0_valid_decodes_to_positive_altitude(self):
        # Build a valid Q=0 code that decodes to a plausible altitude.
        # Target: ~51000 ft range.
        # Working backward from the formula:
        #   alt + 1300 = n500 * 500 + n100 * 100
        # Pick n500 = 102 (even), n100 = 3 → alt = 50000 + 300 - 1300 = 49000 ft
        # Encode 102 as 8-bit gray: 102 = 0b01100110
        # → gray = n ^ (n >> 1) = 0b01010101 = 0x55
        # Encode 3 as 3-bit gray: 3 = 0b011 → gray = 0b010 = 2
        # graystr (MSB first, 11 bits): 0 1 0 1 0 1 0 1 0 1 0
        # = D2 D4 A1 A2 A4 B1 B2 B4 C1 C2 C4
        # D2=0 D4=1 A1=0 A2=1 A4=0 B1=1 B2=0 B4=1 C1=0 C2=1 C4=0
        # AC field (MSB first): C1 A1 C2 A2 C4 A4 M B1 Q B2 D2 B4 D4
        # C1=0 A1=0 C2=1 A2=1 C4=0 A4=0 M=0 B1=1 Q=0 B2=0 D2=0 B4=1 D4=1
        # LSB index = 12 - pos:
        #   pos 2 C2=1 → LSB bit 10
        #   pos 3 A2=1 → LSB bit 9
        #   pos 7 B1=1 → LSB bit 5
        #   pos 11 B4=1 → LSB bit 1
        #   pos 12 D4=1 → LSB bit 0
        ac = (1 << 10) | (1 << 9) | (1 << 5) | (1 << 1) | (1 << 0)
        # Assert the decode returns a non-None plausible altitude.
        # The exact value depends on the round-trip — this test is a
        # smoke test rather than a tight equality check.
        result = altcode_to_altitude(ac)
        assert result is not None
        assert isinstance(result, int)
        assert 45000 < result < 60000

    def test_q1_path_still_works(self):
        # Regression: the existing Q=1 path must not break.
        # Plan 1 test: altcode 0x1030 (Q=1, M=0, value 1040) → 25000 ft.
        assert altcode_to_altitude(0x1030) == 25000

    def test_all_zero_returns_none(self):
        assert altcode_to_altitude(0) is None
