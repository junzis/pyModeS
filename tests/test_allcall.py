from pyModeS import allcall


def test_icao():
    assert allcall.icao("5D484FDEA248F5") == "484FDE"


def test_interrogator():
    assert allcall.interrogator("5D484FDEA248F5") == "SI6"


def test_capability():
    assert allcall.capability("5D484FDEA248F5")[0] == 5
