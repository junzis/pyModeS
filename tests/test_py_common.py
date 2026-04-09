import pytest

from pyModeS import py_common


def test_conversions():
    assert py_common.hex2bin("6E") == "01101110"
    assert py_common.bin2hex("01101110") == "6E"
    assert py_common.bin2hex("1101110") == "6E"


def test_crc_decode():
    assert py_common.crc_legacy("8D406B902015A678D4D220AA4BDA") == 0

    assert py_common.crc("8D406B902015A678D4D220AA4BDA") == 0
    assert py_common.crc("8d8960ed58bf053cf11bc5932b7d") == 0
    assert py_common.crc("8d45cab390c39509496ca9a32912") == 0
    assert py_common.crc("8d49d3d4e1089d00000000744c3b") == 0
    assert py_common.crc("8d74802958c904e6ef4ba0184d5c") == 0
    assert py_common.crc("8d4400cd9b0000b4f87000e71a10") == 0
    assert py_common.crc("8d4065de58a1054a7ef0218e226a") == 0

    assert py_common.crc("c80b2dca34aa21dd821a04cb64d4") == 10719924
    assert py_common.crc("a800089d8094e33a6004e4b8a522") == 4805588
    assert py_common.crc("a8000614a50b6d32bed000bbe0ed") == 5659991
    assert py_common.crc("a0000410bc900010a40000f5f477") == 11727682
    assert py_common.crc("8d4ca251204994b1c36e60a5343d") == 16
    assert py_common.crc("b0001718c65632b0a82040715b65") == 353333


def test_crc_encode():
    parity = py_common.crc("8D406B902015A678D4D220AA4BDA", encode=True)
    assert parity == 11160538


def test_icao():
    assert py_common.icao("8D406B902015A678D4D220AA4BDA") == "406B90"
    assert py_common.icao("A0001839CA3800315800007448D9") == "400940"
    assert py_common.icao("A000139381951536E024D4CCF6B5") == "3C4DD2"
    assert py_common.icao("A000029CFFBAA11E2004727281F1") == "4243D0"


def test_modes_altcode():
    assert py_common.altcode("A02014B400000000000000F9D514") == 32300


def test_modes_idcode():
    assert py_common.idcode("A800292DFFBBA9383FFCEB903D01") == "1346"


def test_graycode_to_altitude():
    assert py_common.gray2alt("00000000010") == -1000
    assert py_common.gray2alt("00000001010") == -500
    assert py_common.gray2alt("00000011011") == -100
    assert py_common.gray2alt("00000011010") == 0
    assert py_common.gray2alt("00000011110") == 100
    assert py_common.gray2alt("00000010011") == 600
    assert py_common.gray2alt("00000110010") == 1000
    assert py_common.gray2alt("00001001001") == 5800
    assert py_common.gray2alt("00011100100") == 10300
    assert py_common.gray2alt("01100011010") == 32000
    assert py_common.gray2alt("01110000100") == 46300
    assert py_common.gray2alt("01010101100") == 50200
    assert py_common.gray2alt("11011110100") == 73200
    assert py_common.gray2alt("10000000011") == 126600
    assert py_common.gray2alt("10000000001") == 126700


RESERVED_RANGES = [
    (0x200000, 0x27FFFF, "AFI"),
    (0x280000, 0x28FFFF, "SAM"),
    (0x500000, 0x5FFFFF, "EUR/NAT"),
    (0x600000, 0x67FFFF, "MID"),
    (0x680000, 0x6F0000, "ASIA"),
    (0x900000, 0x9FFFFF, "NAM/PAC"),
    (0xB00000, 0xBFFFFF, "CAR"),
    (0xD00000, 0xDFFFFF, "future"),
    (0xF00000, 0xFFFFFF, "future"),
]


@pytest.mark.parametrize("lo,hi,name", RESERVED_RANGES)
def test_is_icao_assigned_boundaries_are_unassigned(lo, hi, name):
    """Both the low and high boundary of every reserved range must report
    as NOT assigned. Regression for the strict-inequality bug where
    `lo < icaoint < hi` let the endpoints leak through."""
    assert py_common.is_icao_assigned(f"{lo:06X}") is False, (
        f"{name} range low boundary {lo:06X} leaked through"
    )
    assert py_common.is_icao_assigned(f"{hi:06X}") is False, (
        f"{name} range high boundary {hi:06X} leaked through"
    )


@pytest.mark.parametrize("lo,hi,name", RESERVED_RANGES)
def test_is_icao_assigned_outside_boundaries(lo, hi, name):
    """One below the low boundary and one above the high boundary must
    report as assigned (unless they fall into another reserved range)."""
    if lo > 0:
        below = lo - 1
        in_other = any(
            low <= below <= high for (low, high, _) in RESERVED_RANGES if low != lo
        )
        if not in_other:
            assert py_common.is_icao_assigned(f"{below:06X}") is True, (
                f"{name} lo-1 {below:06X} should be assigned"
            )
    if hi < 0xFFFFFF:
        above = hi + 1
        in_other = any(
            low <= above <= high for (low, high, _) in RESERVED_RANGES if low != lo
        )
        if not in_other:
            assert py_common.is_icao_assigned(f"{above:06X}") is True, (
                f"{name} hi+1 {above:06X} should be assigned"
            )


@pytest.mark.parametrize("lo,hi,name", RESERVED_RANGES)
def test_is_icao_assigned_boundaries_c_common(lo, hi, name):
    """Same boundary check against the Cython implementation."""
    c_common = pytest.importorskip("pyModeS.c_common")
    assert c_common.is_icao_assigned(f"{lo:06X}") is False
    assert c_common.is_icao_assigned(f"{hi:06X}") is False


def test_um_all_ids_values():
    """py_common.um must return a valid (iis, ids, ids_text) tuple for all
    four values of ids (0, 1, 2, 3) without raising UnboundLocalError.

    Regression gate for the `if/if/if/if` chain that happened to work
    because each branch assigned unconditionally, but was fragile — any
    future edit that added a fall-through path could leave ids_text unbound.
    Now an elif chain with an else fallback.
    """
    for ids_value in (0, 1, 2, 3):
        bits = ["0"] * 56
        ids_bin = format(ids_value, "02b")
        bits[17] = ids_bin[0]
        bits[18] = ids_bin[1]
        binstr = "".join(bits)
        msg = format(int(binstr, 2), "014X")
        iis, ids, ids_text = py_common.um(msg)
        assert ids == ids_value, f"ids decode mismatch for value {ids_value}"
        if ids_value == 0:
            assert ids_text is None
        else:
            assert isinstance(ids_text, str)
