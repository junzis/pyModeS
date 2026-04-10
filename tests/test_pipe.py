"""Tests for pymodes.PipeDecoder."""

import pytest

from pymodes import PipeDecoder


class TestPipeDecoderSkeleton:
    def test_construction_defaults(self):
        pipe = PipeDecoder()
        assert pipe.stats == {
            "total": 0,
            "decoded": 0,
            "crc_fail": 0,
            "pending_pairs": 0,
        }

    def test_decode_single_message(self):
        pipe = PipeDecoder()
        result = pipe.decode("8D406B902015A678D4D220AA4BDA")
        assert result["df"] == 17
        assert result["icao"] == "406B90"
        assert pipe.stats["total"] == 1
        assert pipe.stats["decoded"] == 1

    def test_decode_with_timestamp(self):
        pipe = PipeDecoder()
        result = pipe.decode("8D406B902015A678D4D220AA4BDA", timestamp=1000.0)
        assert result["df"] == 17

    def test_decode_corrupt_message_returns_error_dict(self):
        pipe = PipeDecoder()
        result = pipe.decode("not hex")
        assert "error" in result
        assert result["raw_msg"] == "not hex"
        assert pipe.stats["total"] == 1
        assert pipe.stats["decoded"] == 0

    def test_stats_returns_a_copy(self):
        pipe = PipeDecoder()
        stats1 = pipe.stats
        pipe.decode("8D406B902015A678D4D220AA4BDA")
        # Mutating the snapshot shouldn't affect future reads
        stats1["total"] = 999
        assert pipe.stats["total"] == 1

    def test_reset_clears_stats_and_state(self):
        pipe = PipeDecoder()
        pipe.decode("8D406B902015A678D4D220AA4BDA")
        pipe.decode("not hex")
        pipe.reset()
        assert pipe.stats == {
            "total": 0,
            "decoded": 0,
            "crc_fail": 0,
            "pending_pairs": 0,
        }

    def test_surface_ref_propagates_to_decode(self):
        pipe = PipeDecoder(surface_ref="NZCH")
        result = pipe.decode("8FC8200A3AB8F5F893096B000000")
        assert result["latitude"] == pytest.approx(-43.48564, abs=0.001)
        assert result["longitude"] == pytest.approx(172.53942, abs=0.001)

    def test_full_dict_propagates_to_decode(self):
        from pymodes._schema import _FULL_SCHEMA

        pipe = PipeDecoder(full_dict=True)
        result = pipe.decode("8D406B902015A678D4D220AA4BDA")
        for key in _FULL_SCHEMA:
            assert key in result


class TestKnownKwargPlumbing:
    def test_message_decode_accepts_known(self):
        from pymodes import Message

        msg = Message("8D406B902015A678D4D220AA4BDA")
        # No-op for non-CommB messages, but the kwarg must be accepted
        result = msg.decode(known={"groundspeed": 420})
        assert result["df"] == 17

    def test_core_decode_accepts_known(self):
        from pymodes import decode

        result = decode("8D406B902015A678D4D220AA4BDA", known={"groundspeed": 420})
        assert result["df"] == 17


class TestStateTracking:
    def test_state_populated_after_velocity_decode(self):
        pipe = PipeDecoder()
        # DF17 BDS 0,9 ground velocity message — populates groundspeed and track
        pipe.decode("8D485020994409940838175B284F", timestamp=1000.0)
        # State accessible via private attr (test-only API)
        state = pipe._state.get("485020")
        assert state is not None
        assert "groundspeed" in state
        assert "track" in state

    def test_known_passed_to_subsequent_decode(self, monkeypatch):
        # Verify that prior groundspeed/track is forwarded as known=
        # to the next decode. Capture via monkeypatch on Message.decode.
        from pymodes import Message

        captured: list[dict | None] = []
        original_decode = Message.decode

        def spy(self, **kwargs):
            captured.append(kwargs.get("known"))
            return original_decode(self, **kwargs)

        monkeypatch.setattr(Message, "decode", spy)
        pipe = PipeDecoder()
        # First call: state is empty, known should be None or empty
        pipe.decode("8D485020994409940838175B284F", timestamp=1000.0)
        assert captured[0] is None or captured[0] == {}
        # Second call (same ICAO): known should now contain groundspeed
        pipe.decode("8D485020994409940838175B284F", timestamp=1001.0)
        assert captured[1] is not None
        assert "groundspeed" in captured[1]
        # The _last_seen housekeeping key must NOT be in the known dict
        # passed to Message.decode (it would not match _SCORE_FIELDS).
        assert "_last_seen" not in captured[1]

    def test_state_persists_when_field_not_re_emitted(self):
        pipe = PipeDecoder()
        # First message populates groundspeed
        pipe.decode("8D485020994409940838175B284F", timestamp=1000.0)
        gs_before = pipe._state["485020"].get("groundspeed")
        assert gs_before is not None
        # A different ICAO's message should not affect state["485020"]
        pipe.decode("8D406B902015A678D4D220AA4BDA", timestamp=1001.0)
        gs_after = pipe._state["485020"].get("groundspeed")
        assert gs_after == gs_before

    def test_state_updates_on_new_field(self):
        pipe = PipeDecoder()
        pipe.decode("8D485020994409940838175B284F", timestamp=1000.0)
        # Decoding the same message again at a later timestamp
        # should update _last_seen but keep the field values
        pipe.decode("8D485020994409940838175B284F", timestamp=2000.0)
        state = pipe._state["485020"]
        assert state.get("_last_seen") == 2000.0
