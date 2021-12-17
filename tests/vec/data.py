import numpy as np
from binascii import unhexlify

from pyModeS.vec.ctor import array
from pyModeS.vec.common import df

import pytest

@pytest.fixture
def message():
    data = [
        '904ca3a33219741c85465ae1b4c3',  # df = 18
        'a8281d3030000000000000850d4a',  # df = 21
        '8d406b902015a678d4d220000000',  # example from https://mode-s.org/decode/content/ads-b/8-error-control.html
        '904ca3da121010603d04f5df3ecf',  # df = 18, tc = 2
        '977ba7ca0daa3e1915d83237c86e',  # df = 18, tc = 1
        '8d4ca2d4234994b5452820e5b7ab',  # df = 17, tc = 4
    ]
    return array(np.array([unhexlify(v) for v in data]))

@pytest.fixture
def df_message(message):
    return df(message)

# vim: sw=4:et:ai

