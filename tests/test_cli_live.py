"""Tests for `modes live` main loop."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import pytest


class FakeSource:
    """Test double that yields a canned list of (hex, timestamp) tuples."""

    def __init__(self, frames: list[tuple[str, float]]) -> None:
        self._frames = frames

    def __iter__(self):
        yield from self._frames


class TestLiveMainLoop:
    @pytest.fixture(autouse=True)
    def _patch_source(self, monkeypatch):
        """Replace NetworkSource with a FakeSource for every test."""
        import pyModeS.cli.live as live_mod

        def _fake_network_source(host, port, **kwargs):
            return self._fake_source

        monkeypatch.setattr(live_mod, "NetworkSource", _fake_network_source)
        yield

    def test_basic_firehose(self, capsys):
        self._fake_source = FakeSource(
            [
                ("8D406B902015A678D4D220AA4BDA", 1000.0),
                ("8D485020994409940838175B284F", 1001.0),
            ]
        )
        from pyModeS.cli import main

        code = main(["live", "--network", "host.example:30005"])
        assert code == 0
        captured = capsys.readouterr()
        lines = [line for line in captured.out.splitlines() if line.strip()]
        assert len(lines) == 2
        data0 = json.loads(lines[0])
        assert data0["icao"] == "406B90"
        data1 = json.loads(lines[1])
        assert data1["icao"] == "485020"

    def test_dump_to_file(self, capsys, tmp_path):
        self._fake_source = FakeSource([("8D406B902015A678D4D220AA4BDA", 1000.0)])
        outfile = tmp_path / "dump.jsonl"
        from pyModeS.cli import main

        code = main(["live", "--network", "h:1", "--dump-to", str(outfile)])
        assert code == 0
        captured = capsys.readouterr()
        # Stdout got the line
        assert '"icao":"406B90"' in captured.out
        # File got the same line
        text = outfile.read_text()
        assert '"icao":"406B90"' in text

    def test_quiet_suppresses_stdout(self, capsys, tmp_path):
        self._fake_source = FakeSource([("8D406B902015A678D4D220AA4BDA", 1000.0)])
        outfile = tmp_path / "dump.jsonl"
        from pyModeS.cli import main

        code = main(
            [
                "live",
                "--network",
                "h:1",
                "--dump-to",
                str(outfile),
                "--quiet",
            ]
        )
        assert code == 0
        captured = capsys.readouterr()
        # stdout is empty
        assert captured.out == ""
        # file still got the line
        assert '"icao"' in outfile.read_text()

    def test_surface_ref_forwarded_to_pipe(self, capsys):
        # Use a real surface vector; lat/lon should appear in the output
        self._fake_source = FakeSource([("903a23ff426a4e65f7487a775d17", 1000.0)])
        from pyModeS.cli import main

        code = main(["live", "--network", "h:1", "--surface-ref", "LFBO"])
        assert code == 0
        captured = capsys.readouterr()
        line = captured.out.strip().splitlines()[-1]
        data = json.loads(line)
        assert abs(data["latitude"] - 43.62646) < 0.001

    def test_full_dict(self, capsys):
        from pyModeS._schema import _FULL_SCHEMA

        self._fake_source = FakeSource([("8D406B902015A678D4D220AA4BDA", 1000.0)])
        from pyModeS.cli import main

        code = main(["live", "--network", "h:1", "--full-dict"])
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out.strip().splitlines()[-1])
        for key in _FULL_SCHEMA:
            assert key in data

    def test_tui_without_textual_exits_three(self, capsys, monkeypatch):
        """--tui without the textual optional extra exits 3 with install hint."""
        self._fake_source = FakeSource([])
        # Force the textual import to fail as if it's not installed.
        # Patching builtins.__import__ is sticky; instead, inject a
        # fake that raises when `pyModeS.cli._tui` is imported.
        import sys as _sys

        class _RaisingFinder:
            def find_spec(self, name, path=None, target=None):
                if name == "pyModeS.cli._tui":
                    raise ImportError("no textual installed")
                return None

        monkeypatch.setattr(_sys, "meta_path", [_RaisingFinder(), *_sys.meta_path])
        # Also clear any cached import
        _sys.modules.pop("pyModeS.cli._tui", None)

        from pyModeS.cli import main

        code = main(["live", "--network", "h:1", "--tui"])
        assert code == 3
        captured = capsys.readouterr()
        assert "pyModeS[tui]" in captured.err
        assert "textual" in captured.err


class TestLiveGracefulShutdown:
    def test_sigint_exits_zero(self, monkeypatch):
        """A SIGINT during the live loop triggers graceful exit 0.

        We can't actually deliver SIGINT to a helper-thread's sleep
        from the main thread portably, so this test exercises the
        stop-flag branch directly: it monkeypatches the source to
        yield one frame then set the module-level stop flag.
        """
        import pyModeS.cli.live as live_mod

        stop_holder: dict[str, Any] = {}

        class SlowSource:
            def __iter__(self):
                yield ("8D406B902015A678D4D220AA4BDA", 1000.0)
                # Wait for the test to flip the stop flag
                for _ in range(500):
                    flag = stop_holder.get("flag")
                    if flag is not None and flag.stopped:
                        break
                    time.sleep(0.01)

        def _fake_network_source(host, port, **kwargs):
            return SlowSource()

        original_install = live_mod._install_signal_handlers

        def capturing_install(stop):
            stop_holder["flag"] = stop
            original_install(stop)

        monkeypatch.setattr(live_mod, "NetworkSource", _fake_network_source)
        monkeypatch.setattr(live_mod, "_install_signal_handlers", capturing_install)

        from pyModeS.cli import main

        result: dict[str, Any] = {"code": None}

        def runner():
            result["code"] = main(["live", "--network", "h:1"])

        t = threading.Thread(target=runner)
        t.start()
        # Wait a bit for the source to produce its first frame and
        # the stop flag to be captured
        time.sleep(0.1)
        assert "flag" in stop_holder, "stop flag was not captured"
        stop_holder["flag"].stopped = True
        t.join(timeout=5)
        assert not t.is_alive(), "main() did not exit after stop flag set"
        assert result["code"] == 0
