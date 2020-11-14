from pyModeS import surv


def test_fs():
    assert surv.fs("2A00516D492B80")[0] == 2


def test_dr():
    assert surv.dr("2A00516D492B80")[0] == 0


def test_um():
    assert surv.um("200CBE4ED80137")[0] == 9
    assert surv.um("200CBE4ED80137")[1] == 1


def test_identity():
    assert surv.identity("2A00516D492B80") == "0356"


def test_altitude():
    assert surv.altitude("20001718029FCD") == 36000
