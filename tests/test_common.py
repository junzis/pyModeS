from pyModeS import common


def test_conversions():
    assert common.hex2bin("6E406B") == "011011100100000001101011"


def test_crc_decode():
    assert common.crc_legacy("8D406B902015A678D4D220AA4BDA") == 0

    assert common.crc("8D406B902015A678D4D220AA4BDA") == 0
    assert common.crc("8d8960ed58bf053cf11bc5932b7d") == 0
    assert common.crc("8d45cab390c39509496ca9a32912") == 0
    assert common.crc("8d49d3d4e1089d00000000744c3b") == 0
    assert common.crc("8d74802958c904e6ef4ba0184d5c") == 0
    assert common.crc("8d4400cd9b0000b4f87000e71a10") == 0
    assert common.crc("8d4065de58a1054a7ef0218e226a") == 0

    assert common.crc("c80b2dca34aa21dd821a04cb64d4") == 10719924
    assert common.crc("a800089d8094e33a6004e4b8a522") == 4805588
    assert common.crc("a8000614a50b6d32bed000bbe0ed") == 5659991
    assert common.crc("a0000410bc900010a40000f5f477") == 11727682
    assert common.crc("8d4ca251204994b1c36e60a5343d") == 16
    assert common.crc("b0001718c65632b0a82040715b65") == 353333


def test_crc_encode():
    parity = common.crc("8D406B902015A678D4D220AA4BDA", encode=True)
    assert parity == 11160538


def test_icao():
    assert common.icao("8D406B902015A678D4D220AA4BDA") == "406B90"
    assert common.icao("A0001839CA3800315800007448D9") == "400940"
    assert common.icao("A000139381951536E024D4CCF6B5") == "3C4DD2"
    assert common.icao("A000029CFFBAA11E2004727281F1") == "4243D0"


def test_modes_altcode():
    assert common.altcode("A02014B400000000000000F9D514") == 32300


def test_modes_idcode():
    assert common.idcode("A800292DFFBBA9383FFCEB903D01") == "1346"


def test_graycode_to_altitude():
    assert common.gray2alt("00000000010") == -1000
    assert common.gray2alt("00000001010") == -500
    assert common.gray2alt("00000011011") == -100
    assert common.gray2alt("00000011010") == 0
    assert common.gray2alt("00000011110") == 100
    assert common.gray2alt("00000010011") == 600
    assert common.gray2alt("00000110010") == 1000
    assert common.gray2alt("00001001001") == 5800
    assert common.gray2alt("00011100100") == 10300
    assert common.gray2alt("01100011010") == 32000
    assert common.gray2alt("01110000100") == 46300
    assert common.gray2alt("01010101100") == 50200
    assert common.gray2alt("11011110100") == 73200
    assert common.gray2alt("10000000011") == 126600
    assert common.gray2alt("10000000001") == 126700
