"""Tests that pyModeS.c_common and pyModeS.py_common present the same contract
for Optional[int] return types. Both implementations must return None (not a
sentinel value) when given invalid input."""

import pytest

from pyModeS import py_common

try:
    from pyModeS import c_common
    HAVE_C = True
except ImportError:
    HAVE_C = False

MODULES = [py_common]
if HAVE_C:
    MODULES.append(c_common)


@pytest.mark.parametrize("mod", MODULES)
def test_altitude_zero_returns_none(mod):
    """13-bit all-zero altitude code means 'altitude unknown or invalid'."""
    assert mod.altitude("0000000000000") is None


@pytest.mark.parametrize("mod", MODULES)
def test_gray2alt_invalid_n100_returns_none(mod):
    """gray2alt must return None when n100 decodes to 0, 5, or 6 (reserved)."""
    # gc100 == "101" → gray2int = 6 (invalid). gc500 is arbitrary here.
    assert mod.gray2alt("00000000" + "101") is None


@pytest.mark.parametrize("mod", MODULES)
def test_altcode_df4_zero_returns_none(mod):
    """altcode for a DF4 message with zero altitude field returns None."""
    # DF=4 (00100), FS=0, DR=0, UM=0, AC=0, all zero payload. 14 hex chars.
    msg = "20000000000000"
    assert mod.altcode(msg) is None


@pytest.mark.parametrize("mod", MODULES)
def test_typecode_non_df17_returns_none(mod):
    """typecode must return None for non-DF17/18 messages."""
    msg = "20000000000000"  # DF4
    assert mod.typecode(msg) is None
