"""Decoder classes for pymodes, organized by DF family.

Each decoder class handles one or more downlink formats (see spec §5.3):

- AllCallReply: DF11
- SurvReply:    DF4, DF5
- ACAS:         DF0, DF16
- ADSB:         DF17, DF18 (Plan 2)
- CommB:        DF20, DF21 (Plan 3)

Message.decode() dispatches to the correct class via _DECODERS below.
Entries are added by the task that implements each decoder class.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymodes.decoder._base import DecoderBase


# DF → decoder class. Populated by each decoder module as it is added.
_DECODERS: dict[int, type[DecoderBase]] = {}


def register(
    *dfs: int,
) -> Callable[[type[DecoderBase]], type[DecoderBase]]:
    """Decorator that registers a decoder class for one or more DFs.

    Usage:
        @register(11)
        class AllCallReply(DecoderBase):
            ...
    """

    def _wrap(cls: type[DecoderBase]) -> type[DecoderBase]:
        for df in dfs:
            _DECODERS[df] = cls
        return cls

    return _wrap


# Import decoder modules to populate _DECODERS via @register decorators.
# These imports are at the bottom to avoid circular dependencies.
from pymodes.decoder import allcall  # noqa: F401,E402
