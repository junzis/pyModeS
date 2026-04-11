"""Main loop for ``modes live`` — streaming TCP decode.

Pipeline::

    NetworkSource (TCP + beast frame parser)
        │ yields (hex, timestamp)
        ▼
    PipeDecoder
        │ per-ICAO state, CPR pair matching, TTL eviction
        ▼
    Sink (JsonLinesSink | TeeSink | NullSink | TuiSink)

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


class _TuiImportError(RuntimeError):
    """Raised when --tui is set but `rich` is missing."""


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

    # Construct the sink
    try:
        sink = _build_sink(args)
    except _TuiImportError as e:
        print(str(e), file=sys.stderr)
        return 3

    # Signal handling
    stop = _StopFlag()
    _install_signal_handlers(stop)

    # Network source. In --tui mode we suppress every stderr
    # notification (format detection, reconnect warnings, periodic
    # stats) because rich.live.Live holds the alternate screen
    # buffer and a raw `print(..., file=sys.stderr)` writes into
    # the middle of rich's render area, corrupting the cursor
    # tracking and leaving the display stuck. The TUI footer
    # already surfaces the running stats via TuiSink's table
    # title, so no information is lost.
    silence_stderr = args.quiet or args.tui
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

    # Enter the sink as a context manager when it supports one
    # (TuiSink holds a rich.live.Live alt-screen). Non-TUI sinks
    # are plain objects with just write()/close() — take the
    # direct path so we can close them in the finally clause.
    try:
        if hasattr(sink, "__enter__"):
            with sink:
                code = _loop()
        else:
            try:
                code = _loop()
            finally:
                sink.close()
    except BaseException:
        # TuiSink's __exit__ will restore the terminal; still
        # re-raise so callers see the underlying error.
        raise

    # Final stats line lands AFTER the TUI's alt-screen has been
    # restored (either because __exit__ ran above, or because we
    # used the non-TUI path), so it appears on the normal terminal.
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


def _build_sink(args: argparse.Namespace) -> Any:
    """Construct the appropriate sink for the given args.

    Raises _TuiImportError when --tui is set but the `rich` optional
    extra is not installed. Caller translates that into exit code 3.
    """
    if args.tui:
        # Lazy-import _tui.py so we only pay the rich import cost
        # when the user actually asks for the TUI.
        try:
            from pymodes.cli._tui import TuiSink
        except ImportError as e:
            raise _TuiImportError(
                "modes live: error: --tui requires the optional `rich` package.\n"
                '  install via: pip install "pymodes[tui]"\n'
                f"  (original import error: {e})"
            ) from e
        return TuiSink()

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
