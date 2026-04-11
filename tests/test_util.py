"""Tests for the public :mod:`pyModeS.util` helpers.

Every function in ``pyModeS.util`` is a thin wrapper around a
primitive in ``_bits.py`` / ``_altcode.py`` / ``_idcode.py`` /
``position/_cpr.py``. The primitives themselves already have
extensive unit tests. This file's job is to verify the public
wrapper surface:

1. That the signatures are stable and return the shapes users
   expect (strings, ints, Optionals).
2. That messages from the golden tests/data corpus feed through
   the helpers consistently with what :func:`pyModeS.decode`
   reports on the same input.
3. That bit-position arithmetic (``altcode``, ``idcode``) agrees
   with the full-message decoders.
"""

from __future__ import annotations

import pytest

import pyModeS
from pyModeS import util


class TestHexBinConverters:
    def test_hex2bin_expands_to_4_bits_per_char(self) -> None:
        assert util.hex2bin("8D") == "10001101"
        assert util.hex2bin("0") == "0000"
        assert util.hex2bin("F") == "1111"

    def test_hex2bin_preserves_leading_zeros(self) -> None:
        # A leading-zero nibble must become four zero bits, not
        # be dropped — length is always exactly 4 * len(hexstr).
        assert util.hex2bin("01") == "00000001"
        assert util.hex2bin("00FF") == "0000000011111111"

    def test_bin2int(self) -> None:
        assert util.bin2int("0") == 0
        assert util.bin2int("1") == 1
        assert util.bin2int("10001101") == 0x8D

    def test_hex2int(self) -> None:
        assert util.hex2int("0") == 0
        assert util.hex2int("FF") == 255
        assert util.hex2int("8D406B90") == 0x8D406B90

    def test_bin2hex_uppercase_and_padded(self) -> None:
        assert util.bin2hex("10001101") == "8D"
        assert util.bin2hex("0000000011111111") == "00FF"
        # A 3-bit input rounds up to one hex char (one nibble)
        assert util.bin2hex("101") == "5"

    def test_roundtrip_hex_bin_hex(self) -> None:
        msg = "8D406B902015A678D4D220AA4BDA"
        assert util.bin2hex(util.hex2bin(msg)) == msg

    def test_hex2int_rejects_non_hex(self) -> None:
        with pytest.raises(ValueError):
            util.hex2int("notahex")


class TestMessageExtractors:
    # Reference messages with known-good decode outputs.
    DF17_IDENT = "8D406B902015A678D4D220AA4BDA"  # ident EZY85MH
    DF17_POS_EVEN = "8D40058B58C901375147EFD09357"  # airborne pos
    DF20_BDS10 = "A000178D10010080F50000D5893C"  # data link capability
    DF21_BDS60 = "A8000D9FA55A032DBFFC000D8123"  # heading/speed

    def test_df_matches_core_decode(self) -> None:
        for msg in (
            self.DF17_IDENT,
            self.DF17_POS_EVEN,
            self.DF20_BDS10,
            self.DF21_BDS60,
        ):
            assert util.df(msg) == pyModeS.decode(msg)["df"]

    def test_df_clamps_at_24(self) -> None:
        # A hex byte with top 5 bits >= 24 (0xC0 = 0b11000000 →
        # top 5 = 11000 = 24) must clamp rather than return 24, 25, ...
        assert util.df("C0000000000000") == 24
        assert util.df("F8000000000000") == 24

    def test_icao_df17_uses_aa_field(self) -> None:
        assert util.icao(self.DF17_IDENT) == "406B90"

    def test_icao_df20_21_via_crc_xor(self) -> None:
        # The CRC remainder of a DF20/21 message is its ICAO
        # (per the Mode-S reply overlay). Match the decoder.
        for msg in (self.DF20_BDS10, self.DF21_BDS60):
            assert util.icao(msg) == pyModeS.decode(msg)["icao"]

    def test_icao_df11_uses_aa_field(self) -> None:
        # A made-up DF11 with AA = 0x4840D6. DF=11 → top byte 0x58.
        msg = "5D4840D6202CC3"
        assert util.icao(msg) == "4840D6"

    def test_icao_returns_none_for_unaddressed_df(self) -> None:
        # DF24 (comm-D) doesn't carry an address via AA or CRC
        # overlay the same way, so the helper declines.
        assert util.icao("C0000000000000") is None

    def test_typecode_df17_matches_core_decode(self) -> None:
        assert util.typecode(self.DF17_IDENT) == 4
        assert (
            util.typecode(self.DF17_IDENT)
            == pyModeS.decode(self.DF17_IDENT)["typecode"]
        )

    def test_typecode_none_for_non_adsb(self) -> None:
        assert util.typecode(self.DF20_BDS10) is None
        assert util.typecode(self.DF21_BDS60) is None

    def test_crc_zero_for_valid_df17(self) -> None:
        assert util.crc(self.DF17_IDENT) == 0
        assert util.crc(self.DF17_POS_EVEN) == 0

    def test_crc_equals_icao_for_df20(self) -> None:
        # CRC of DF20/21 equals the ICAO XORed with a BDS
        # overlay. For BDS 1,0 the overlay is zero, so the crc
        # returns exactly the ICAO integer.
        icao_hex = util.icao(self.DF20_BDS10)
        assert icao_hex is not None
        assert util.crc(self.DF20_BDS10) == int(icao_hex, 16)

    def test_altcode_matches_core_decode_df20(self) -> None:
        # DF20 has altitude in the AC field.
        util_alt = util.altcode(self.DF20_BDS10)
        full = pyModeS.decode(self.DF20_BDS10)
        assert util_alt == full.get("altitude")

    def test_altcode_none_for_df17_21(self) -> None:
        # DF17 ADS-B altitude lives in the ME field, not the AC
        # field — altcode only understands the classic AC layout.
        assert util.altcode(self.DF17_POS_EVEN) is None
        assert util.altcode(self.DF21_BDS60) is None

    def test_idcode_matches_core_decode_df21(self) -> None:
        util_sq = util.idcode(self.DF21_BDS60)
        full = pyModeS.decode(self.DF21_BDS60)
        assert util_sq == full.get("squawk")

    def test_idcode_none_for_df17_20(self) -> None:
        assert util.idcode(self.DF17_IDENT) is None
        assert util.idcode(self.DF20_BDS10) is None


class TestCprNL:
    def test_cprnl_matches_position_cpr_internal(self) -> None:
        # Match the ICAO spec reference: 59 zones at the equator,
        # decreasing to 2 by latitude 87° and 1 at the pole.
        assert util.cprNL(0.0) == 59
        assert util.cprNL(52.0) == 36
        assert util.cprNL(87.0) == 2

    def test_cprnl_monotone_non_increasing(self) -> None:
        # Moving poleward can only decrease (or equal) the zone
        # count — a stable invariant of the CPR boundary table.
        prev = util.cprNL(0.0)
        for lat_deg in range(1, 88):
            now = util.cprNL(float(lat_deg))
            assert now <= prev
            prev = now
