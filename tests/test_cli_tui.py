"""Unit tests for the optional Textual live view."""

from __future__ import annotations

import argparse
import threading

from pyModeS import PipeDecoder
from pyModeS.cli._source import NetworkSource
from pyModeS.cli._tui import ModesLiveApp, _pick_columns, _row_for_state


def _app() -> ModesLiveApp:
    return ModesLiveApp(
        argparse.Namespace(),
        PipeDecoder(),
        NetworkSource("example.invalid", 10006),
    )


def test_column_breakpoints() -> None:
    assert len(_pick_columns(70)) == 7
    assert len(_pick_columns(100)) == 10
    assert len(_pick_columns(101)) == 18


def test_row_rendering_uses_decoded_state() -> None:
    columns = ("icao", "callsign", "lat", "alt", "gs", "trk")
    cells = _row_for_state(
        "abc123",
        {
            "callsign": "TEST123",
            "latitude": 52.12345,
            "altitude": 12000,
            "groundspeed": 250.4,
            "track": 90.2,
        },
        1000.0,
        columns,
    )
    assert cells == ["ABC123", "TEST123", "52.123", "12000", "250", "90"]


def test_snapshot_copies_nested_aircraft_state() -> None:
    app = _app()
    app._record_decoded({"icao": "ABC123", "callsign": "FIRST"}, 1.0)
    snapshot = app._snapshot_state()

    app._record_decoded({"icao": "ABC123", "callsign": "SECOND"}, 2.0)

    assert snapshot[0][1]["callsign"] == "FIRST"
    assert app._snapshot_state()[0][1]["callsign"] == "SECOND"


def test_snapshot_is_safe_during_worker_updates() -> None:
    app = _app()

    def update() -> None:
        for i in range(2_000):
            app._record_decoded({"icao": f"{i % 200:06X}", "altitude": i}, float(i))

    worker = threading.Thread(target=update)
    worker.start()
    while worker.is_alive():
        snapshot = app._snapshot_state()
        for _, state in snapshot:
            assert "_last_seen" in state
    worker.join()

    assert len(app._snapshot_state()) == 200
