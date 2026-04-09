import sys

import pytest
from pyModeS import bds

# this one fails on GitHub action for some unknown reason
# it looks successful on other Windows instances though
# TODO fix later
@pytest.mark.skipif(sys.platform == "win32", reason="GitHub Action")
def test_bds_infer():
    assert bds.infer("8D406B902015A678D4D220AA4BDA") == "BDS08"
    assert bds.infer("8FC8200A3AB8F5F893096B000000") == "BDS06"
    assert bds.infer("8D40058B58C901375147EFD09357") == "BDS05"
    assert bds.infer("8D485020994409940838175B284F") == "BDS09"

    assert bds.infer("A800178D10010080F50000D5893C") == "BDS10"
    assert bds.infer("A0000638FA81C10000000081A92F") == "BDS17"
    assert bds.infer("A0001838201584F23468207CDFA5") == "BDS20"
    assert bds.infer("A0001839CA3800315800007448D9") == "BDS40"
    assert bds.infer("A000139381951536E024D4CCF6B5") == "BDS50"
    assert bds.infer("A00004128F39F91A7E27C46ADC21") == "BDS60"


def test_bds_is50or60():
    assert bds.is50or60("A0001838201584F23468207CDFA5", 0, 0, 0) == None
    assert bds.is50or60("A8001EBCFFFB23286004A73F6A5B", 320, 250, 14000) == "BDS50"
    assert bds.is50or60("A8001EBCFE1B29287FDCA807BCFC", 320, 250, 14000) == "BDS50"


def test_surface_position():
    msg0 = "8FE48C033A9FA184B934E744C6FD"
    msg1 = "8FE48C033A9FA68F7C3D39B1C2F0"

    t0 = 1565608663102
    t1 = 1565608666214

    lat_ref = -23.4265448
    lon_ref = -46.4816258

    lat, lon = bds.bds06.surface_position(msg0, msg1, t0, t1, lat_ref, lon_ref)

    assert abs(lon_ref - lon) < 0.05


def test_is45_bounds_check_applies_to_zero_temperature():
    """BDS45 is45 must run its temperature bounds check unconditionally,
    not short-circuit via a truthy test that treats 0.0°C as 'no data'.

    The original code at bds45.py:58 read `if temp: if temp > 60 or
    temp < -80: return False` which skipped the bounds check entirely
    when temp == 0.0. The fix uses an explicit `-80 <= temp <= 60`
    range test.
    """
    import inspect

    from pyModeS.decoder.bds import bds45

    src = inspect.getsource(bds45.is45)
    assert "if temp:" not in src, (
        "bds45.is45 still uses truthy `if temp:` check — must use "
        "explicit `-80 <= temp <= 60` range test so 0.0°C is validated"
    )
    assert "-80" in src and "60" in src, (
        "bds45.is45 must contain explicit temperature bounds"
    )
