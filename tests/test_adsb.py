"""Tests for pymodes.decoder.adsb — ADSB class dispatch for DF17/18."""

from pymodes import decode


class TestAdsbDispatchIdentification:
    def test_df17_identification_full_decode(self):
        # Golden from v2 test_adsb_*: TC=4 identification
        result = decode("8D406B902015A678D4D220AA4BDA")
        assert result["df"] == 17
        assert result["icao"] == "406B90"
        assert result["typecode"] == 4
        assert result["bds"] == "0,8"
        assert result["callsign"] == "EZY85MH"
        assert result["category"] == 0

    def test_df18_routes_to_same_dispatch(self):
        # DF18 (non-transponder ADS-B) uses the same ME field layout.
        # Construct a synthetic DF18 by flipping the DF bits of the
        # TC=4 golden (DF17=10001, DF18=10010 → byte 0 becomes 0x90).
        result = decode("90406B902015A678D4D220AA4BDA")
        assert result["df"] == 18
        assert result["typecode"] == 4
        assert result["bds"] == "0,8"

    def test_unknown_typecode_returns_typecode_only(self):
        # TC=0 is "No position information, no ID" — not in the
        # dispatch table. The ADSB class returns just {typecode: 0}
        # so the Decoded dict has df + icao + crc_valid + typecode
        # but NO `bds` key and no BDS fields.
        from pymodes._bits import crc_remainder

        n = int("8D406B902015A678D4D220AA4BDA", 16)
        # ME starts at message bit 32. TC is bits 32-36 (MSB-first).
        # In LSB terms for a 112-bit message, TC occupies bits 75-79.
        tc_mask = 0x1F << (112 - 32 - 5)
        n &= ~tc_mask
        # Rebuild CRC so crc_valid stays True
        n_no_parity = n & ~0xFFFFFF
        n_no_parity |= crc_remainder(n_no_parity, 112)
        msg = f"{n_no_parity:028X}"
        result = decode(msg)
        assert result["df"] == 17
        assert result["typecode"] == 0
        assert "bds" not in result
        assert "callsign" not in result
