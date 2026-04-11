"""Tests for the pyModeS.cli._source NetworkSource and beast frame parser."""

from __future__ import annotations

import pytest


class TestDetectFormat:
    def test_beast_marker_at_start(self):
        from pyModeS.cli._source import _detect_format

        assert _detect_format(b"\x1a3\x00\x00\x00") is True

    def test_resync_past_garbage(self):
        from pyModeS.cli._source import _detect_format

        garbage = b"\x00\x01\x02\x03\x04\x05"
        assert _detect_format(garbage + b"\x1a3rest") is True

    def test_undetected_returns_false(self):
        from pyModeS.cli._source import _detect_format

        assert _detect_format(b"only random bytes no marker") is False


class TestBeastParser:
    def _make_long_frame(self, hex_msg: str, mlat: int = 0) -> bytes:
        """Build a minimal beast 'long' frame with the given hex payload.

        Format: ESC(0x1a) + TYPE(0x33) + MLAT(6 bytes big-endian)
        + SIG(1 zero byte) + PAYLOAD(14 bytes from hex)
        """
        payload = bytes.fromhex(hex_msg)
        assert len(payload) == 14
        mlat_bytes = mlat.to_bytes(6, "big")
        return b"\x1a\x33" + mlat_bytes + b"\x00" + payload

    def _make_short_frame(self, hex_msg: str, mlat: int = 0) -> bytes:
        payload = bytes.fromhex(hex_msg)
        assert len(payload) == 7
        mlat_bytes = mlat.to_bytes(6, "big")
        return b"\x1a\x32" + mlat_bytes + b"\x00" + payload

    def test_single_long_frame(self):
        from pyModeS.cli._source import _parse_beast_buffer

        frame = self._make_long_frame("8D406B902015A678D4D220AA4BDA")
        # Need a second esc-marker to terminate the current frame
        buf = frame + b"\x1a"
        frames, _remainder = _parse_beast_buffer(buf)
        assert len(frames) == 1
        mlat, hex_msg = frames[0]
        assert hex_msg.upper() == "8D406B902015A678D4D220AA4BDA"
        assert mlat == 0

    def test_multiple_long_frames_with_distinct_mlat(self):
        from pyModeS.cli._source import _parse_beast_buffer

        # Two frames 1 second apart at 12 MHz → 12_000_000 ticks.
        f1 = self._make_long_frame("8D406B902015A678D4D220AA4BDA", mlat=1000)
        f2 = self._make_long_frame(
            "8D485020994409940838175B284F", mlat=1000 + 12_000_000
        )
        buf = f1 + f2 + b"\x1a"
        frames, _remainder = _parse_beast_buffer(buf)
        assert len(frames) == 2
        m1, h1 = frames[0]
        m2, h2 = frames[1]
        assert h1.upper() == "8D406B902015A678D4D220AA4BDA"
        assert h2.upper() == "8D485020994409940838175B284F"
        assert m1 == 1000
        assert m2 == 1000 + 12_000_000

    def test_short_frame(self):
        from pyModeS.cli._source import _parse_beast_buffer

        frame = self._make_short_frame("20000000000000")
        buf = frame + b"\x1a"
        frames, _remainder = _parse_beast_buffer(buf)
        assert len(frames) == 1
        _mlat, hex_msg = frames[0]
        assert hex_msg.upper() == "20000000000000"

    def test_escaped_0x1a_in_payload(self):
        """Beast protocol: a literal 0x1a byte in the payload is encoded
        as two consecutive 0x1a bytes. The parser must un-escape."""
        from pyModeS.cli._source import _parse_beast_buffer

        # Long frame with 0x1a in the middle of the payload
        payload = bytes.fromhex("8D406B902015A6781AD220AA4BDA")
        assert len(payload) == 14
        header = b"\x1a\x33" + b"\x00" * 7
        # Insert escape for the 0x1a byte in payload
        escaped_payload = payload.replace(b"\x1a", b"\x1a\x1a")
        buf = header + escaped_payload + b"\x1a"
        frames, _remainder = _parse_beast_buffer(buf)
        assert len(frames) == 1
        _mlat, hex_msg = frames[0]
        # 0x1a in hex is '1A'
        assert hex_msg.upper() == "8D406B902015A6781AD220AA4BDA"

    def test_escaped_0x1a_in_mlat(self):
        """A 0x1a byte inside the MLAT field must be un-escaped the
        same way payload bytes are — the parser walks the entire
        body (MLAT + SIG + PAYLOAD) uniformly."""
        from pyModeS.cli._source import _parse_beast_buffer

        # MLAT with 0x1a as the middle byte (bytes 0,1,2 = 00 00 1a,
        # bytes 3,4,5 = 00 00 00). Un-escaped MLAT value is the
        # big-endian int of 00 00 1a 00 00 00 = 0x1a000000.
        header = b"\x1a\x33"
        mlat_bytes = b"\x00\x00\x1a\x00\x00\x00"
        escaped_mlat = mlat_bytes.replace(b"\x1a", b"\x1a\x1a")
        sig = b"\x00"
        payload = bytes.fromhex("8D406B902015A678D4D220AA4BDA")
        buf = header + escaped_mlat + sig + payload + b"\x1a"
        frames, _remainder = _parse_beast_buffer(buf)
        assert len(frames) == 1
        mlat, hex_msg = frames[0]
        assert mlat == 0x1A000000
        assert hex_msg.upper() == "8D406B902015A678D4D220AA4BDA"

    def test_partial_frame_preserved_in_remainder(self):
        from pyModeS.cli._source import _parse_beast_buffer

        f1 = self._make_long_frame("8D406B902015A678D4D220AA4BDA")
        # Incomplete second frame (just the header + a few payload bytes)
        partial = b"\x1a\x33" + b"\x00" * 7 + b"\x8d\x48"
        buf = f1 + partial
        frames, remainder = _parse_beast_buffer(buf)
        assert len(frames) == 1
        # Remainder should include the incomplete frame so the next
        # parse call can complete it when more bytes arrive
        assert b"\x1a\x33" in remainder

    def test_skips_mode_ac_frames(self):
        from pyModeS.cli._source import _parse_beast_buffer

        # Mode AC is type 0x31, which the parser should drop.
        # Mode AC payload length is 2 bytes; total frame is 11 bytes
        # (ESC + TYPE + 6 MLAT + 1 SIG + 2 payload).
        mode_ac = b"\x1a\x31" + b"\x00" * 7 + b"\x00\x00"
        long_f = self._make_long_frame("8D406B902015A678D4D220AA4BDA")
        buf = mode_ac + long_f + b"\x1a"
        frames, _remainder = _parse_beast_buffer(buf)
        assert len(frames) == 1
        _mlat, hex_msg = frames[0]
        assert hex_msg.upper() == "8D406B902015A678D4D220AA4BDA"


class TestMlatCalibration:
    """End-to-end tests for NetworkSource's MLAT-derived per-frame
    timestamps. The read-loop grabs ``time.time()`` once per recv()
    burst, auto-calibrates a tick rate from the delta between
    consecutive burst anchors, and interpolates each frame in the
    current burst against the burst's first-frame MLAT.

    We drive ``_read_loop`` through a fake socket rather than spinning
    up a real TCP server — the bytes-in / frames-out contract is all
    that matters for the timing logic.
    """

    def _make_long_frame(self, hex_msg: str, mlat: int) -> bytes:
        # Same bytes layout as TestBeastParser._make_long_frame —
        # kept inline to avoid cross-class test coupling.
        payload = bytes.fromhex(hex_msg)
        assert len(payload) == 14
        mlat_bytes = mlat.to_bytes(6, "big")
        return b"\x1a\x33" + mlat_bytes + b"\x00" + payload

    def _run_bursts(
        self,
        bursts: list[bytes],
        wall_times: list[float],
    ) -> list[tuple[str, float]]:
        """Feed a sequence of recv() bursts through a real
        NetworkSource wired up to a fake socket. ``wall_times[i]``
        is the value ``time.time()`` returns when the i-th recv()
        call completes."""
        from pyModeS.cli._source import NetworkSource

        class _FakeSock:
            def __init__(self, chunks: list[bytes]) -> None:
                self._chunks = list(chunks)

            def recv(self, n: int) -> bytes:
                if not self._chunks:
                    raise OSError("no more fake data")
                return self._chunks.pop(0)

            def settimeout(self, *_: object) -> None:
                pass

            def close(self) -> None:
                pass

        src = NetworkSource("fake", 0)
        src._sock = _FakeSock(bursts)  # type: ignore[assignment]

        captured: list[tuple[str, float]] = []
        call_idx = [0]
        orig_time = __import__("time").time

        def fake_time() -> float:
            i = call_idx[0]
            if i < len(wall_times):
                call_idx[0] += 1
                return wall_times[i]
            return orig_time()

        import pyModeS.cli._source as source_mod

        real_time = source_mod.time.time
        source_mod.time.time = fake_time  # type: ignore[method-assign]
        try:
            try:
                for hex_msg, ts in src._read_loop():
                    captured.append((hex_msg, ts))
                    if len(captured) >= 10:
                        break
            except OSError:
                pass
        finally:
            source_mod.time.time = real_time  # type: ignore[method-assign]
        return captured

    def test_first_burst_falls_back_to_wall_now(self) -> None:
        # With no previous anchor the rate is unknown, so every
        # frame in the very first burst is stamped with wall_now
        # instead of interpolating.
        frame1 = self._make_long_frame("8D406B902015A678D4D220AA4BDA", mlat=0)
        frame2 = self._make_long_frame("8D485020994409940838175B284F", mlat=5_000_000)
        burst = frame1 + frame2 + b"\x1a"

        captured = self._run_bursts([burst], wall_times=[1000.0])
        assert len(captured) == 2
        assert captured[0][1] == 1000.0
        assert captured[1][1] == 1000.0

    def test_second_burst_calibrates_to_12mhz_dump1090(self) -> None:
        # Burst 1: anchor wall=1000, mlat=0
        # Burst 2: anchor wall=1001, mlat=12e6 → rate = 12 MHz
        #          second frame within burst 2 is 6e6 ticks further
        #          → wall = 1001 + 6e6 / 12e6 = 1001.5
        b1 = self._make_long_frame("8D406B902015A678D4D220AA4BDA", mlat=0) + b"\x1a"
        f1 = self._make_long_frame("8D485020994409940838175B284F", mlat=12_000_000)
        f2 = self._make_long_frame("8D40058B58C901375147EFD09357", mlat=18_000_000)
        b2 = f1 + f2 + b"\x1a"

        captured = self._run_bursts([b1, b2], wall_times=[1000.0, 1001.0])
        # burst 1: fallback wall_now
        assert captured[0][1] == 1000.0
        # burst 2 frame 1: anchor to wall_now=1001.0
        assert captured[1][1] == pytest.approx(1001.0, abs=1e-6)
        # burst 2 frame 2: interpolate (rate from burst1→burst2 anchor pair)
        assert captured[2][1] == pytest.approx(1001.5, abs=1e-6)

    def test_second_burst_calibrates_to_1ghz_radarcape(self) -> None:
        # Burst 1: anchor wall=1000, mlat=0
        # Burst 2: anchor wall=1001, mlat=1e9 → rate = 1 GHz
        #          second frame 500e6 ticks further → wall = 1001.5
        b1 = self._make_long_frame("8D406B902015A678D4D220AA4BDA", mlat=0) + b"\x1a"
        f1 = self._make_long_frame("8D485020994409940838175B284F", mlat=1_000_000_000)
        f2 = self._make_long_frame("8D40058B58C901375147EFD09357", mlat=1_500_000_000)
        b2 = f1 + f2 + b"\x1a"

        captured = self._run_bursts([b1, b2], wall_times=[1000.0, 1001.0])
        assert captured[1][1] == pytest.approx(1001.0, abs=1e-6)
        assert captured[2][1] == pytest.approx(1001.5, abs=1e-6)

    def test_reconnect_resets_calibration_state(self) -> None:
        from pyModeS.cli._source import NetworkSource

        src = NetworkSource("fake", 0)
        src._prev_burst_wall = 100.0
        src._prev_burst_mlat = 42
        src._rate_estimate = 12_000_000.0

        # Simulate the __iter__ reconnect branch inline — same
        # three assignments the real code does.
        src._prev_burst_wall = None
        src._prev_burst_mlat = None
        src._rate_estimate = None

        assert src._prev_burst_wall is None
        assert src._prev_burst_mlat is None
        assert src._rate_estimate is None
