"""Shared error builder for v2-API removal shims.

v3 deleted the function-per-field API that v2 shipped
(``from pyModeS.adsb import callsign``). Code written against v2
fails on a fresh v3 install with confusing ``ModuleNotFoundError``
or ``AttributeError`` messages. To give v2 users a clear pointer
to v3's unified ``decode()``, we keep stub modules at every
v2-visible path and intercept attribute access via
``pyModeS.__getattr__``. Both paths raise a
:class:`V2APIRemovedError` built here.

A single helper keeps the error message uniform across every
shim so updating the migration URL only touches one file.
"""

from __future__ import annotations

_MIGRATION_URL = "https://github.com/junzis/pyModeS/blob/main/docs/migration.md"


class V2APIRemovedError(ImportError):
    """Raised when legacy v2 code touches a removed v2 submodule.

    Inherits from :class:`ImportError` so it propagates naturally
    out of ``from pyModeS.adsb import callsign`` and also satisfies
    ``except ImportError`` clauses that v2 users may have written.
    """


def v2_removed_error(qualname: str) -> V2APIRemovedError:
    """Build a :class:`V2APIRemovedError` for the given v2 name.

    ``qualname`` is the dotted path the user tried to touch, e.g.
    ``"pyModeS.adsb"`` or ``"pyModeS.common.hex2bin"``. It's shown
    verbatim in the message so users see exactly which legacy
    import broke.
    """
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
        "\n"
        f"Migration guide: {_MIGRATION_URL}\n"
        "\n"
        "If you need the old function-per-field API, pin v2:\n"
        '    pip install "pyModeS<3"'
    )
    return V2APIRemovedError(message)
