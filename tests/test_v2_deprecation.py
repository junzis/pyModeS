"""Tests for the v2-API removal shims.

v3 deleted v2's function-per-field API (``from pyModeS.adsb
import callsign``). The shims in ``pyModeS/_v2_removed.py`` plus
the stub submodules (``pyModeS/adsb.py`` etc.) and the
``__getattr__`` hook in ``pyModeS/__init__.py`` together ensure
that every v2 access path raises a clear :class:`V2APIRemovedError`
pointing users at :func:`pyModeS.decode` and the migration guide.
"""

from __future__ import annotations

import importlib

import pytest

from pyModeS._v2_removed import V2APIRemovedError, modeslive_main

# Every v2 submodule name that should hit a removal shim. Mirrors
# ``_V2_REMOVED_NAMES`` in ``pyModeS/__init__.py`` — the two lists
# are kept in sync by a cross-check test below.
_V2_NAMES: tuple[str, ...] = (
    "adsb",
    "commb",
    "ehs",
    "els",
    "common",
    "util",
    "bds",
    "streamer",
    "extra",
)


def _assert_v2_error_message(exc: V2APIRemovedError, qualname: str) -> None:
    """Every removal message shares the same load-bearing phrases."""
    msg = str(exc)
    assert qualname in msg, msg
    assert "v3" in msg
    assert "decode(" in msg
    assert "migration.md" in msg
    assert '"pyModeS<3"' in msg


def test_v2_api_removed_error_is_import_error() -> None:
    """``except ImportError`` in v2 user code should still catch."""
    exc = V2APIRemovedError("demo")
    assert isinstance(exc, ImportError)


@pytest.mark.parametrize("name", _V2_NAMES)
def test_submodule_import_raises(name: str) -> None:
    # Fresh import each run — remove any cached stub first so the
    # stub's module-level raise fires on every parametrised case.
    importlib.invalidate_caches()
    qualname = f"pyModeS.{name}"
    import sys

    sys.modules.pop(qualname, None)
    with pytest.raises(V2APIRemovedError) as info:
        importlib.import_module(qualname)
    _assert_v2_error_message(info.value, qualname)


@pytest.mark.parametrize("name", _V2_NAMES)
def test_attribute_access_raises(name: str) -> None:
    import pyModeS

    with pytest.raises(V2APIRemovedError) as info:
        getattr(pyModeS, name)
    _assert_v2_error_message(info.value, f"pyModeS.{name}")


def test_unknown_attribute_is_still_attribute_error() -> None:
    """Unrelated attribute access stays a regular AttributeError."""
    import pyModeS

    with pytest.raises(AttributeError, match="no attribute 'does_not_exist'"):
        _ = pyModeS.does_not_exist  # type: ignore[attr-defined]


def test_nested_import_via_v2_bds_package_raises() -> None:
    """``from pyModeS.bds.bds05 import altitude`` must not leak
    through to a ModuleNotFoundError — the ``pyModeS.bds`` stub
    package's ``__init__.py`` should raise first."""
    import sys

    sys.modules.pop("pyModeS.bds", None)
    sys.modules.pop("pyModeS.bds.bds05", None)
    with pytest.raises(V2APIRemovedError) as info:
        importlib.import_module("pyModeS.bds.bds05")
    assert "pyModeS.bds" in str(info.value)


def test_v3_api_still_works_after_shim_touch() -> None:
    """Triggering the removal shim must not corrupt v3's own state."""
    import pyModeS

    with pytest.raises(V2APIRemovedError):
        _ = pyModeS.adsb  # type: ignore[attr-defined]
    # v3 API still works
    result = pyModeS.decode("8D406B902015A678D4D220AA4BDA")
    assert result["callsign"] == "EZY85MH"


def test_modeslive_main_prints_migration_hint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """v2's ``modeslive`` console script now prints a migration
    hint pointing at ``modes live`` / ``modes decode``, and
    returns exit code 2 (usage error)."""
    rc = modeslive_main()
    assert rc == 2
    captured = capsys.readouterr()
    # Printed to stderr, not stdout
    assert captured.out == ""
    err = captured.err
    assert "modeslive" in err
    assert "removed in pyModeS v3" in err
    assert "modes live" in err
    assert "modes decode" in err
    assert "migration.md" in err
    assert '"pyModeS<3"' in err


def test_removed_names_set_matches_test_list() -> None:
    """Keep the test-side ``_V2_NAMES`` in sync with the production
    set in ``pyModeS/__init__.py``. If v3 adds a new shim, update
    both — failing this test on an imbalance is the point."""
    from pyModeS import _V2_REMOVED_NAMES

    assert frozenset(_V2_NAMES) == _V2_REMOVED_NAMES
