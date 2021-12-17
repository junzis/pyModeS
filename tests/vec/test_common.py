import numpy as np

from pyModeS.common import df, typecode

from .data import message

def test_df(message):
    """
    Test parsing of ADS-B downlink format.
    """
    result = df(message)
    assert np.array_equal([18, 21, 17, 18, 18, 17], result)

def test_typecode(message):
    """
    Test ADS-B type code parsing.
    """
    result = typecode(message)
    assert np.array_equal([6, 0, 4, 2, 1, 4], result)
    assert np.array_equal([6, 4, 2, 1, 4], result.compressed())
