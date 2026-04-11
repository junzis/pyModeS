"""Interactive textual-based TUI for ``modes live --tui``.

Drop-in replacement for the old rich-based TuiSink. Gives users
keyboard navigation (j/k/g/G), sort cycling (s), sort direction
toggle (r), and incremental search (/) over the live aircraft
table — matching the UX of jet1090's Rust/ratatui console.

This module is lazy-imported ONLY when --tui is set, so users
without the ``pymodes[tui]`` extra pay zero cost. The caller in
``pymodes.cli.live`` catches the ImportError and surfaces a clean
exit-3 with an install hint.

Architecture:

- ``ModesLiveApp`` is a textual App with a single DataTable widget.
- On mount, we spawn a daemon worker thread that drains the
  blocking ``NetworkSource`` iterator, calls ``PipeDecoder.decode``
  on each frame, and merges the decoded fields into a shared
  ``dict[icao, state]`` that the UI thread reads from.
- A 250 ms ``set_interval`` timer snapshots the shared dict,
  applies any active search filter and sort, and rewrites the
  DataTable rows. At 4 Hz with <=500 aircraft this is O(2000
  cells/second) — negligible cost.
- Terminal width changes trigger a column-set swap (7 / 10 / 18
  columns) matching jet1090's breakpoints.

Thread safety: the shared dict sees single-key writes from the
worker thread (GIL-atomic under CPython) and snapshot reads from
the UI thread via ``list(state.items())``. No locks needed.
"""

from __future__ import annotations

import argparse
import contextlib
import threading
from datetime import UTC, datetime
from typing import Any, ClassVar

# textual is optional; caller guards the import.
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Footer, Header, Input

from pymodes import PipeDecoder
from pymodes.cli._source import NetworkSource, UnsupportedStreamError

# Fields the worker thread copies out of each decoded message into
# the per-ICAO shared state dict. Covers every column across every
# responsive breakpoint. Comm-B and ADS-B use slightly different
# names for several concepts (vertical rate, track, altitude);
# both are captured so the UI can render whichever was most
# recently observed.
_TRACKED_FIELDS: tuple[str, ...] = (
    "callsign",
    "squawk",
    "latitude",
    "longitude",
    "altitude",
    "selected_altitude_mcp",
    "selected_altitude_fms",
    "groundspeed",
    "true_airspeed",
    "indicated_airspeed",
    "mach",
    "vertical_rate",
    "baro_vertical_rate",
    "inertial_vertical_rate",
    "track",
    "true_track",
    "heading",
    "magnetic_heading",
    "roll",
    "nac_p",
)

# Sort keys cycled by the `s` binding. Order mirrors the sequence
# jet1090 exposes in its console.
_SORT_KEYS: tuple[str, ...] = (
    "last_seen",
    "icao",
    "callsign",
    "altitude",
    "groundspeed",
    "vertical_rate",
)

# Human labels shown in the SUB_TITLE for the currently active
# sort key. Keys match _SORT_KEYS.
_SORT_LABELS: dict[str, str] = {
    "last_seen": "last",
    "icao": "icao",
    "callsign": "callsign",
    "altitude": "alt",
    "groundspeed": "gs",
    "vertical_rate": "vrate",
}

# Aircraft older than this are hidden from the table (matches
# PipeDecoder.eviction_ttl default of 300 seconds).
_INTERACTIVE_EXPIRE: float = 300.0


def _fmt_float(v: Any, digits: int = 4) -> str:
    """Format a float with a fixed decimal count; empty if None."""
    if v is None:
        return ""
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return ""


def _fmt_int(v: Any) -> str:
    """Format an int; empty if None."""
    if v is None:
        return ""
    try:
        return f"{int(v)}"
    except (TypeError, ValueError):
        return ""


def _fmt_last_seen(v: Any, now: float) -> str:
    """Seconds-since string; empty when <=1s old (avoids 0s flicker)."""
    if v is None:
        return ""
    try:
        age = now - float(v)
    except (TypeError, ValueError):
        return ""
    if age <= 1.0:
        return ""
    return f"{int(age)}s"


def _fmt_time(v: Any) -> str:
    """Render a unix timestamp as HH:MM UTC; empty if None."""
    if v is None:
        return ""
    try:
        return datetime.fromtimestamp(float(v), tz=UTC).strftime("%H:%M")
    except (TypeError, ValueError, OSError):
        return ""


# Column sets per terminal-width bracket. Keys are the breakpoint
# upper bounds (inclusive); the values are the ordered column id
# lists. ``_COLUMNS_XL`` is used for >130.
_COLUMNS_XS: tuple[str, ...] = (
    "icao",
    "callsign",
    "lat",
    "lon",
    "alt",
    "gs",
    "trk",
)
_COLUMNS_SM: tuple[str, ...] = (
    "icao",
    "callsign",
    "sqwk",
    "lat",
    "lon",
    "alt",
    "gs",
    "vrate",
    "trk",
    "last",
)
_COLUMNS_LG: tuple[str, ...] = (
    "icao",
    "callsign",
    "sqwk",
    "lat",
    "lon",
    "alt",
    "sel",
    "gs",
    "tas",
    "ias",
    "mach",
    "vrate",
    "trk",
    "hdg",
    "roll",
    "nac",
    "last",
    "first",
)


def _pick_columns(width: int) -> tuple[str, ...]:
    """Return the column id tuple appropriate for ``width``."""
    if width <= 70:
        return _COLUMNS_XS
    if width <= 100:
        return _COLUMNS_SM
    return _COLUMNS_LG


def _row_for_state(
    icao: str,
    state: dict[str, Any],
    now: float,
    columns: tuple[str, ...],
) -> list[str]:
    """Build the ordered cell value list for one aircraft row.

    The output length is exactly ``len(columns)`` so the caller can
    splat it into ``DataTable.add_row``.
    """
    cells: list[str] = []
    for col in columns:
        if col == "icao":
            cells.append(icao.upper())
        elif col == "callsign":
            cells.append(str(state.get("callsign") or ""))
        elif col == "sqwk":
            cells.append(str(state.get("squawk") or ""))
        elif col == "lat":
            cells.append(_fmt_float(state.get("latitude"), 3))
        elif col == "lon":
            cells.append(_fmt_float(state.get("longitude"), 3))
        elif col == "alt":
            cells.append(_fmt_int(state.get("altitude")))
        elif col == "sel":
            cells.append(
                _fmt_int(
                    state.get("selected_altitude_mcp")
                    or state.get("selected_altitude_fms")
                )
            )
        elif col == "gs":
            cells.append(_fmt_int(state.get("groundspeed")))
        elif col == "tas":
            cells.append(_fmt_int(state.get("true_airspeed")))
        elif col == "ias":
            cells.append(_fmt_int(state.get("indicated_airspeed")))
        elif col == "mach":
            cells.append(_fmt_float(state.get("mach"), 2))
        elif col == "vrate":
            cells.append(
                _fmt_int(state.get("vertical_rate") or state.get("baro_vertical_rate"))
            )
        elif col == "trk":
            cells.append(_fmt_int(state.get("track") or state.get("true_track")))
        elif col == "hdg":
            cells.append(
                _fmt_int(state.get("heading") or state.get("magnetic_heading"))
            )
        elif col == "roll":
            cells.append(_fmt_float(state.get("roll"), 1))
        elif col == "nac":
            cells.append(_fmt_int(state.get("nac_p")))
        elif col == "last":
            cells.append(_fmt_last_seen(state.get("_last_seen"), now))
        elif col == "first":
            cells.append(_fmt_time(state.get("_first_seen")))
        else:  # pragma: no cover - defensive
            cells.append("")
    return cells


def _sort_value(icao: str, state: dict[str, Any], key: str) -> Any:
    """Return a sortable value for the given sort key.

    Missing fields always sort to the end (largest value under
    ascending, smallest under descending).
    """
    if key == "last_seen":
        return state.get("_last_seen", 0.0)
    if key == "icao":
        return icao
    if key == "callsign":
        return state.get("callsign") or "\uffff"
    if key == "altitude":
        v = state.get("altitude")
        return float("inf") if v is None else float(v)
    if key == "groundspeed":
        v = state.get("groundspeed")
        return float("inf") if v is None else float(v)
    if key == "vertical_rate":
        v = state.get("vertical_rate") or state.get("baro_vertical_rate")
        return float("inf") if v is None else float(v)
    return 0


class ModesLiveApp(App[int]):
    """Interactive textual App for ``modes live --tui``.

    Owns the terminal, spawns a worker thread to drain
    ``NetworkSource``, and paints the shared per-aircraft state
    dict into a ``DataTable`` on a 4 Hz timer.
    """

    TITLE = "pymodes live"

    CSS = """
    Screen {
        layout: vertical;
    }
    #aircraft-container {
        height: 1fr;
        padding: 0 1;
    }
    DataTable {
        height: 1fr;
        border: round $accent;
    }
    #search {
        height: 1;
        border: none;
        background: $surface;
    }
    """

    # q/escape are NOT priority so the Input widget receives them
    # while the user is typing a search query. action_quit is
    # context-aware: it cancels an active search first and only
    # exits the app when the search bar is hidden.
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "cursor_home", "Top"),
        Binding("G", "cursor_end", "Bottom"),
        Binding("s", "cycle_sort", "Sort"),
        Binding("r", "toggle_sort_dir", "Reverse"),
        Binding("slash", "toggle_search", "Search"),
    ]

    def __init__(
        self,
        args: argparse.Namespace,
        pipe: PipeDecoder,
        source: NetworkSource,
    ) -> None:
        super().__init__()
        self._args = args
        self._pipe = pipe
        self._source = source
        self._host = source.host
        self._port = source.port
        self.sub_title = f"{self._host}:{self._port}"

        # Shared per-aircraft state. Writes from the worker thread
        # are single-key dict assignments (GIL-atomic under
        # CPython); reads from the UI thread snapshot via
        # ``list(state.items())`` to dodge "dict changed during
        # iteration" errors.
        self._state: dict[str, dict[str, Any]] = {}
        self._msg_count: int = 0
        self._worker_error: BaseException | None = None
        self._stop_flag: bool = False
        self._worker_thread: threading.Thread | None = None

        # UI state. Default sort = icao ascending: gives a stable
        # row order so rows don't visibly jump every tick. Sorting
        # by last_seen (the old default) caused every arriving
        # message to reshuffle the table and flash the view.
        self._sort_index: int = _SORT_KEYS.index("icao")
        self._sort_asc: bool = True
        self._search_query: str = ""
        self._search_backup: str = ""
        self._search_visible: bool = False
        self._columns: tuple[str, ...] = _COLUMNS_SM
        self._last_width: int = -1

        # Cache of what's currently painted in the DataTable, used
        # to drive diff updates so a per-tick refresh only touches
        # cells whose values actually changed. A full clear+re-add
        # is done only when the set or order of rows changes.
        self._rendered_keys: list[str] = []
        self._rendered_columns: tuple[str, ...] = ()
        self._rendered_cells: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Composition + lifecycle
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="aircraft-container"):
            yield DataTable(
                id="aircraft",
                cursor_type="row",
                zebra_stripes=True,
            )
        yield Input(id="search", placeholder="search icao or callsign")
        yield Footer()

    def on_mount(self) -> None:
        # Hide the inline search bar until the user presses "/".
        self.query_one("#search", Input).display = False

        # Configure the DataTable columns based on the initial
        # terminal width.
        self._apply_column_set(self.size.width)

        # Start the worker thread that drains NetworkSource.
        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="pymodes-live-tui-worker"
        )
        self._worker_thread.start()

        # 4 Hz table refresh and 1 Hz title refresh.
        self.set_interval(0.25, self._refresh_table)
        self.set_interval(1.0, self._refresh_title)

    def on_unmount(self) -> None:
        # Signal the worker to stop and try to unblock a recv() by
        # closing the underlying socket. The thread is a daemon so
        # if it stays blocked (e.g. recv() not raising on close on
        # some platforms) Python will still exit.
        self._stop_flag = True
        sock = getattr(self._source, "_sock", None)
        if sock is not None:
            with contextlib.suppress(Exception):
                sock.close()

    def on_resize(self, event: Any) -> None:
        # Re-lay out columns if the width bracket changed.
        self._apply_column_set(self.size.width)

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        try:
            for hex_msg, ts in self._source:
                if self._stop_flag:
                    break
                try:
                    decoded = self._pipe.decode(hex_msg, timestamp=ts)
                except Exception:
                    self._msg_count += 1
                    continue
                self._msg_count += 1
                icao = decoded.get("icao")
                if not icao:
                    continue
                state = self._state.get(icao)
                if state is None:
                    state = {"_first_seen": ts, "_last_seen": ts}
                    self._state[icao] = state
                for key in _TRACKED_FIELDS:
                    val = decoded.get(key)
                    if val is not None:
                        state[key] = val
                state["_last_seen"] = ts
        except UnsupportedStreamError as e:
            self._worker_error = e
            with contextlib.suppress(Exception):
                self.call_from_thread(self.exit, 2)
        except Exception as e:
            if self._stop_flag:
                return
            self._worker_error = e
            with contextlib.suppress(Exception):
                self.call_from_thread(self.exit, 1)

    # ------------------------------------------------------------------
    # Periodic refresh
    # ------------------------------------------------------------------

    def _apply_column_set(self, width: int) -> None:
        columns = _pick_columns(width)
        if columns == self._columns and self._last_width >= 0:
            return
        self._columns = columns
        self._last_width = width
        try:
            table = self.query_one("#aircraft", DataTable)
        except Exception:
            return
        table.clear(columns=True)
        table.add_columns(*columns)
        # Column set changed → invalidate the render cache so the
        # next _refresh_table does a full rebuild.
        self._rendered_keys = []
        self._rendered_columns = columns
        self._rendered_cells = {}

    def _refresh_table(self) -> None:
        try:
            table = self.query_one("#aircraft", DataTable)
        except Exception:
            return

        # React to width bracket changes even if on_resize didn't
        # fire (textual occasionally coalesces resize events).
        if _pick_columns(self.size.width) != self._columns:
            self._apply_column_set(self.size.width)

        now = _now()
        cutoff = now - _INTERACTIVE_EXPIRE

        # Snapshot — dict may mutate from the worker thread between
        # calls, so copy the items out first.
        snapshot: list[tuple[str, dict[str, Any]]] = list(self._state.items())

        # Filter
        filtered: list[tuple[str, dict[str, Any]]] = []
        query = self._search_query.lower()
        for icao, state in snapshot:
            last_seen = state.get("_last_seen", 0.0)
            if last_seen < cutoff:
                continue
            if query:
                callsign = str(state.get("callsign") or "").lower()
                if query not in icao.lower() and query not in callsign:
                    continue
            filtered.append((icao, state))

        # Sort
        key = _SORT_KEYS[self._sort_index]
        filtered.sort(key=lambda item: _sort_value(item[0], item[1], key))
        if not self._sort_asc:
            filtered.reverse()

        desired_keys = [icao for icao, _ in filtered]
        columns = self._columns

        # Fast path: if the set AND order of rows is unchanged,
        # update only cells whose values actually changed. Avoids
        # the clear-and-rebuild that wipes cursor/scroll state and
        # makes the whole table flash every tick.
        if desired_keys == self._rendered_keys and columns == self._rendered_columns:
            for icao, state in filtered:
                new_cells = _row_for_state(icao, state, now, columns)
                old_cells = self._rendered_cells.get(icao)
                if old_cells == new_cells:
                    continue
                try:
                    row_idx = table.get_row_index(icao)
                except Exception:
                    continue
                for col_idx, new_val in enumerate(new_cells):
                    if (
                        old_cells is not None
                        and col_idx < len(old_cells)
                        and old_cells[col_idx] == new_val
                    ):
                        continue
                    with contextlib.suppress(Exception):
                        table.update_cell_at(
                            Coordinate(row_idx, col_idx),
                            new_val,
                            update_width=False,
                        )
                self._rendered_cells[icao] = new_cells
            return

        # Rebuild path: row set or order changed (new aircraft,
        # expired aircraft, user-triggered sort change). Save the
        # ICAO under the cursor and the scroll offset so the view
        # stays anchored across the rebuild.
        prev_icao: str | None = None
        try:
            if table.row_count and table.cursor_row >= 0:
                cell_key = table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0))
                prev_icao = cell_key.row_key.value
        except Exception:
            pass
        prev_scroll_y = table.scroll_y

        table.clear(columns=False)
        rendered_cells: dict[str, list[str]] = {}
        for icao, state in filtered:
            cells = _row_for_state(icao, state, now, columns)
            table.add_row(*cells, key=icao)
            rendered_cells[icao] = cells
        self._rendered_cells = rendered_cells
        self._rendered_keys = desired_keys
        self._rendered_columns = columns

        # Restore cursor by ICAO key (not by row index — indices
        # shift after a re-sort). scroll=False keeps the viewport
        # where it was; scroll_to below then pins it exactly.
        if prev_icao is not None:
            with contextlib.suppress(Exception):
                new_row = table.get_row_index(prev_icao)
                table.move_cursor(row=new_row, scroll=False)
        with contextlib.suppress(Exception):
            table.scroll_to(y=prev_scroll_y, animate=False)

    def _refresh_title(self) -> None:
        now = _now()
        cutoff = now - _INTERACTIVE_EXPIRE
        n_aircraft = sum(
            1
            for st in list(self._state.values())
            if st.get("_last_seen", 0.0) >= cutoff
        )
        sort_label = _SORT_LABELS.get(_SORT_KEYS[self._sort_index], "?")
        direction = "asc" if self._sort_asc else "desc"
        search_bit = f" /{self._search_query}" if self._search_query else ""
        self.sub_title = (
            f"{self._host}:{self._port}  "
            f"{n_aircraft} a/c  {self._msg_count} msgs  "
            f"sort={sort_label}:{direction}{search_bit}"
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_cursor_down(self) -> None:
        try:
            table = self.query_one("#aircraft", DataTable)
        except Exception:
            return
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        try:
            table = self.query_one("#aircraft", DataTable)
        except Exception:
            return
        table.action_cursor_up()

    def action_cursor_home(self) -> None:
        try:
            table = self.query_one("#aircraft", DataTable)
        except Exception:
            return
        if table.row_count:
            with contextlib.suppress(Exception):
                table.move_cursor(row=0)

    def action_cursor_end(self) -> None:
        try:
            table = self.query_one("#aircraft", DataTable)
        except Exception:
            return
        if table.row_count:
            with contextlib.suppress(Exception):
                table.move_cursor(row=table.row_count - 1)

    def action_cycle_sort(self) -> None:
        self._sort_index = (self._sort_index + 1) % len(_SORT_KEYS)
        self._refresh_table()
        self._refresh_title()

    def action_toggle_sort_dir(self) -> None:
        self._sort_asc = not self._sort_asc
        self._refresh_table()
        self._refresh_title()

    def action_toggle_search(self) -> None:
        try:
            search = self.query_one("#search", Input)
        except Exception:
            return
        if not self._search_visible:
            # Opening the bar: remember the committed query so
            # escape can roll back if the user cancels.
            self._search_backup = self._search_query
            search.value = self._search_query
            search.display = True
            self._search_visible = True
        search.focus()

    async def action_quit(self) -> None:
        # Context-aware: while the search bar is open, escape/q
        # discards the in-progress query and closes the bar rather
        # than quitting the app. This lets the Input widget also
        # receive q as a typed character (q is not priority).
        if self._search_visible:
            self._search_query = self._search_backup
            self._hide_search()
            self._refresh_table()
            self._refresh_title()
            return
        self.exit(0)

    def _hide_search(self) -> None:
        try:
            search = self.query_one("#search", Input)
            search.display = False
        except Exception:
            pass
        self._search_visible = False
        with contextlib.suppress(Exception):
            self.query_one("#aircraft", DataTable).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        # Live search: filter the table as the user types.
        if event.input.id != "search":
            return
        self._search_query = event.value
        self._refresh_table()
        self._refresh_title()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Enter commits the query (already applied via
        # on_input_changed). Hide the bar and return focus to
        # the table.
        if event.input.id != "search":
            return
        self._hide_search()


def _now() -> float:
    import time

    return time.time()


def run_tui_app(
    args: argparse.Namespace,
    pipe: PipeDecoder,
    source: NetworkSource,
) -> int:
    """Run the textual App until the user quits.

    Returns the exit code: 0 for a clean quit, 1 for an internal
    error, 2 for an UnsupportedStreamError raised by the worker
    thread.
    """
    app = ModesLiveApp(args, pipe, source)
    exit_code = app.run()
    err = app._worker_error
    if err is not None:
        import sys

        if isinstance(err, UnsupportedStreamError):
            print(f"modes live: error: {err}", file=sys.stderr)
            return 2
        print(f"modes live: error: {err}", file=sys.stderr)
        return 1
    if isinstance(exit_code, int):
        return exit_code
    return 0
