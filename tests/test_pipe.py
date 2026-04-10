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
