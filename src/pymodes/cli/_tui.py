"""Optional rich-based TUI for ``modes live --tui``.

This module is lazy-imported by ``cli/live.py`` ONLY when the ``--tui``
flag is set. If ``rich`` is not installed, the import fails and the
caller converts the ImportError into a clean exit-3 with an install
hint pointing at ``pip install "pymodes[tui]"``.

Rendering strategy: the TuiSink maintains its own per-ICAO sliding
state, merging in fields from every decoded message that arrives.
On each ``write(decoded)`` call the row for that ICAO is updated and
the table is re-rendered via ``rich.live.Live``. Re-render cost is
tiny compared to the decode cost, so we re-render on every message
rather than on a timer.
"""

from __future__ import annotations

import sys
import time
from types import TracebackType
from typing import Any

# This import raises ImportError if rich is missing — intentional,
# caller (cli/live.py) catches it and emits a clean exit-3.
from rich.console import Console
from rich.live import Live
from rich.table import Table

from pymodes.message import Decoded


class TuiSink:
    """rich-based live aircraft table.

    Maintains a sliding view over recently-seen aircraft keyed by
    ICAO. On every ``write(decoded)`` call the row for that ICAO is
    updated in-place and the table is re-rendered via
    ``rich.live.Live``.

    The TUI takes over the terminal (``screen=True`` puts rich into
    the alternate screen mode) so stdout JSON lines are NOT emitted
    when ``--tui`` is active. argparse enforces the ``--tui`` +
    ``--dump-to`` and ``--tui`` + ``--quiet`` mutexes.

    Output goes to ``sys.stderr`` so any stray stdout writes from
    other code paths don't garble the rendered table.
    """

    def __init__(self) -> None:
        self._console = Console(file=sys.stderr)
        self._state: dict[str, dict[str, Any]] = {}
        self._last_seen: dict[str, float] = {}
        self._total = 0
        self._live: Live | None = None

    def __enter__(self) -> TuiSink:
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=4,
            screen=True,
        )
        self._live.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._live is not None:
            self._live.__exit__(exc_type, exc, tb)
            self._live = None

    def write(self, decoded: Decoded) -> None:
        self._total += 1
        icao = decoded.get("icao")
        if not icao:
            return
        state = self._state.setdefault(icao, {})
        # Merge non-null fields into the per-ICAO sliding state
        for key in (
            "callsign",
            "altitude",
            "groundspeed",
            "track",
            "latitude",
            "longitude",
        ):
            val = decoded.get(key)
            if val is not None:
                state[key] = val
        self._last_seen[icao] = time.monotonic()

        if self._live is not None:
            self._live.update(self._render())

    def close(self) -> None:
        if self._live is not None:
            self._live.__exit__(None, None, None)
            self._live = None

    def _render(self) -> Table:
        now = time.monotonic()
        table = Table(
            title=f"pymodes live — {self._total} msgs, {len(self._state)} a/c",
            show_lines=False,
            expand=True,
        )
        table.add_column("ICAO", style="cyan", no_wrap=True)
        table.add_column("Callsign", style="green", no_wrap=True)
        table.add_column("Alt(ft)", justify="right")
        table.add_column("GS(kt)", justify="right")
        table.add_column("Trk(°)", justify="right")
        table.add_column("Lat", justify="right")
        table.add_column("Lon", justify="right")
        table.add_column("Seen", justify="right")

        # Sort by most-recently-seen first, cap display at 50 rows
        ordered = sorted(
            self._state.items(),
            key=lambda item: self._last_seen.get(item[0], 0.0),
            reverse=True,
        )
        for icao, state in ordered[:50]:
            seen_ago = now - self._last_seen.get(icao, now)
            table.add_row(
                icao,
                str(state.get("callsign") or ""),
                str(state.get("altitude") or ""),
                str(state.get("groundspeed") or ""),
                (f"{state['track']:.1f}" if state.get("track") is not None else ""),
                (
                    f"{state['latitude']:.4f}"
                    if state.get("latitude") is not None
                    else ""
                ),
                (
                    f"{state['longitude']:.4f}"
                    if state.get("longitude") is not None
                    else ""
                ),
                f"{seen_ago:.1f}s",
            )
        return table
