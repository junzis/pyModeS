"""Tests for batch decode(list[str]) overload."""

import logging

import pytest

from pymodes import decode


class TestBatchDecode:
    def test_simple_batch(self):
        msgs = [
            "8D406B902015A678D4D220AA4BDA",
            "8D485020994409940838175B284F",
        ]
        results = decode(msgs)
        assert len(results) == 2
        assert results[0]["icao"] == "406B90"
        assert results[1]["icao"] == "485020"

    def test_batch_with_timestamps_resolves_cpr_pair(self):
        msgs = [
            "8D40058B58C901375147EFD09357",
            "8D40058B58C904A87F402D3B8C59",
        ]
        results = decode(msgs, timestamps=[1446332400.0, 1446332405.0])
        assert results[1]["latitude"] == pytest.approx(49.81755, abs=0.001)
        assert results[1]["longitude"] == pytest.approx(6.08442, abs=0.001)

    def test_batch_corrupt_message_becomes_error_dict(self):
        msgs = [
            "8D406B902015A678D4D220AA4BDA",
            "not hex",
            "8D485020994409940838175B284F",
        ]
        results = decode(msgs)
        assert len(results) == 3
        assert "error" in results[1]
        assert results[1]["raw_msg"] == "not hex"
        assert results[0]["icao"] == "406B90"
        assert results[2]["icao"] == "485020"

    def test_batch_without_timestamps_warns(self, caplog):
        with caplog.at_level(logging.WARNING):
            decode(["8D406B902015A678D4D220AA4BDA"])
        assert any("timestamps" in r.message for r in caplog.records)

    def test_batch_with_surface_ref(self):
        # Real DF18 BDS 0,6 surface movement from jet1090 corpus
        # (LFBO taxiway). Replaces the earlier synthetic NZCH vector.
        results = decode(
            ["903a23ff426a4e65f7487a775d17"],
            timestamps=[0.0],
            surface_ref="LFBO",
        )
        assert results[0]["latitude"] == pytest.approx(43.62646, abs=0.001)
        assert results[0]["longitude"] == pytest.approx(1.37476, abs=0.001)

    def test_batch_rejects_single_msg_kwargs(self):
        with pytest.raises(TypeError, match="reference"):
            decode(["8D40058B58C901375147EFD09357"], reference=(49, 6))

    def test_batch_length_preserved_with_errors(self):
        msgs = ["bad1", "bad2", "bad3"]
        results = decode(msgs)
        assert len(results) == 3
        for r in results:
            assert "error" in r

    def test_batch_with_full_dict(self):
        from pymodes._schema import _FULL_SCHEMA

        results = decode(
            ["8D406B902015A678D4D220AA4BDA"],
            timestamps=[0.0],
            full_dict=True,
        )
        for key in _FULL_SCHEMA:
            assert key in results[0]

    def test_batch_timestamps_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="length"):
            decode(
                ["8D406B902015A678D4D220AA4BDA", "8D485020994409940838175B284F"],
                timestamps=[1.0],  # only 1 timestamp for 2 messages
            )

    def test_batch_empty_list(self):
        # Empty batch should return an empty list without spinning up
        # a decoder or logging a warning about missing timestamps.
        assert decode([]) == []
        assert decode([], timestamps=[]) == []
