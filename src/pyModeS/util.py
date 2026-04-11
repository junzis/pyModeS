"""Public utility helpers for low-level Mode-S message inspection.

This module is a thin, public wrapper around the bit/hex/CRC
primitives that v3's decoder uses internally. Users rarely need
these functions — ``pyModeS.decode(msg)`` returns every decodable
field in one dict. They're exposed for ad-hoc message inspection,
custom tooling that needs to pre-filter a stream before passing
messages to :func:`pyModeS.decode`, or tests that want to poke
at a raw message without spinning up the full decoder.

Everything here is either a one-liner over stdlib (``hex2bin``,
``bin2int``) or a thin wrapper over an existing ``pyModeS._bits``
/ ``pyModeS._altcode`` / ``pyModeS._idcode`` / ``pyModeS.position``
primitive. There is no second implementation — changing v3's
internals automatically flows through to this public surface.

See :mod:`pyModeS` or ``docs/quickstart.md`` for the canonical
``decode()`` API.
"""

from __future__ import annotations

from pyModeS._altcode import altcode_to_altitude
from pyModeS._bits import crc_remainder
from pyModeS._idcode import idcode_to_squawk
from pyModeS.position._cpr import cprNL as _cprNL

__all__ = [
    "altcode",
    "bin2hex",
    "bin2int",
    "cprNL",
    "crc",
    "df",
    "hex2bin",
    "hex2int",
    "icao",
    "idcode",
    "typecode",
]


# ---------------------------------------------------------------------------
# Hex / binary string converters
# ---------------------------------------------------------------------------


def hex2bin(hexstr: str) -> str:
    """Convert a hex string to a zero-padded binary string.

    Each hex character expands to exactly four bits, so the
    output length is always ``4 * len(hexstr)`` — leading zeros
    are preserved.

    >>> hex2bin("8D")
    '10001101'
    """
    return f"{int(hexstr, 16):0{4 * len(hexstr)}b}"


def bin2int(binstr: str) -> int:
    """Parse a binary (``'0'``/``'1'``) string to an integer."""
    return int(binstr, 2)


def hex2int(hexstr: str) -> int:
    """Parse a hex string to an integer."""
    return int(hexstr, 16)


def bin2hex(binstr: str) -> str:
    """Convert a binary string to an uppercase hex string.

    The output width is ``ceil(len(binstr) / 4)`` hex characters,
    so bit strings whose length isn't a multiple of four pad on
    the left when mapped to nibble boundaries.
    """
    width = (len(binstr) + 3) // 4
    return f"{int(binstr, 2):0{width}X}"


# ---------------------------------------------------------------------------
# Message-level extractors
# ---------------------------------------------------------------------------


def df(msg: str) -> int:
    """Mode-S downlink format (bits 0-4).

    Values 24-31 all denote the same "extended-length Comm-D"
    format in Annex 10, so the return is clamped at 24 — matching
    every public Mode-S decoder including pyModeS v2, dump1090,
    and rs1090.

    >>> df("8D406B902015A678D4D220AA4BDA")
    17
    """
    top = int(msg[:2], 16) >> 3
    return 24 if top >= 24 else top


def icao(msg: str) -> str | None:
    """Return the ICAO 24-bit address embedded in ``msg``.

    For DF11/17/18 the address is carried explicitly in the AA
    field (bits 8-31). For DF0/4/5/16/20/21 it's XORed into the
    parity field during interrogation, so we recover it by taking
    the CRC-24 remainder of the whole message. Other DFs don't
    carry an address and return ``None``.

    >>> icao("8D406B902015A678D4D220AA4BDA")
    '406B90'
    """
    dfv = df(msg)
    if dfv in (11, 17, 18):
        return msg[2:8].upper()
    if dfv in (0, 4, 5, 16, 20, 21):
        length = len(msg) * 4
        rem = crc_remainder(int(msg, 16), length)
        return f"{rem:06X}"
    return None


def typecode(msg: str) -> int | None:
    """ADS-B type code (ME bits 32-36) for DF17/18, else ``None``.

    >>> typecode("8D406B902015A678D4D220AA4BDA")
    4
    """
    if df(msg) not in (17, 18):
        return None
    return int(msg[8:10], 16) >> 3


def crc(msg: str) -> int:
    """Mode-S CRC-24 remainder of a hex message.

    Returns 0 for a valid DF17/18 extended squitter; for DF20/21
    returns the aircraft's ICAO address (possibly XORed with a
    BDS overlay). Thin wrapper around :func:`pyModeS._bits.crc_remainder`.

    >>> crc("8D406B902015A678D4D220AA4BDA")
    0
    """
    length = len(msg) * 4
    return crc_remainder(int(msg, 16), length)


def altcode(msg: str) -> int | None:
    """Altitude in feet from the 13-bit AC field (DF0/4/16/20).

    Returns ``None`` for other DFs and for the reserved "altitude
    unknown" AC=0 code.
    """
    dfv = df(msg)
    if dfv not in (0, 4, 16, 20):
        return None
    length = len(msg) * 4
    # AC occupies bits 19-31 (MSB-first, 13 bits) on all four
    # message types that carry it.
    ac = (int(msg, 16) >> (length - 32)) & 0x1FFF
    return altcode_to_altitude(ac)


def idcode(msg: str) -> str | None:
    """4-digit octal squawk from the 13-bit ID field (DF5/21).

    Returns ``None`` for other DFs.
    """
    dfv = df(msg)
    if dfv not in (5, 21):
        return None
    length = len(msg) * 4
    # ID occupies bits 19-31 (same layout as AC, different field).
    ident = (int(msg, 16) >> (length - 32)) & 0x1FFF
    return idcode_to_squawk(ident)


# ---------------------------------------------------------------------------
# CPR helper (re-exported)
# ---------------------------------------------------------------------------


def cprNL(lat: float) -> int:
    """CPR NL (longitude zone count) lookup for a given latitude.

    Exposed here so custom CPR code can reuse v3's ICAO-standard
    NL boundary table without reaching into
    ``pyModeS.position._cpr``.
    """
    return _cprNL(lat)
