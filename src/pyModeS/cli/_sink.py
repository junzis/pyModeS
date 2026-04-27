"""Output sinks for ``modes live``.

Three sink classes sharing a common interface:

- ``JsonLinesSink`` — writes compact JSON lines to a text file handle
  (stdout by default). One line per decoded message.
- ``TeeSink`` — wraps a primary sink and mirrors every write to a
  secondary sink (typically stdout + a file).
- ``NullSink`` — discards every write (used by ``--quiet``).

The rich-based ``TuiSink`` lives in ``_tui.py`` (lazy-imported only
when ``--tui`` is set) so that users without the ``pyModeS[tui]``
extra don't pay the ``rich`` import cost on every ``modes live`` run.

All sinks implement ``write(decoded) -> None`` and ``close() -> None``.
The live main loop calls ``write`` for every decoded message and
``close`` during graceful shutdown.
"""

from __future__ import annotations

import os
import csv
import json
import sys
from datetime import datetime
from typing import IO, Protocol

from pyModeS.message import Decoded


class Sink(Protocol):
    def write(self, decoded: Decoded) -> None: ...
    def close(self) -> None: ...


class JsonLinesSink:
    """Write compact JSON lines to a text stream (default: stdout).

    Each ``write(decoded)`` call emits exactly one line to the stream
    with no indentation. The stream is flushed after every write so
    tailers see output immediately (important for ``--dump-to`` file
    consumers running ``tail -f``).
    """

    def __init__(self, stream: IO[str] | None = None) -> None:
        self._stream = stream if stream is not None else sys.stdout
        self._owns_stream = False

    @classmethod
    def to_file(cls, path: str) -> JsonLinesSink:
        """Open a file in line-buffered mode and wrap it."""
        # buffering=1 → line buffered (text mode)
        fh = open(path, "w", buffering=1)  # noqa: SIM115
        sink = cls(fh)
        sink._owns_stream = True
        return sink

    def write(self, decoded: Decoded) -> None:
        line = json.dumps(decoded, separators=(",", ":"), default=str)
        self._stream.write(line)
        self._stream.write("\n")
        self._stream.flush()

    def close(self) -> None:
        if self._owns_stream:
            self._stream.close()
            
SKIP_FIELDS = {"df", "raw_msg", "bds"}

class CsvSink:
    def __init__(self, path: str, ac_filter: str | None = None) -> None:
        self._ac_filter = ac_filter.upper() if ac_filter is not None else None
        base = path.removesuffix(".csv")
        ts_now = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("dump", exist_ok=True)
        
        if self._ac_filter is not None:
            base = os.path.join("dump", f"{ts_now}_{base}_{self._ac_filter}")
        else:
             base = os.path.join("dump", f"{ts_now}_{base}")
            
        self._fh_decoded = open(base + ".csv", "w", buffering=1, newline="")
        self._fh_raw = open(base + "_raw.csv", "w", buffering=1, newline="")

        self._writer_decoded = csv.writer(self._fh_decoded, lineterminator="\n")
        self._writer_raw = csv.writer(self._fh_raw, lineterminator="\n")

        self._writer_decoded.writerow(["timestamp", "icao", "field", "value"])
        self._writer_raw.writerow(["timestamp", "icao", "df", "raw_msg"])

        self._fh_decoded.flush()
        self._fh_raw.flush()

    def write(self, decoded: Decoded) -> None:
        if self._ac_filter is not None and decoded.get("icao", "").upper() != self._ac_filter:
            return

        ts = decoded.get("timestamp", "")
        ts_formatted = datetime.fromtimestamp(ts).strftime("%Y%m%d-%H:%M:%S.%f") if ts != "" else ""
        icao = decoded.get("icao", "")

        self._writer_raw.writerow([ts_formatted, icao, decoded.get("df", ""), decoded.get("raw_msg", "")])

        for field, value in decoded.items():
            if field in ("timestamp", "icao") or field in SKIP_FIELDS or value is None:
                continue
            self._writer_decoded.writerow([ts_formatted, icao, field, value])

        self._fh_decoded.flush()
        self._fh_raw.flush()

    def close(self) -> None:
        self._fh_decoded.close()
        self._fh_raw.close()


class TeeSink:
    """Wraps a primary sink and mirrors every write to a secondary.

    Used by ``modes live --dump-to FILE`` to send JSON lines both to
    stdout and to the dump file. Closing the tee closes both underlying
    sinks.
    """

    def __init__(self, primary: Sink, secondary: Sink) -> None:
        self._primary = primary
        self._secondary = secondary

    def write(self, decoded: Decoded) -> None:
        self._primary.write(decoded)
        self._secondary.write(decoded)

    def close(self) -> None:
        try:
            self._primary.close()
        finally:
            self._secondary.close()


class NullSink:
    """Sink that discards every write. Used by ``--quiet`` with no dump."""

    def write(self, decoded: Decoded) -> None:
        pass

    def close(self) -> None:
        pass
