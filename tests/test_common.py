from pyModeS import common


def test_hex2bin():
    assert common.hex2bin('6E406B') == "011011100100000001101011"

def test_crc_decode():
    checksum = common.crc("8D406B902015A678D4D220AA4BDA")
    assert checksum == "000000000000000000000000"

def test_crc_encode():
    parity = common.crc("8D406B902015A678D4D220AA4BDA", encode=True)
    assert common.hex2bin("AA4BDA") == parity

def test_icao():
    assert common.icao("8D406B902015A678D4D220AA4BDA") == "406B90"
    assert common.icao("A0001839CA3800315800007448D9") == '400940'
    assert common.icao("A000139381951536E024D4CCF6B5") == '3C4DD2'
    assert common.icao("A000029CFFBAA11E2004727281F1") == '4243D0'

def test_modes_altcode():
    assert common.altcode("A02014B400000000000000F9D514") == 32300

def test_modes_idcode():
    assert common.idcode("A800292DFFBBA9383FFCEB903D01") == '1346'

def test_graycode_to_altitude():
    assert common.gray2alt('00000000010') == -1000
    assert common.gray2alt('00000001010') == -500
    assert common.gray2alt('00000011011') == -100
    assert common.gray2alt('00000011010') == 0
    assert common.gray2alt('00000011110') == 100
    assert common.gray2alt('00000010011') == 600
    assert common.gray2alt('00000110010') == 1000
    assert common.gray2alt('00001001001') == 5800
    assert common.gray2alt('00011100100') == 10300
    assert common.gray2alt('01100011010') == 32000
    assert common.gray2alt('01110000100') == 46300
    assert common.gray2alt('01010101100') == 50200
    assert common.gray2alt('11011110100') == 73200
    assert common.gray2alt('10000000011') == 126600
    assert common.gray2alt('10000000001') == 126700
