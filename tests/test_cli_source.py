"""Tests for the pymodes.cli._source NetworkSource and beast frame parser."""

from __future__ import annotations


class TestDetectFormat:
    def test_beast_marker_at_start(self):
        from pymodes.cli._source import _detect_format

        assert _detect_format(b"\x1a3\x00\x00\x00") is True

    def test_resync_past_garbage(self):
        from pymodes.cli._source import _detect_format

        garbage = b"\x00\x01\x02\x03\x04\x05"
        assert _detect_format(garbage + b"\x1a3rest") is True

    def test_undetected_returns_false(self):
        from pymodes.cli._source import _detect_format

        assert _detect_format(b"only random bytes no marker") is False


class TestBeastParser:
    def _make_long_frame(self, hex_msg: str) -> bytes:
        """Build a minimal beast 'long' frame with the given hex payload.

        Format: ESC(0x1a) + TYPE(0x33) + MLAT(6 zero bytes) + SIG(1 zero byte)
        + PAYLOAD(14 bytes from hex)
        """
        payload = bytes.fromhex(hex_msg)
        assert len(payload) == 14
        return b"\x1a\x33" + b"\x00" * 7 + payload

    def _make_short_frame(self, hex_msg: str) -> bytes:
        payload = bytes.fromhex(hex_msg)
        assert len(payload) == 7
        return b"\x1a\x32" + b"\x00" * 7 + payload

    def test_single_long_frame(self):
        from pymodes.cli._source import _parse_beast_buffer

        frame = self._make_long_frame("8D406B902015A678D4D220AA4BDA")
        # Need a second esc-marker to terminate the current frame
        buf = frame + b"\x1a"
        frames, _remainder = _parse_beast_buffer(buf)
        assert len(frames) == 1
        assert frames[0].upper() == "8D406B902015A678D4D220AA4BDA"

    def test_multiple_long_frames(self):
        from pymodes.cli._source import _parse_beast_buffer

        f1 = self._make_long_frame("8D406B902015A678D4D220AA4BDA")
        f2 = self._make_long_frame("8D485020994409940838175B284F")
        buf = f1 + f2 + b"\x1a"
        frames, _remainder = _parse_beast_buffer(buf)
        assert len(frames) == 2
        assert frames[0].upper() == "8D406B902015A678D4D220AA4BDA"
        assert frames[1].upper() == "8D485020994409940838175B284F"

    def test_short_frame(self):
        from pymodes.cli._source import _parse_beast_buffer

        frame = self._make_short_frame("20000000000000")
        buf = frame + b"\x1a"
        frames, _remainder = _parse_beast_buffer(buf)
        assert len(frames) == 1
        assert frames[0].upper() == "20000000000000"

    def test_escaped_0x1a_in_payload(self):
        """Beast protocol: a literal 0x1a byte in the payload is encoded
        as two consecutive 0x1a bytes. The parser must un-escape."""
        from pymodes.cli._source import _parse_beast_buffer

        # Long frame with 0x1a in the middle of the payload
        payload = bytes.fromhex("8D406B902015A6781AD220AA4BDA")
        assert len(payload) == 14
        header = b"\x1a\x33" + b"\x00" * 7
        # Insert escape for the 0x1a byte in payload
        escaped_payload = payload.replace(b"\x1a", b"\x1a\x1a")
        buf = header + escaped_payload + b"\x1a"
        frames, _remainder = _parse_beast_buffer(buf)
        assert len(frames) == 1
        # 0x1a in hex is '1A'
        assert frames[0].upper() == "8D406B902015A6781AD220AA4BDA"

    def test_partial_frame_preserved_in_remainder(self):
        from pymodes.cli._source import _parse_beast_buffer

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
        from pymodes.cli._source import _parse_beast_buffer

        # Mode AC is type 0x31, which the parser should drop.
        # Mode AC payload length is 2 bytes; total frame is 11 bytes
        # (ESC + TYPE + 6 MLAT + 1 SIG + 2 payload).
        mode_ac = b"\x1a\x31" + b"\x00" * 7 + b"\x00\x00"
        long_f = self._make_long_frame("8D406B902015A678D4D220AA4BDA")
        buf = mode_ac + long_f + b"\x1a"
        frames, _remainder = _parse_beast_buffer(buf)
        assert len(frames) == 1
        assert frames[0].upper() == "8D406B902015A678D4D220AA4BDA"
