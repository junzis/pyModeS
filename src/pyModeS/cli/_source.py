"""Network source + beast frame parser for ``modes live``.

``NetworkSource`` opens a TCP socket to a dump1090-style Mode-S feed,
verifies the stream is Mode-S Beast binary format, parses frames into
hex strings, and yields ``(hex_msg, timestamp)`` tuples.

Only Mode-S Beast binary is supported — that covers dump1090's default
port 30005, dump1090-fa, readsb, piaware, the AirSquitter receiver,
and most modern Mode-S feeds. The legacy AVR raw text format (port
30002) is out of scope for the alpha and can be added later if a user
requests it.

Beast format (per Mode-S Beast wire protocol, cross-checked against
FlightAware dump1090 ``net_io.c::modesReadFromClient``)::

    <ESC=0x1a> <TYPE> <MLAT:6 bytes> <SIG:1 byte> <PAYLOAD>

    TYPE values:
      0x31 "1": 2-byte Mode AC frame (skipped by this parser)
      0x32 "2": 7-byte Mode-S short frame (14 hex chars)
      0x33 "3": 14-byte Mode-S long frame (28 hex chars)
      0x34 "4": status/config (skipped by this parser)

    A literal 0x1a byte inside any body field (MLAT, signal, or
    payload) is encoded as two consecutive 0x1a bytes. The parser
    un-escapes across the entire body, not just the payload.
"""

from __future__ import annotations

import socket
import sys
import time
from collections.abc import Callable, Iterator

_DETECT_CAP = 16 * 1024  # give up on auto-detect after 16 KB

# Beast body lengths: MLAT(6) + SIGNAL(1) + PAYLOAD
_BODY_LEN_SHORT = 7 + 7  # type 0x32
_BODY_LEN_LONG = 7 + 14  # type 0x33
_BODY_LEN_MODE_AC = 7 + 2  # type 0x31

# MLAT counter tick rates we've seen in the wild:
#
#   12 MHz  — plain dump1090 / piaware / readsb. Counter is a
#             free-running local oscillator, wraps every ~6.5 h.
#
#   1 GHz   — radarcape / GNS AirSquitter / jetvision. Counter is
#             nanoseconds since UTC midnight (or a local-time
#             midnight — TU Delft's public feed is UTC+1 for
#             example), wraps at the next midnight.
#
# Rather than hard-coding 12 MHz and being wrong on radarcape
# feeds (wall-clock 83x too fast), NetworkSource auto-calibrates
# the rate from the observed delta between consecutive recv()
# bursts. See ``_rate_estimate`` in ``_read_loop``.
_MLAT_HZ_DUMP1090: float = 12_000_000.0
_MLAT_HZ_RADARCAPE: float = 1_000_000_000.0

# Minimum wall-clock delta between calibration samples — a new
# rate estimate is only accepted when the two anchoring bursts
# are spaced at least this far apart. Avoids dividing by tiny
# jitter in the wall-clock timestamps.
_CALIB_MIN_DELTA_S: float = 0.1


class UnsupportedStreamError(RuntimeError):
    """Raised when the network stream is not Mode-S Beast binary format."""


def _detect_format(chunk: bytes) -> bool:
    """Return True if a beast marker (0x1a) is found in ``chunk``.

    The caller reads more bytes as long as this returns False and
    gives up once ``_DETECT_CAP`` bytes have been scanned without
    finding a marker — at which point the stream is not beast Mode-S
    and NetworkSource raises UnsupportedStreamError.
    """
    return b"\x1a" in chunk


def _walk_body(buf: bytes, start: int, body_len: int) -> tuple[list[int], int]:
    """Walk the beast body starting at ``buf[start]`` un-escaping 0x1a 0x1a.

    Collects ``body_len`` un-escaped bytes (MLAT + SIG + PAYLOAD) and
    returns (body_bytes, next_index) where next_index points to the
    first byte after the last consumed byte in ``buf``.

    If the buffer ends before ``body_len`` un-escaped bytes have been
    collected, returns (partial_body, -1) to signal incompleteness.
    """
    body: list[int] = []
    j = start
    while j < len(buf) and len(body) < body_len:
        b = buf[j]
        if b == 0x1A:
            if j + 1 >= len(buf):
                # Dangling 0x1a at end of buffer — can't tell yet if
                # it's a literal (0x1a 0x1a) or the start of the next
                # frame. Wait for more bytes.
                return body, -1
            if buf[j + 1] == 0x1A:
                body.append(0x1A)
                j += 2
                continue
            # Unescaped 0x1a mid-body means the frame is truncated
            # and the 0x1a is the start of the next frame. Caller
            # will treat the current frame as incomplete.
            return body, -1
        body.append(b)
        j += 1
    if len(body) < body_len:
        return body, -1
    return body, j


def _parse_beast_buffer(buf: bytes) -> tuple[list[tuple[int, str]], bytes]:
    """Parse a beast-format byte buffer into frames + remainder.

    Scans forward through ``buf`` looking for frame starts (0x1a).
    For each recognised frame (types 0x32 and 0x33), un-escapes the
    body and extracts the 48-bit MLAT counter and the payload hex.
    Mode AC (0x31) and status (0x34) frames are skipped but still
    advance the parse cursor. Unknown type bytes are also skipped.

    Returns ``(frames, remainder)`` where ``frames`` is a list of
    ``(mlat_ticks, payload_hex)`` tuples and ``remainder`` is the
    tail of the buffer containing any incomplete trailing frame
    (from the last 0x1a that couldn't be fully parsed). The caller
    should prepend the remainder to the next chunk of bytes before
    the next parse.

    ``mlat_ticks`` is the big-endian 48-bit counter at the head of
    the beast body. Interpretation (unix time vs free-running) is
    receiver-dependent; :class:`NetworkSource` anchors the first
    frame's MLAT against ``time.time()`` and computes per-frame
    wall-clock from the 12 MHz tick rate used by dump1090-compatible
    feeds.
    """
    frames: list[tuple[int, str]] = []
    i = 0
    last_consumed = 0

    while i < len(buf):
        if buf[i] != 0x1A:
            i += 1
            continue

        # Potential frame start at buf[i]
        if i + 1 >= len(buf):
            # Dangling 0x1a, wait for more bytes
            break

        msg_type = buf[i + 1]

        if msg_type == 0x32:
            body_len = _BODY_LEN_SHORT
            payload_offset = 7
        elif msg_type == 0x33:
            body_len = _BODY_LEN_LONG
            payload_offset = 7
        elif msg_type == 0x31:
            # Mode A/C: skip
            body, next_i = _walk_body(buf, i + 2, _BODY_LEN_MODE_AC)
            if next_i == -1:
                break  # incomplete; keep remainder from i
            i = next_i
            last_consumed = next_i
            continue
        elif msg_type == 0x34:
            # Status frame: skip. Length is format-defined but we
            # don't know it precisely; scan to the next unescaped
            # 0x1a to resync.
            j = i + 2
            while j < len(buf):
                if buf[j] == 0x1A:
                    if j + 1 < len(buf) and buf[j + 1] == 0x1A:
                        j += 2
                        continue
                    break
                j += 1
            if j >= len(buf):
                break  # incomplete; keep remainder from i
            i = j
            last_consumed = j
            continue
        else:
            # Unknown type byte — advance past the escape and try
            # again at the next byte.
            i += 1
            continue

        body, next_i = _walk_body(buf, i + 2, body_len)
        if next_i == -1:
            # Incomplete frame; keep remainder starting at i so the
            # next call can continue from this frame's 0x1a.
            break

        # Body layout (after un-escape): MLAT(6) + SIG(1) + PAYLOAD.
        # The MLAT counter is big-endian 48-bit; NetworkSource turns
        # it into a wall-clock timestamp via an anchor set on the
        # first frame.
        mlat_ticks = int.from_bytes(bytes(body[:6]), "big")
        payload_bytes = bytes(body[payload_offset:])
        frames.append((mlat_ticks, payload_bytes.hex().upper()))
        i = next_i
        last_consumed = next_i

    remainder = buf[last_consumed:] if last_consumed > 0 else buf
    # If we consumed nothing AND found no frames, return the whole
    # buffer as remainder (waiting for more bytes). If we consumed
    # everything cleanly, return empty.
    if not frames and last_consumed == 0:
        return frames, buf
    return frames, remainder


class NetworkSource:
    """TCP source that yields decoded Mode-S hex strings from a beast feed.

    Usage::

        src = NetworkSource("airsquitter.lr.tudelft.nl", 10006)
        for hex_msg, timestamp in src:
            ...

    Iterator never terminates under normal operation — it reconnects
    on dropped connections with exponential backoff. Caller is
    responsible for interrupting via signal (Ctrl-C) or by raising
    from the consuming loop.

    If the initial read from the socket does not contain a beast
    marker byte (0x1a) within the first ``_DETECT_CAP`` bytes, the
    iterator raises ``UnsupportedStreamError`` — the stream is either
    legacy AVR raw text, a totally unrelated protocol, or a broken
    feed.
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
        on_detect: Callable[[str], None] | None = None,
        silent: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.on_detect = on_detect
        # When silent is True, suppress the reconnect WARNING that
        # __iter__ prints to stderr. Used by ``modes live --tui``
        # which cannot tolerate arbitrary stderr writes inside
        # rich.live.Live's alt-screen buffer without corrupting the
        # rendered table.
        self.silent = silent
        self._sock: socket.socket | None = None
        self._buf: bytes = b""
        self._detected: bool = False
        # MLAT-to-wall-clock calibration state. A per-recv() anchor
        # (wall time + first-frame MLAT in the burst) drives per-
        # frame interpolation within the burst; the rate is learned
        # from the delta between consecutive bursts. Both reset on
        # reconnect so the post-reconnect burst anchors freshly.
        self._prev_burst_wall: float | None = None
        self._prev_burst_mlat: int | None = None
        self._rate_estimate: float | None = None

    def __iter__(self) -> Iterator[tuple[str, float]]:
        backoff = 0.5
        while True:
            try:
                self._connect()
                backoff = 0.5  # reset on successful connect
                yield from self._read_loop()
            except UnsupportedStreamError:
                raise
            except (OSError, TimeoutError) as e:
                if not self.silent:
                    print(
                        f"[pyModeS.live] connection dropped ({e}); "
                        f"retrying in {backoff:.1f}s",
                        file=sys.stderr,
                    )
                time.sleep(backoff)
                backoff = min(backoff * 2, 10.0)
                self._detected = False
                self._buf = b""
                # New TCP connection → the receiver's MLAT epoch
                # may be unrelated to the previous one (and on
                # radarcape feeds may even change after midnight).
                # Drop the calibration state so the next burst
                # re-anchors.
                self._prev_burst_wall = None
                self._prev_burst_mlat = None
                self._rate_estimate = None

    def _connect(self) -> None:
        self._sock = socket.create_connection(
            (self.host, self.port), timeout=self.connect_timeout
        )
        self._sock.settimeout(self.read_timeout)

    def _read_loop(self) -> Iterator[tuple[str, float]]:
        """Inner loop: read bytes, parse beast frames, yield (hex, ts).

        Per-frame timestamp strategy:

        - Take ``wall_now = time.time()`` once per ``recv()`` burst.
        - Use the first frame's MLAT in the burst as a local
          anchor; every frame in the burst is then assigned
          ``wall_now + (frame.mlat - first_mlat) / rate``. This
          gives sub-microsecond within-burst precision (at 1 GHz
          radarcape) or sub-100 ns precision (12 MHz dump1090),
          both of which are much finer than what TCP batching
          leaves us with if we just stamp ``time.time()`` once
          per batch.
        - ``rate`` is auto-calibrated against the delta between
          consecutive burst anchors: ``(mlat_N - mlat_{N-1}) /
          (wall_N - wall_{N-1})``. The very first burst has no
          prior anchor, so all its frames fall back to
          ``wall_now``; by the second burst onward, interpolation
          kicks in. The estimator is receiver-agnostic — it works
          the same for 12 MHz dump1090 counters and radarcape
          nanosecond counters with no configuration.
        """
        assert self._sock is not None
        while True:
            chunk = self._sock.recv(8192)
            if not chunk:
                raise OSError("connection closed by remote")
            wall_now = time.time()
            self._buf += chunk

            # On first real data, verify the stream is beast format
            # and resync past any pre-marker preamble.
            if not self._detected:
                if not _detect_format(self._buf):
                    if len(self._buf) > _DETECT_CAP:
                        raise UnsupportedStreamError(
                            f"no beast marker (0x1a) in {_DETECT_CAP} bytes; "
                            "stream is not Mode-S Beast binary format"
                        )
                    continue
                self._detected = True
                if self.on_detect is not None:
                    self.on_detect("beast")
                # Resync: drop any pre-marker bytes
                self._buf = self._buf[self._buf.find(b"\x1a") :]

            # Parse beast frames from the buffer
            frames, remainder = _parse_beast_buffer(self._buf)
            self._buf = remainder

            if not frames:
                continue

            # Per-burst anchor: the first frame's MLAT pairs with
            # wall_now. Interpolate later frames against that.
            burst_anchor_mlat = frames[0][0]

            # Update the rate estimate from the delta between this
            # burst's anchor and the previous one. Skip the very
            # first burst (no prior) and any burst whose wall-clock
            # delta is too small to give a stable estimate.
            if self._prev_burst_wall is not None and self._prev_burst_mlat is not None:
                dw = wall_now - self._prev_burst_wall
                dm = burst_anchor_mlat - self._prev_burst_mlat
                if dw >= _CALIB_MIN_DELTA_S and dm > 0:
                    self._rate_estimate = dm / dw
            self._prev_burst_wall = wall_now
            self._prev_burst_mlat = burst_anchor_mlat

            rate = self._rate_estimate
            for mlat, hex_msg in frames:
                if rate is not None and rate > 0:
                    ts = wall_now + (mlat - burst_anchor_mlat) / rate
                else:
                    # Pre-calibration fallback: every frame in the
                    # burst gets the same wall_now reading. Lasts
                    # only until the second burst (typically <1 s
                    # on a busy feed).
                    ts = wall_now
                yield hex_msg, ts
