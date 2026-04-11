"""Main loop for ``modes live`` — streaming TCP decode.

Pipeline (non-TUI path)::

    NetworkSource (TCP + beast frame parser)
        │ yields (hex, timestamp)
        ▼
    PipeDecoder
        │ per-ICAO state, CPR pair matching, TTL eviction
        ▼
    Sink (JsonLinesSink | TeeSink | NullSink)

TUI path: the textual ``ModesLiveApp`` owns the NetworkSource and
PipeDecoder directly — sinks don't apply because the app paints a
DataTable rather than emitting JSON lines.

Signal handling: SIGINT and SIGTERM set a stop flag that the iterator
loop checks after each message. The main loop then flushes the sink,
closes the source, emits a final stats line to stderr, and returns 0.

Full tracebacks only with ``PYMODES_CLI_DEBUG=1`` in the environment.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from types import FrameType
from typing import Any

from pymodes import PipeDecoder
from pymodes.cli._sink import JsonLinesSink, NullSink, TeeSink
from pymodes.cli._source import NetworkSource, UnsupportedStreamError


class _StopFlag:
    """Mutable flag so signal handlers can signal the main loop."""

    def __init__(self) -> None:
        self.stopped = False


def run(args: argparse.Namespace) -> int:
    """Entry point for ``modes live``. Returns exit code."""
    host, port = _parse_network(args.network)
    if host is None:
        print(
            "modes live: error: --network must be in HOST:PORT form "
            f"(got {args.network!r})",
            file=sys.stderr,
        )
        return 2

    surface_ref = _parse_surface_ref(args.surface_ref)

    pipe = PipeDecoder(surface_ref=surface_ref, full_dict=args.full_dict)

    # TUI path takes its own branch — textual owns the event loop
    # and drives the source + pipe itself, so the sink pipeline
    # doesn't apply. We lazy-import _tui so the textual package is
    # only required when --tui is actually set; if it's missing we
    # emit an exit-3 with an install hint.
    if args.tui:
        try:
            from pymodes.cli._tui import run_tui_app
        except ImportError as e:
            print(
                "modes live: error: --tui requires the optional "
                "`textual` package.\n"
                '  install via: pip install "pymodes[tui]"\n'
                f"  (original import error: {e})",
                file=sys.stderr,
            )
            return 3
        # silent=True because textual owns the terminal; any stderr
        # writes inside the alt-screen would corrupt the display.
        source = NetworkSource(host, port, on_detect=None, silent=True)
        return run_tui_app(args, pipe, source)

    # Non-TUI sink pipeline
    sink = _build_sink(args)

    # Signal handling
    stop = _StopFlag()
    _install_signal_handlers(stop)

    silence_stderr = args.quiet
    source = NetworkSource(
        host,
        port,
        on_detect=(
            None
            if silence_stderr
            else lambda fmt: print(
                f"[pymodes.live] detected {fmt} format, resyncing",
                file=sys.stderr,
            )
        ),
        silent=silence_stderr,
    )

    last_stats_ts = time.monotonic()

    def _loop() -> int:
        nonlocal last_stats_ts
        try:
            for hex_msg, ts in source:
                if stop.stopped:
                    break
                result = pipe.decode(hex_msg, timestamp=ts)
                sink.write(result)
                now = time.monotonic()
                if now - last_stats_ts >= 60.0 and not silence_stderr:
                    _emit_stats_line(pipe, args.quiet)
                    last_stats_ts = now
        except UnsupportedStreamError as e:
            print(f"modes live: error: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            if os.environ.get("PYMODES_CLI_DEBUG") == "1":
                raise
            print(f"modes live: error: {e}", file=sys.stderr)
            return 1
        return 0

    try:
        code = _loop()
    finally:
        sink.close()

    _emit_stats_line(pipe, args.quiet, prefix="final")
    return code


def _parse_network(value: str) -> tuple[str | None, int]:
    """Split a HOST:PORT string. Returns (None, 0) on parse failure."""
    if ":" not in value:
        return None, 0
    host, _, port_str = value.rpartition(":")
    try:
        port = int(port_str)
    except ValueError:
        return None, 0
    return host, port


def _parse_surface_ref(value: str | None) -> Any:
    """Accept either an ICAO airport code or a 'lat,lon' string."""
    if value is None:
        return None
    if "," in value:
        lat_str, lon_str = value.split(",", 1)
        return (float(lat_str.strip()), float(lon_str.strip()))
    return value


def _build_sink(
    args: argparse.Namespace,
) -> JsonLinesSink | NullSink | TeeSink:
    """Construct the appropriate non-TUI sink for the given args.

    The TUI path does NOT go through this function — it has its
    own branch in ``run()`` that hands the NetworkSource straight
    to the textual App.
    """
    stdout_sink: JsonLinesSink | NullSink = (
        NullSink() if args.quiet else JsonLinesSink(sys.stdout)
    )
    if args.dump_to is not None:
        file_sink = JsonLinesSink.to_file(args.dump_to)
        return TeeSink(stdout_sink, file_sink)
    return stdout_sink


def _install_signal_handlers(stop: _StopFlag) -> None:
    def _handler(signum: int, frame: FrameType | None) -> None:
        stop.stopped = True

    # Only install in the main thread; tests that run main() in a
    # helper thread get a ValueError when calling signal.signal from
    # a non-main thread, so we catch it.
    try:
        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
    except ValueError:
        # Non-main thread (test harness); caller is responsible for
        # setting stop.stopped by other means.
        pass


def _emit_stats_line(pipe: PipeDecoder, quiet: bool, *, prefix: str = "") -> None:
    if quiet:
        return
    stats = pipe.stats
    label = f"[pymodes.live{' ' + prefix if prefix else ''}]"
    print(
        f"{label} {stats['total']} msgs, "
        f"{stats['decoded']} decoded, "
        f"{stats['crc_fail']} crc_fail, "
        f"{stats['pending_pairs']} pending pairs",
        file=sys.stderr,
    )
