"""Shims and meta-path finder for removed v2 API paths.

v3 deleted the v2 function-per-field API (``from pyModeS.adsb
import callsign``) but keeps v2's distribution slot on PyPI,
so legacy code lands on v3 after ``pip install -U pyModeS``.
Without a catch, users see an opaque ``ModuleNotFoundError``
for submodule imports or a bare ``AttributeError`` for
``pms.adsb.callsign``. This module turns both paths into a
clear :class:`V2APIRemovedError` that points at the v3
``decode()`` dict API and the migration guide.

Two entry points, both routing through :func:`v2_removed_error`
so the error text stays uniform across every v2 touchpoint:

1. A meta-path finder (:class:`_V2RemovedFinder`) intercepts
   every ``pyModeS.<removed>`` submodule import and raises from
   the loader's ``exec_module``. Covers ``from pyModeS.adsb
   import X``, ``import pyModeS.commb``, and nested paths like
   ``from pyModeS.bds.bds05 import altitude`` — the
   ``pyModeS.bds`` parent shim fires before the nested module
   is ever resolved.

2. A module-level ``__getattr__`` in ``pyModeS/__init__.py``
   (PEP 562) catches bare attribute access like
   ``pyModeS.adsb`` that doesn't go through the import system.

The finder replaces what used to be eight hand-written stub
files (``adsb.py``, ``commb.py``, ``bds/__init__.py``, etc.).
Adding a new removed-module name is now a one-liner in
``_V2_REMOVED_NAMES`` below.

Also exports :func:`modeslive_main`, the console-script entry
point registered as ``modeslive`` in pyproject.toml — v2's beast
streamer CLI is removed in v3, and this stub prints a hint
pointing at ``modes live`` / ``modes decode``.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from collections.abc import Sequence
from types import ModuleType
from typing import NoReturn

_MIGRATION_URL = "https://github.com/junzis/pyModeS/blob/main/docs/migration.md"

# Bare v2 submodule names under pyModeS.<name>. Kept as short
# names so the __getattr__ hook in pyModeS/__init__.py can look
# them up directly by attribute name without having to strip a
# `pyModeS.` prefix every call.
_V2_REMOVED_NAMES: frozenset[str] = frozenset(
    {
        "adsb",
        "commb",
        "ehs",
        "els",
        "common",
        "bds",
        "streamer",
        "extra",
    }
)

# Fully-qualified module names for the meta-path finder, derived
# from the short names above. Kept as a separate frozenset so
# set membership is O(1) rather than a per-import string build.
_V2_REMOVED_MODULES: frozenset[str] = frozenset(
    f"pyModeS.{name}" for name in _V2_REMOVED_NAMES
)

# Per-module migration hints appended to the error message.
# Modules not listed here fall back to the generic `decode()`
# pointer. The common shim is the only module whose replacement
# isn't decode(): its bit/hex/CRC helpers moved to pyModeS.util.
_COMMON_HINT = (
    "The bit/hex/CRC helpers that used to live in "
    "pyModeS.common (hex2bin, bin2int, crc, df, icao, ...) "
    "are restored in v3 under pyModeS.util:\n"
    "\n"
    "    from pyModeS.util import hex2bin, crc, icao\n"
    "    crc('8D406B902015A678D4D220AA4BDA')  # 0\n"
    "    icao('8D406B902015A678D4D220AA4BDA') # '406B90'"
)

_V2_HINTS: dict[str, str] = {
    "pyModeS.common": _COMMON_HINT,
}


class V2APIRemovedError(ImportError):
    """Raised when legacy v2 code touches a removed v2 submodule.

    Inherits from :class:`ImportError` so it propagates naturally
    out of ``from pyModeS.adsb import callsign`` and also satisfies
    ``except ImportError`` clauses that v2 users may have written.
    """


def v2_removed_error(qualname: str, *, hint: str | None = None) -> V2APIRemovedError:
    """Build a :class:`V2APIRemovedError` for the given v2 name.

    ``qualname`` is the dotted path the user tried to touch, e.g.
    ``"pyModeS.adsb"`` or ``"pyModeS.common"``. It's shown
    verbatim in the message so users see exactly which legacy
    import broke.

    ``hint`` is an optional extra paragraph slotted between the
    generic ``decode()`` example and the migration-guide link.
    Used by shims whose replacement isn't ``decode()`` — e.g.
    ``pyModeS.common`` routes users to ``pyModeS.util`` instead.
    """
    hint_block = f"\n{hint}\n" if hint else ""
    message = (
        f"{qualname} is part of the pyModeS v2 API, which was "
        "removed in v3.\n"
        "\n"
        "pyModeS v3 replaces the function-per-field API with a "
        "single decode() call that returns every decodable field "
        "in one dict:\n"
        "\n"
        "    import pyModeS\n"
        "    result = pyModeS.decode(msg)\n"
        '    callsign = result["callsign"]\n'
        '    altitude = result["altitude"]\n'
        f"{hint_block}"
        "\n"
        f"Migration guide: {_MIGRATION_URL}\n"
        "\n"
        "If you need the old function-per-field API, pin v2:\n"
        '    pip install "pyModeS<3"'
    )
    return V2APIRemovedError(message)


def raise_v2_removed(qualname: str) -> NoReturn:
    """Raise :class:`V2APIRemovedError` with the right hint for ``qualname``.

    Both the meta-path loader and the ``__getattr__`` hook in
    ``pyModeS/__init__.py`` call this so the hint lookup happens
    in exactly one place.
    """
    raise v2_removed_error(qualname, hint=_V2_HINTS.get(qualname))


class _V2RemovedLoader(importlib.abc.Loader):
    """Loader that raises V2APIRemovedError instead of executing a module.

    The meta-path finder attaches this loader to the spec it
    returns for any intercepted v2 path. When Python calls
    ``exec_module``, we raise — the module never populates
    ``sys.modules``, so a subsequent import retries from scratch
    rather than replaying a stale, partially-initialised shim.
    """

    def __init__(self, qualname: str) -> None:
        # qualname may differ from the imported fullname: for a
        # nested path like pyModeS.bds.bds05, we report the
        # parent shim's name (pyModeS.bds) in the error so users
        # see the actual removed package.
        self.qualname = qualname

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        # None → use default module creation; we'll raise from
        # exec_module instead.
        return None

    def exec_module(self, module: ModuleType) -> None:
        raise_v2_removed(self.qualname)


class _V2RemovedFinder(importlib.abc.MetaPathFinder):
    """Meta-path finder that intercepts removed-v2 submodule imports.

    Direct matches (``pyModeS.adsb``, ``pyModeS.common``, ...) and
    nested paths (``pyModeS.bds.bds05`` → parent ``pyModeS.bds``)
    both resolve to a spec whose loader raises on exec. Any import
    we don't recognise returns ``None`` so the default
    :class:`PathFinder` can handle it — including the real
    :mod:`pyModeS.util` module.
    """

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname in _V2_REMOVED_MODULES:
            return importlib.machinery.ModuleSpec(
                fullname, _V2RemovedLoader(fullname), is_package=False
            )
        # Nested: a caller tried to import pyModeS.bds.bds05 etc.
        # Report the parent shim's name in the error so users see
        # "pyModeS.bds is part of the v2 API" rather than a
        # confusing "pyModeS.bds.bds05" they may not recognise.
        for removed in _V2_REMOVED_MODULES:
            if fullname.startswith(f"{removed}."):
                return importlib.machinery.ModuleSpec(
                    fullname, _V2RemovedLoader(removed), is_package=False
                )
        return None


_FINDER: _V2RemovedFinder = _V2RemovedFinder()


def install_v2_removed_finder() -> None:
    """Install :class:`_V2RemovedFinder` at the head of ``sys.meta_path``.

    Idempotent — repeated calls are a no-op. Called from
    :mod:`pyModeS` at package import time.
    """
    if _FINDER not in sys.meta_path:
        sys.meta_path.insert(0, _FINDER)


def modeslive_main() -> int:
    """Console-script entry point for the removed ``modeslive``.

    v2 shipped a ``modeslive`` console script for its beast
    streamer. v3 replaces it with ``modes live`` and ``modes
    decode``. Registering this stub as ``modeslive`` in
    pyproject.toml gives users who still type the old command
    a clear migration hint instead of ``command not found``.

    Returns exit code 2 (conventional for usage errors), ignores
    argv — any flags the user passed to the old command are
    irrelevant because nothing is going to run.
    """
    message = (
        "modeslive: error: the v2 `modeslive` command was removed "
        "in pyModeS v3.\n"
        "\n"
        "pyModeS v3 replaces it with the `modes` CLI:\n"
        "\n"
        "    modes live --network HOST:PORT    "
        "# stream from a TCP beast feed\n"
        "    modes decode HEX                  "
        "# one-shot hex decode\n"
        "    modes decode --file PATH          "
        "# batch decode from file / stdin\n"
        "\n"
        f"Migration guide: {_MIGRATION_URL}\n"
        "\n"
        "If you need the old `modeslive` command, pin v2:\n"
        '    pip install "pyModeS<3"'
    )
    print(message, file=sys.stderr)
    return 2
