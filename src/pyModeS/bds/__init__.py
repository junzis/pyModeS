"""Removed in v3 — see :mod:`pyModeS._v2_removed`.

This stub intentionally collides with the v2 ``pyModeS.bds``
package so that ``from pyModeS.bds.bds05 import altitude`` (v2)
fails fast with a migration pointer instead of a surprising
``ModuleNotFoundError``. The real v3 BDS decoders live under
``pyModeS.decoder.bds`` and are internal implementation detail —
users should call :func:`pyModeS.decode` instead.
"""

from pyModeS._v2_removed import v2_removed_error

raise v2_removed_error("pyModeS.bds")
