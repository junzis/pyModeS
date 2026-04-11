"""Removed in v3 — see :mod:`pyModeS._v2_removed`.

The v2 ``pyModeS.common`` bit/hex/CRC helpers were restored in
v3 under :mod:`pyModeS.util`. The hint in the error message
below points users directly at the new location.
"""

from pyModeS._v2_removed import v2_removed_error

raise v2_removed_error(
    "pyModeS.common",
    hint=(
        "The bit/hex/CRC helpers that used to live in "
        "pyModeS.common (hex2bin, bin2int, crc, df, icao, ...) "
        "are restored in v3 under pyModeS.util:\n"
        "\n"
        "    from pyModeS.util import hex2bin, crc, icao\n"
        "    crc('8D406B902015A678D4D220AA4BDA')  # 0\n"
        "    icao('8D406B902015A678D4D220AA4BDA') # '406B90'"
    ),
)
