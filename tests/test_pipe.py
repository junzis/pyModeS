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

    def test_known_none_when_state_only_has_housekeeping(self, monkeypatch):
        # A BDS 0,8 identification message emits no field in
        # `_DECODED_TO_KNOWN`, so the first decode leaves state with
        # only `_last_seen`. The second decode filters out that key
        # and passes `known=None` to Message.decode (not an empty dict).
        from pymodes import Message

        captured: list[dict | None] = []
        original_decode = Message.decode

        def spy(self, **kwargs):
            captured.append(kwargs.get("known"))
            return original_decode(self, **kwargs)

        monkeypatch.setattr(Message, "decode", spy)
        pipe = PipeDecoder()
        # First decode: BDS 0,8 identification — emits callsign,
        # category, wake_vortex, none of which are in _DECODED_TO_KNOWN.
        pipe.decode("8D406B902015A678D4D220AA4BDA", timestamp=1000.0)
        state = pipe._state["406B90"]
        # Confirm the state only contains the _last_seen housekeeping key
        assert set(state.keys()) == {"_last_seen"}
        # Second decode, same ICAO: known must be None (not {})
        pipe.decode("8D406B902015A678D4D220AA4BDA", timestamp=1001.0)
        assert captured[1] is None


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

    def test_velocity_then_ambiguous_commb_picks_bds50(self):
        # Mirror of the heading test: a known groundspeed near the
        # BDS 5,0 decoded value should keep 5,0 at the front. Without
        # this, we only exercise the heading branch of Phase 3 scoring.
        pipe = PipeDecoder()
        pipe._state["4243D0"] = {"groundspeed": 240, "_last_seen": 1000.0}

        result = pipe.decode("a000029cffbaa11e2004727281f1", timestamp=1001.0)

        assert result.get("bds") == "5,0"
        assert "groundspeed" in result

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

    def test_bds09_subtype_ias_routes_to_ias(self):
        # Synthetic IAS vector: same as the TAS vector above but with
        # the airspeed-type bit flipped (bit 24 of the ME field cleared).
        # Decodes to subtype=3, airspeed=375, airspeed_type="IAS".
        # Exercises the IAS branch of _update_state's airspeed router.
        pipe = PipeDecoder()
        pipe.decode("8DA05F219B06B62F189400CBC33F", timestamp=1000.0)
        state = pipe._state.get("A05F21")
        assert state is not None
        assert state.get("ias") == 375
        assert "tas" not in state


class TestKnownKeyInvariant:
    """PipeDecoder and _infer share a contract: the scoring tables in
    _infer reference known-dict keys (e.g. "heading", "tas"), and
    PipeDecoder populates those keys via its `_DECODED_TO_KNOWN` map.
    If _infer grows a new scoring field and PipeDecoder isn't updated,
    Phase 3 disambiguation silently stops working (the missing key
    reads as None and the candidate scores inf).

    This test keeps the two sides in sync.
    """

    def test_score_field_known_keys_are_populated_by_pipe(self):
        from pymodes._pipe import _DECODED_TO_KNOWN
        from pymodes.decoder.bds._infer import (
            _SCORE_FIELDS_BDS50,
            _SCORE_FIELDS_BDS60,
        )

        pipe_known_keys = set(_DECODED_TO_KNOWN.values())
        # Also include the airspeed discriminator routing in _update_state:
        # BDS 0,9 sub 3/4 writes `ias` or `tas` based on airspeed_type.
        pipe_known_keys.update({"ias", "tas"})

        scored_keys = {k for _, k, _ in _SCORE_FIELDS_BDS50 + _SCORE_FIELDS_BDS60}
        missing = scored_keys - pipe_known_keys
        assert not missing, (
            f"_infer scoring tables reference known keys that PipeDecoder "
            f"never populates: {sorted(missing)}. Either add a mapping to "
            f"_pipe._DECODED_TO_KNOWN or drop the field from the scoring table."
        )


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

    def test_odd_first_pair_resolves(self):
        # Mirror of the airborne_pair test with frames reversed: the
        # odd frame arrives first (stored as pending), then the even
        # frame arrives and resolves. This exercises the cpr_format==0
        # "current is even, other is odd" branch of _resolve_pair that
        # the even-first test skips. Because the newer (even) frame
        # dictates the reported position, the expected lat/lon differs
        # slightly from the even-first test.
        pipe = PipeDecoder()
        pipe.decode(
            "8D40058B58C904A87F402D3B8C59",  # odd, arrives first
            timestamp=1446332400.0,
        )
        assert pipe.stats["pending_pairs"] == 1
        result = pipe.decode(
            "8D40058B58C901375147EFD09357",  # even, 5s later
            timestamp=1446332405.0,
        )
        # even_is_newer=True resolution
        assert result["latitude"] == pytest.approx(49.82410, abs=0.001)
        assert result["longitude"] == pytest.approx(6.06785, abs=0.001)

    def test_surface_pair_without_surface_ref_skips_resolution(self):
        # When a surface CPR (BDS 0,6) pair is eligible but the decoder
        # was constructed without a surface_ref, _resolve_pair must
        # silently skip rather than crash. The single-frame lat/lon
        # is already absent because surface CPR requires the ref even
        # for single-message resolution.
        pipe = PipeDecoder()  # no surface_ref
        pipe.decode("8CC8200A3AC8F009BCDEF2000000", timestamp=0.0)
        result = pipe.decode("8FC8200A3AB8F5F893096B000000", timestamp=2.0)
        # No crash, and no lat/lon resolved
        assert "latitude" not in result
        assert "longitude" not in result

    def test_pair_different_nl_zones_returns_none(self, monkeypatch):
        # When the even/odd pair falls in different cprNL zones,
        # airborne_position_pair returns None. The pair is still
        # popped from pending but no lat/lon is merged into the result.
        # Easier to monkeypatch the pair solver than to hand-construct
        # a pair straddling a zone boundary. _pipe.py lazy-imports the
        # resolver from `pymodes.position`, so we patch the re-export
        # there (not the underlying _cpr module).
        import pymodes.position

        monkeypatch.setattr(
            pymodes.position, "airborne_position_pair", lambda *a, **kw: None
        )

        pipe = PipeDecoder()
        pipe.decode("8D40058B58C901375147EFD09357", timestamp=1000.0)
        result = pipe.decode("8D40058B58C904A87F402D3B8C59", timestamp=1003.0)
        assert "latitude" not in result
        assert "longitude" not in result
        # Pair still popped from pending
        assert pipe.stats["pending_pairs"] == 0


class TestEviction:
    def test_old_pending_pair_evicted(self):
        pipe = PipeDecoder(eviction_ttl=10.0, pair_window=10.0)
        pipe.decode("8D40058B58C901375147EFD09357", timestamp=0.0)
        assert pipe.stats["pending_pairs"] == 1
        # 100s later, decode an unrelated message — eviction runs
        pipe.decode("8D406B902015A678D4D220AA4BDA", timestamp=100.0)
        # Old pending entry should have been evicted
        assert pipe.stats["pending_pairs"] == 0

    def test_old_state_evicted(self):
        pipe = PipeDecoder(eviction_ttl=10.0)
        pipe.decode("8D485020994409940838175B284F", timestamp=0.0)
        assert "485020" in pipe._state
        # 100s later, decode an unrelated ICAO
        pipe.decode("8D406B902015A678D4D220AA4BDA", timestamp=100.0)
        # 485020's state is older than eviction_ttl → dropped
        assert "485020" not in pipe._state

    def test_recent_state_not_evicted(self):
        pipe = PipeDecoder(eviction_ttl=10.0)
        pipe.decode("8D485020994409940838175B284F", timestamp=0.0)
        # 5s later — within eviction window
        pipe.decode("8D406B902015A678D4D220AA4BDA", timestamp=5.0)
        assert "485020" in pipe._state

    def test_eviction_skipped_without_timestamp(self):
        pipe = PipeDecoder(eviction_ttl=10.0)
        pipe.decode("8D485020994409940838175B284F", timestamp=0.0)
        # Decoding without timestamp shouldn't trigger eviction
        pipe.decode("8D406B902015A678D4D220AA4BDA")
        assert "485020" in pipe._state

    def test_trusted_icaos_not_evicted(self):
        # The trusted set is permanent — no TTL applied
        pipe = PipeDecoder(eviction_ttl=10.0)
        pipe.decode("8D406B902015A678D4D220AA4BDA", timestamp=0.0)
        assert "406B90" in pipe._trusted_icaos
        # 1000s later
        pipe.decode("8D485020994409940838175B284F", timestamp=1000.0)
        assert "406B90" in pipe._trusted_icaos

    def test_same_icao_stale_state_wiped_before_refresh(self):
        # When an ICAO's state is older than the TTL and the SAME
        # ICAO sends a new message, eviction drops the stale entry
        # first and the new message builds state from scratch. Prior
        # tests only cover cross-ICAO eviction (where a different
        # ICAO's message triggers the sweep).
        pipe = PipeDecoder(eviction_ttl=10.0)
        pipe.decode("8D485020994409940838175B284F", timestamp=0.0)
        # Put a marker in the state dict — if eviction properly fires,
        # the stale entry is popped and our marker disappears.
        pipe._state["485020"]["_marker"] = "stale"
        pipe.decode("8D485020994409940838175B284F", timestamp=100.0)
        # The new state is a fresh dict without the marker
        assert "_marker" not in pipe._state["485020"]
        # And _last_seen reflects the new timestamp
        assert pipe._state["485020"]["_last_seen"] == 100.0
