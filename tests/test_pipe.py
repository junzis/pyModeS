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

    def test_last_seen_refreshed_on_repeat_decode(self):
        pipe = PipeDecoder()
        pipe.decode("8D485020994409940838175B284F", timestamp=1000.0)
        # Decoding the same message again at a later timestamp
        # should update _last_seen but keep the field values
        pipe.decode("8D485020994409940838175B284F", timestamp=2000.0)
        state = pipe._state["485020"]
        assert state.get("_last_seen") == 2000.0


class TestEndToEndDisambiguation:
    """End-to-end test: a BDS 0,9 velocity report from an aircraft
    populates per-ICAO state, and a subsequent ambiguous BDS 5,0/6,0
    Comm-B from the same ICAO is correctly disambiguated by Phase 3.

    The first part of this test would catch a regression where the
    `_DECODED_TO_KNOWN` mapping is wrong (missing keys, wrong target),
    or where the `known=` forwarding chain breaks anywhere between
    PipeDecoder and `_infer.infer()`.
    """

    def test_velocity_then_ambiguous_commb_picks_bds60(self):
        from pymodes.decoder.bds._infer import infer

        # The ambiguous payload (from tests/test_bds_commb.py) decodes
        # plausibly as both BDS 5,0 (groundspeed=240) and BDS 6,0
        # (magnetic_heading=359°). Without `known`, the heuristic
        # dispatch order returns 5,0 first.
        ambiguous_payload = 0xFFBAA11E200472
        # Sanity-check: bare infer with no known returns 5,0 first
        assert infer(ambiguous_payload)[0] == "5,0"

        # Pre-populate state for the ICAO this Comm-B is from. The
        # Comm-B vector "a000029cffbaa11e2004727281f1" CRC-derives
        # ICAO 4243D0. Set known heading near the BDS 6,0 value (359°)
        # so Phase 3 reorders the candidates.
        pipe = PipeDecoder()
        pipe._state["4243D0"] = {"heading": 359.0, "_last_seen": 1000.0}

        result = pipe.decode("a000029cffbaa11e2004727281f1", timestamp=1001.0)

        # Phase 3 should have reordered the candidates so 6,0 comes first.
        assert result.get("bds") == "6,0"
        # Magnetic heading from BDS 6,0 decode should be present
        assert "magnetic_heading" in result

    def test_bds09_subtype_airspeed_routes_correctly(self):
        # BDS 0,9 subtype 3/4 emits `airspeed` + `airspeed_type`
        # ("IAS"/"TAS"). _update_state must route to known["ias"]
        # or known["tas"] correctly.
        # Real subtype-3 vector from v2 tests: "8DA05F219B06B6AF189400CBC33F"
        # decodes with airspeed_type="TAS", airspeed=375
        pipe = PipeDecoder()
        pipe.decode("8DA05F219B06B6AF189400CBC33F", timestamp=1000.0)
        state = pipe._state.get("A05F21")
        assert state is not None
        # Vector has airspeed_type="TAS" so airspeed routes to known["tas"]
        assert state.get("tas") == 375
        # And NOT to known["ias"]
        assert "ias" not in state


class TestIcaoVerification:
    def test_df20_unverified_without_prior_observation(self):
        pipe = PipeDecoder()
        # No DF11/17/18 has been seen for this ICAO yet
        result = pipe.decode("a000029cffbaa11e2004727281f1")
        assert result.get("icao_verified") is False

    def test_df20_verified_after_synthetic_trusted_observation(self):
        pipe = PipeDecoder()
        # Force-trust ICAO 4243D0 directly (the ICAO encoded in the
        # DF20 vector below). This avoids needing a paired real DF17
        # vector — we're testing the verification logic, not the
        # population logic, which is covered by the next test.
        pipe._trusted_icaos.add("4243D0")
        result = pipe.decode("a000029cffbaa11e2004727281f1", timestamp=1001.0)
        assert result["icao_verified"] is True

    def test_trusted_set_populated_by_df17(self):
        pipe = PipeDecoder()
        # Any clean DF17 message populates the trusted set with its ICAO
        pipe.decode("8D406B902015A678D4D220AA4BDA", timestamp=1000.0)
        assert "406B90" in pipe._trusted_icaos

    def test_trusted_set_not_populated_by_failing_crc(self):
        pipe = PipeDecoder()
        # Flip a bit in the DF17 to break the CRC
        n = int("8D406B902015A678D4D220AA4BDA", 16) ^ (1 << 50)
        pipe.decode(f"{n:028X}", timestamp=1000.0)
        assert "406B90" not in pipe._trusted_icaos

    def test_reset_clears_trusted_set(self):
        pipe = PipeDecoder()
        pipe.decode("8D406B902015A678D4D220AA4BDA", timestamp=1000.0)
        assert "406B90" in pipe._trusted_icaos
        pipe.reset()
        assert "406B90" not in pipe._trusted_icaos


class TestCprPairAccumulation:
    def test_airborne_pair_resolves_lat_lon(self):
        pipe = PipeDecoder()
        # v2 test vector pair from tests/test_cpr.py
        pipe.decode(
            "8D40058B58C901375147EFD09357",  # even
            timestamp=1446332400.0,
        )
        result = pipe.decode(
            "8D40058B58C904A87F402D3B8C59",  # odd, 5s later
            timestamp=1446332405.0,
        )
        assert result["latitude"] == pytest.approx(49.81755, abs=0.001)
        assert result["longitude"] == pytest.approx(6.08442, abs=0.001)

    def test_pair_outside_window_not_resolved(self):
        pipe = PipeDecoder(pair_window=2.0)
        pipe.decode("8D40058B58C901375147EFD09357", timestamp=1000.0)
        result = pipe.decode("8D40058B58C904A87F402D3B8C59", timestamp=1010.0)
        # 10s gap > 2s window — no pair resolution
        assert "latitude" not in result

    def test_single_frame_no_pair_keeps_raw_cpr(self):
        pipe = PipeDecoder()
        result = pipe.decode("8D40058B58C901375147EFD09357", timestamp=1000.0)
        assert "latitude" not in result
        assert "cpr_lat" in result
        assert pipe.stats["pending_pairs"] == 1

    def test_pair_resolution_decrements_pending_pairs(self):
        pipe = PipeDecoder()
        pipe.decode("8D40058B58C901375147EFD09357", timestamp=1000.0)
        assert pipe.stats["pending_pairs"] == 1
        pipe.decode("8D40058B58C904A87F402D3B8C59", timestamp=1003.0)
        assert pipe.stats["pending_pairs"] == 0

    def test_pair_without_timestamp_no_resolution(self):
        pipe = PipeDecoder()
        # No timestamp on either decode — pair logic must skip
        pipe.decode("8D40058B58C901375147EFD09357")
        result = pipe.decode("8D40058B58C904A87F402D3B8C59")
        assert "latitude" not in result
        assert pipe.stats["pending_pairs"] == 0  # nothing stored either

    def test_surface_pair_with_surface_ref(self):
        pipe = PipeDecoder(surface_ref="NZCH")
        # First frame (even) — surface_ref already resolves it via
        # single-message path, so latitude is set after this call.
        # The pair logic stores it as pending anyway for the next.
        pipe.decode("8CC8200A3AC8F009BCDEF2000000", timestamp=0.0)
        # Second frame (odd) — single-message also resolves via
        # surface_ref, but the pair would also resolve it.
        result = pipe.decode("8FC8200A3AB8F5F893096B000000", timestamp=2.0)
        # Either path should yield the same lat/lon
        assert result["latitude"] == pytest.approx(-43.48564, abs=0.001)
        assert result["longitude"] == pytest.approx(172.53942, abs=0.001)

    def test_same_parity_overwrites_pending(self):
        pipe = PipeDecoder()
        pipe.decode("8D40058B58C901375147EFD09357", timestamp=1000.0)
        # Decode another even frame from the same ICAO — should
        # overwrite the older pending entry, not add a second
        pipe.decode("8D40058B58C901375147EFD09357", timestamp=1001.0)
        assert pipe.stats["pending_pairs"] == 1
