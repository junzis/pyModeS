"""Tests that pyModeS.c_common and pyModeS.py_common present the same contract
for Optional[int] return types. Both implementations must return None (not a
sentinel value) when given invalid input.

The c_common parametrizations are explicitly skipped (with a visible SKIPPED
marker) when the Cython extension is not built — this avoids the silent
"4 passed" outcome that previously hid contract violations when the .so was
missing.
"""

import pytest

from pyModeS import py_common

c_common = pytest.importorskip("pyModeS.c_common")

MODULES = [py_common, c_common]


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
def test_altitude_delegates_to_gray2alt_none(mod):
    """When Mbit=0 Qbit=0 and the gray-coded altitude bits decode to an
    invalid n100 (0, 5, or 6), altitude() must propagate the None from
    gray2alt() — not silently return 0 or a partial value.

    Regression gate for the altitude→gray2alt chained-None path: if a
    future edit re-types gray2alt to return int (re-introducing a sentinel)
    without updating altitude, this test catches it.
    """
    # 13-bit altitude code:
    #   bit 0-5: C1 A1 C2 A2 C4 A4 (high bits of gray altitude)
    #   bit 6:   Mbit (0 = feet)
    #   bit 7:   B1 (100ft step bit)
    #   bit 8:   Qbit (0 = 100ft interval / gray encoding)
    #   bit 9-12: B2 D2 B4 D4
    #
    # We need: Mbit=0, Qbit=0, and the gray2alt() input string (formed by
    # altitude() as C1 A1 C2 A2 C4 A4 B1 B2 D2 B4 D4 — 11 bits) to have
    # n100 ∈ {0, 5, 6}.
    #
    # gray2alt() slices codestr as gc500=codestr[:8] and gc100=codestr[8:].
    # gc100 is 3 bits. gray2int("000")=0, gray2int("111")=5, gray2int("101")=6.
    #
    # altitude() builds graystr from the binstr characters in this order:
    #   graystr = D2 + D4 + A1 + A2 + A4 + B1 + B2 + B4 + C1 + C2 + C4
    # so gc100 = C1 + C2 + C4 = binstr[0] + binstr[2] + binstr[4].
    #
    # To force gc100 = "101" (n100 = 6, invalid), set:
    #   binstr[0]=1, binstr[2]=0, binstr[4]=1
    # All other bits zero, with Mbit (pos 6) = 0 and Qbit (pos 8) = 0.
    #
    # binstr positions: 0  1  2  3  4  5  6  7  8  9  10 11 12
    #                   C1 A1 C2 A2 C4 A4 M  B1 Q  B2 D2 B4 D4
    # Values:           1  0  0  0  1  0  0  0  0  0  0  0  0
    binstr = "1000100000000"
    assert mod.altitude(binstr) is None


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
