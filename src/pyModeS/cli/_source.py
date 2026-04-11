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


def _parse_beast_buffer(buf: bytes) -> tuple[list[str], bytes]:
    """Parse a beast-format byte buffer into hex strings + remainder.

    Scans forward through ``buf`` looking for frame starts (0x1a).
    For each recognised frame (types 0x32 and 0x33), un-escapes the
    body and extracts the payload hex. Mode AC (0x31) and status
    (0x34) frames are skipped but still advance the parse cursor.
    Unknown type bytes are also skipped.

    Returns (frames, remainder) where remainder is the tail of the
    buffer containing any incomplete trailing frame (from the last
    0x1a that couldn't be fully parsed). The caller should prepend
    the remainder to the next chunk of bytes before the next parse.
    """
    frames: list[str] = []
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

        payload_bytes = bytes(body[payload_offset:])
        frames.append(payload_bytes.hex().upper())
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

    def _connect(self) -> None:
        self._sock = socket.create_connection(
            (self.host, self.port), timeout=self.connect_timeout
        )
        self._sock.settimeout(self.read_timeout)

    def _read_loop(self) -> Iterator[tuple[str, float]]:
        """Inner loop: read bytes, parse beast frames, yield (hex, ts)."""
        assert self._sock is not None
        while True:
            chunk = self._sock.recv(8192)
            if not chunk:
                raise OSError("connection closed by remote")
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

            now = time.time()
            for hex_msg in frames:
                yield hex_msg, now
