"""Tests for pyModeS.PipeDecoder."""

from typing import ClassVar

import pytest

from pyModeS import PipeDecoder


class TestPipeDecoderSkeleton:
    def test_construction_defaults(self):
        pipe = PipeDecoder()
        assert pipe.stats == {
            "total": 0,
            "decoded": 0,
            "crc_fail": 0,
            "pending_pairs": 0,
            "altitude_mismatch": 0,
            "velocity_mismatch": 0,
            "position_rejected": 0,
            "bootstrap_held": 0,
            "bootstrap_reset": 0,
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
            "altitude_mismatch": 0,
            "velocity_mismatch": 0,
            "position_rejected": 0,
            "bootstrap_held": 0,
            "bootstrap_reset": 0,
        }

    def test_surface_ref_propagates_to_decode(self):
        # Real DF18 BDS 0,6 surface movement from jet1090 corpus
        # (LFBO taxiway). Replaces the earlier synthetic NZCH vector.
        pipe = PipeDecoder(surface_ref="LFBO")
        result = pipe.decode("903a23ff426a4e65f7487a775d17")
        assert result["latitude"] == pytest.approx(43.62646, abs=0.001)
        assert result["longitude"] == pytest.approx(1.37476, abs=0.001)

    def test_full_dict_propagates_to_decode(self):
        from pyModeS._schema import _FULL_SCHEMA

        pipe = PipeDecoder(full_dict=True)
        result = pipe.decode("8D406B902015A678D4D220AA4BDA")
        for key in _FULL_SCHEMA:
            assert key in result


class TestKnownKwargPlumbing:
    def test_message_decode_accepts_known(self):
        from pyModeS import Message

        msg = Message("8D406B902015A678D4D220AA4BDA")
        # No-op for non-CommB messages, but the kwarg must be accepted
        result = msg.decode(known={"groundspeed": 420})
        assert result["df"] == 17

    def test_core_decode_accepts_known(self):
        from pyModeS import decode

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
        from pyModeS import Message

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
        from pyModeS import Message

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
        from pyModeS.decoder.bds._infer import infer

        # The ambiguous payload (from tests/test_bds_commb.py) decodes
        # plausibly as both BDS 5,0 (groundspeed=240) and BDS 6,0
        # (magnetic_heading=359°). Without `known`, the heuristic
        # dispatch order returns 5,0 first.
        ambiguous_payload = 0xFFBAA11E200472
        # Sanity-check: bare infer with no known returns 5,0 first
        assert infer(ambiguous_payload, 20)[0] == "5,0"

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
        from pyModeS._pipe import _DECODED_TO_KNOWN
        from pyModeS.decoder.bds._infer import (
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


class TestAltitudeMismatch:
    # Reference DF20 frame shared across these tests:
    #   ICAO = 4243D0, AC-code altitude = 3300 ft, BDS 5,0
    #   (roll, true_track, groundspeed, track_rate, true_airspeed)
    DF20 = "a000029cffbaa11e2004727281f1"

    def test_matching_anchor_keeps_bds_payload(self):
        pipe = PipeDecoder()
        # Pretend the aircraft is actually at ~3300 ft (the DF20's AC-code
        # reports 3300 ft); BDS payload must be preserved.
        pipe._adsb_altitude["4243D0"] = (1000.0, 3300.0)
        result = pipe.decode(self.DF20, timestamp=1001.0)
        assert result.get("altitude_mismatch") is None
        assert result["bds"] == "5,0"
        assert result["roll"] == pytest.approx(-0.527, abs=0.01)
        assert pipe.stats["altitude_mismatch"] == 0

    def test_mismatching_anchor_strips_bds_payload(self):
        pipe = PipeDecoder()
        # Anchor says the aircraft is at FL370; DF20's AC-code says 3300 ft.
        # Diff ≈ 33 700 ft — far outside any tolerance — likely a CRC
        # collision from another aircraft.
        pipe._adsb_altitude["4243D0"] = (1000.0, 37000.0)
        result = pipe.decode(self.DF20, timestamp=1001.0)
        assert result["altitude_mismatch"] is True
        assert result.get("bds") is None
        assert result.get("roll") is None
        assert result.get("true_track") is None
        assert result.get("groundspeed") is None
        # The header AC-code altitude itself is preserved so callers
        # can see why the message was rejected.
        assert result["altitude"] == 3300
        assert pipe.stats["altitude_mismatch"] == 1

    def test_no_anchor_passes_through(self):
        pipe = PipeDecoder()
        # Nothing in _adsb_altitude for this ICAO — can't cross-check.
        result = pipe.decode(self.DF20, timestamp=1001.0)
        assert result.get("altitude_mismatch") is None
        assert result["bds"] == "5,0"
        assert pipe.stats["altitude_mismatch"] == 0

    def test_stale_anchor_does_not_reject(self):
        pipe = PipeDecoder(eviction_ttl=60.0)
        # Anchor is a full 10 min old — trust it no more.
        pipe._adsb_altitude["4243D0"] = (0.0, 37000.0)
        result = pipe.decode(self.DF20, timestamp=601.0)
        assert result.get("altitude_mismatch") is None
        assert result["bds"] == "5,0"

    def test_rejection_does_not_pollute_state(self):
        pipe = PipeDecoder()
        pipe._adsb_altitude["4243D0"] = (1000.0, 37000.0)
        pipe.decode(self.DF20, timestamp=1001.0)
        # BDS 5,0 fields (groundspeed, true_track, true_airspeed, roll)
        # would normally be merged into per-ICAO state — rejection must
        # suppress that so a later ambiguous Comm-B isn't scored against
        # spurious values.
        assert "4243D0" not in pipe._state

    def test_adsb_anchor_populated_by_df17_position(self):
        pipe = PipeDecoder()
        # Real airborne position vector (BDS 0,5), altitude = 39000 ft,
        # ICAO 40058B. This message alone populates the anchor even
        # without its CPR pair (anchor only needs altitude, not lat/lon).
        pipe.decode("8D40058B58C901375147EFD09357", timestamp=1000.0)
        anchor = pipe._adsb_altitude.get("40058B")
        assert anchor is not None
        assert anchor == (1000.0, 39000.0)

    def test_tolerance_scales_with_time_gap(self):
        pipe = PipeDecoder()
        # Anchor at 35 000 ft. After 30 s the aircraft could (at 100 ft/s
        # max) be at most 3 000 ft off — a DF20 reporting 37 500 ft
        # (diff 2 500) stays within tolerance; 40 000 ft (diff 5 000)
        # does not. Using synthetic altitudes here rather than hand-
        # constructing DF20 frames: bypass the DF20 decode by
        # calling the internal check directly.
        pipe._adsb_altitude["4243D0"] = (0.0, 35000.0)
        result = {"altitude": 37500}
        rejected = pipe._reject_on_altitude_mismatch(result, "4243D0", 30.0)
        assert rejected is False
        result = {"altitude": 40500}  # diff 5500, tol=max(500, min(3000,5000))=3000
        rejected = pipe._reject_on_altitude_mismatch(result, "4243D0", 30.0)
        assert rejected is True

    def test_reset_clears_adsb_altitude(self):
        pipe = PipeDecoder()
        pipe._adsb_altitude["4243D0"] = (1000.0, 37000.0)
        pipe.reset()
        assert pipe._adsb_altitude == {}

    def test_eviction_drops_stale_adsb_altitude(self):
        pipe = PipeDecoder(eviction_ttl=60.0)
        pipe._adsb_altitude["4243D0"] = (0.0, 37000.0)
        # Next decode at t=100 (beyond the 60 s TTL) triggers eviction.
        pipe.decode("8D406B902015A678D4D220AA4BDA", timestamp=100.0)
        assert "4243D0" not in pipe._adsb_altitude


class TestDF17AltitudeMismatch:
    """DF17/18 TC=5-18 airborne positions carry their own AC-code
    altitude (BDS 0,5). A CRC-lucky FRUIT phantom whose altitude jumps
    thousands of feet from the running ADS-B anchor should be rejected
    before it can contaminate the altitude trace or poison CPR pairing.
    """

    # Real-world phantom lifted from EDDB->EHAM KLM90J on 2025-04-13:
    # surrounding TC=11 frames all decode to 34 000 ft; this one decodes
    # to 27 900 ft while sitting in a stable cruise segment.
    REAL_POS = "8D48455658AF82FB9200E0A1E0EF"  # alt=34000
    PHANTOM_POS = "8D4845565C6AAA206D6E6095C950"  # alt=27900

    def test_matching_anchor_keeps_position(self):
        pipe = PipeDecoder()
        pipe._adsb_altitude["484556"] = (1000.0, 34000.0)
        r = pipe.decode(self.REAL_POS, timestamp=1001.0)
        assert r.get("altitude_mismatch") is None
        assert r["altitude"] == 34000
        assert r["cpr_lat"] is not None

    def test_mismatching_anchor_flags_and_clears_cpr(self):
        pipe = PipeDecoder()
        pipe._adsb_altitude["484556"] = (1000.0, 34000.0)
        r = pipe.decode(self.PHANTOM_POS, timestamp=1001.0)
        assert r["altitude_mismatch"] is True
        # Header AC-code altitude preserved so callers see why flagged.
        assert r["altitude"] == 27900
        # cpr fields scrubbed so the phantom can't pair with neighbours.
        assert r.get("cpr_lat") is None
        assert r.get("cpr_lon") is None
        assert pipe.stats["altitude_mismatch"] == 1

    def test_no_anchor_passes_through(self):
        pipe = PipeDecoder()
        r = pipe.decode(self.PHANTOM_POS, timestamp=1001.0)
        assert r.get("altitude_mismatch") is None
        assert r["altitude"] == 27900

    def test_stale_anchor_does_not_reject(self):
        pipe = PipeDecoder(eviction_ttl=60.0)
        pipe._adsb_altitude["484556"] = (0.0, 34000.0)
        r = pipe.decode(self.PHANTOM_POS, timestamp=601.0)
        assert r.get("altitude_mismatch") is None

    def test_rejection_does_not_update_anchor(self):
        pipe = PipeDecoder()
        pipe._adsb_altitude["484556"] = (1000.0, 34000.0)
        pipe.decode(self.PHANTOM_POS, timestamp=1001.0)
        # Anchor must not have been overwritten with the phantom's 27 900 ft.
        assert pipe._adsb_altitude["484556"] == (1000.0, 34000.0)


class TestVelocityMismatch:
    # Real-world phantom lifted from OpenSky traffic for ICAO 484556
    # on 2025-04-13 04:37 UTC (EDDB->EHAM flight). The surrounding
    # CRC-valid TC=19 samples decode to (gs=445 kt, track=272°); the
    # phantom below sits 1.6 s after a real sample and decodes to
    # (gs=558 kt, track=340.9°) — a +113 kt, +69° jump that's
    # dynamically impossible on an airliner.
    REAL_VEL = "8D484556990DBE023008844B0DE0"  # gs=445, trk=272°
    PHANTOM_VEL = "8D484556990CB8423008844B2DE1"  # gs=558, trk=340.9°

    def test_matching_anchor_keeps_velocity(self):
        pipe = PipeDecoder()
        # Anchor close to the real sample's values — the real msg
        # should pass untouched.
        pipe._adsb_velocity["484556"] = (1000.0, 445.0, 272.0)
        result = pipe.decode(self.REAL_VEL, timestamp=1001.6)
        assert result.get("velocity_mismatch") is None
        assert result["groundspeed"] == 445
        assert result["track"] == pytest.approx(272.06, abs=0.1)

    def test_mismatching_anchor_strips_velocity(self):
        pipe = PipeDecoder()
        pipe._adsb_velocity["484556"] = (1000.0, 445.0, 272.0)
        result = pipe.decode(self.PHANTOM_VEL, timestamp=1001.6)
        assert result["velocity_mismatch"] is True
        assert result.get("groundspeed") is None
        assert result.get("track") is None
        assert result.get("vertical_rate") is None
        assert pipe.stats["velocity_mismatch"] == 1

    def test_no_anchor_passes_and_populates(self):
        pipe = PipeDecoder()
        result = pipe.decode(self.REAL_VEL, timestamp=1000.0)
        assert result.get("velocity_mismatch") is None
        assert result["groundspeed"] == 445
        anchor = pipe._adsb_velocity.get("484556")
        assert anchor is not None
        assert anchor[0] == 1000.0
        assert anchor[1] == 445.0
        assert anchor[2] == pytest.approx(272.06, abs=0.1)

    def test_stale_anchor_does_not_reject(self):
        pipe = PipeDecoder(eviction_ttl=60.0)
        # Anchor 10 min old — beyond TTL — skip the check.
        pipe._adsb_velocity["484556"] = (0.0, 445.0, 272.0)
        result = pipe.decode(self.PHANTOM_VEL, timestamp=601.0)
        assert result.get("velocity_mismatch") is None

    def test_rejection_does_not_pollute_anchor(self):
        pipe = PipeDecoder()
        pipe._adsb_velocity["484556"] = (1000.0, 445.0, 272.0)
        pipe.decode(self.PHANTOM_VEL, timestamp=1001.6)
        # The rejected phantom must not become the new anchor —
        # otherwise the next real msg would be measured against 558/340.
        anchor = pipe._adsb_velocity["484556"]
        assert anchor == (1000.0, 445.0, 272.0)

    def test_tolerance_scales_with_time_gap(self):
        pipe = PipeDecoder()
        pipe._adsb_velocity["4243D0"] = (0.0, 400.0, 90.0)
        # 30 s later, a real +100 kt + 60° change is physically plausible
        # (rate-3 turn + descent accel). Direct internal check.
        result = {"groundspeed": 500, "track": 150.0}
        rejected = pipe._reject_velocity_mismatch(result, "4243D0", 30.0)
        assert rejected is False
        # But a 1 s gap with a +100 kt jump is not plausible.
        result = {"groundspeed": 500, "track": 92.0}
        rejected = pipe._reject_velocity_mismatch(result, "4243D0", 1.0)
        assert rejected is True

    def test_reset_clears_adsb_velocity(self):
        pipe = PipeDecoder()
        pipe._adsb_velocity["484556"] = (1000.0, 445.0, 272.0)
        pipe.reset()
        assert pipe._adsb_velocity == {}

    def test_eviction_drops_stale_adsb_velocity(self):
        pipe = PipeDecoder(eviction_ttl=60.0)
        pipe._adsb_velocity["484556"] = (0.0, 445.0, 272.0)
        pipe.decode("8D406B902015A678D4D220AA4BDA", timestamp=100.0)
        assert "484556" not in pipe._adsb_velocity


class TestVerticalRatePlausibility:
    """TC=19 airborne-velocity frames carry vertical rate in a 9-bit
    signed field (±16 384 fpm step 64). A CRC-lucky phantom whose gs
    and track happen to match the real anchor but whose VR decodes to
    an impossible value (commercial airliner envelope is ~±6 000 fpm)
    should be rejected."""

    # Real-world phantom from KLM1775 EHAM->EDDB on 2025-04-13 08:47:56:
    # gs=481, track=82.8° (both match the aircraft), vr=-24 704 fpm.
    PHANTOM_VR = "8D4867C29911DF07AE0F12C99EC9"

    def test_implausible_vr_rejected_even_with_matching_anchor(self):
        pipe = PipeDecoder()
        # Anchor matches the phantom's gs/track, so the anchor check
        # alone would pass. The VR check must still fire.
        pipe._adsb_velocity["4867C2"] = (1000.0, 481.0, 82.8)
        r = pipe.decode(self.PHANTOM_VR, timestamp=1001.0)
        assert r["velocity_mismatch"] is True
        assert r.get("groundspeed") is None
        assert r.get("track") is None
        assert r.get("vertical_rate") is None
        assert pipe.stats["velocity_mismatch"] == 1

    def test_normal_vr_passes(self):
        pipe = PipeDecoder()
        # A real TC=19 with reasonable VR (the earlier EDDB->EHAM
        # KLM90J fixture — gs=445, track=272°, vr=+64).
        r = pipe.decode("8D484556990DBE021008840E71C9", timestamp=1000.0)
        assert r.get("velocity_mismatch") is None
        assert r["vertical_rate"] == 64


class TestBDS60HeadingMismatch:
    """DF20/21 Comm-B BDS 6,0 carries magnetic_heading — it should
    agree (within magnetic variation + wind-correction angle, ~60°)
    with the aircraft's ADS-B track. A 150°+ disagreement is a
    CRC-collision phantom from a different aircraft."""

    # Real-world phantom from KLM1775 EHAM->EDDB on 2025-04-13 08:46:57:
    # aircraft heading ~84°, this decodes as BDS 6,0 with hdg=240.8°.
    PHANTOM_BDS60 = "A8000BBDD5AA7D2E606C03601B7F"

    def test_matching_heading_keeps_bds60(self):
        pipe = PipeDecoder()
        # Real KLM1775 track ~84° — within tolerance of phantom hdg
        # would mean no rejection. But the phantom decodes to 240°,
        # so for THIS test use an anchor at 240° (flipped scenario).
        pipe._adsb_velocity["4867C2"] = (1000.0, 481.0, 240.0)
        r = pipe.decode(self.PHANTOM_BDS60, timestamp=1001.0)
        assert r.get("velocity_mismatch") is None
        assert r["bds"] == "6,0"
        assert r["magnetic_heading"] == pytest.approx(240.8, abs=0.5)

    def test_mismatching_heading_rejects_bds60(self):
        pipe = PipeDecoder()
        pipe._adsb_velocity["4867C2"] = (1000.0, 481.0, 84.0)
        r = pipe.decode(self.PHANTOM_BDS60, timestamp=1001.0)
        assert r["velocity_mismatch"] is True
        assert r.get("bds") is None
        assert r.get("magnetic_heading") is None
        assert r.get("mach") is None
        assert r.get("indicated_airspeed") is None
        assert pipe.stats["velocity_mismatch"] == 1

    def test_no_anchor_passes_through(self):
        pipe = PipeDecoder()
        r = pipe.decode(self.PHANTOM_BDS60, timestamp=1001.0)
        assert r.get("velocity_mismatch") is None
        assert r["bds"] == "6,0"

    def test_stale_anchor_does_not_reject(self):
        pipe = PipeDecoder(eviction_ttl=60.0)
        pipe._adsb_velocity["4867C2"] = (0.0, 481.0, 84.0)
        r = pipe.decode(self.PHANTOM_BDS60, timestamp=601.0)
        assert r.get("velocity_mismatch") is None

    def test_magnetic_variation_plus_wind_within_tolerance(self):
        """A real BDS 6,0 whose magnetic heading differs from true
        track by up to ~60° (worst-case magnetic variation + wind
        correction) must not be mistakenly rejected. Direct call to
        internal check with a synthetic diff of 55°."""
        pipe = PipeDecoder()
        pipe._adsb_velocity["4867C2"] = (0.0, 481.0, 84.0)
        result = {"magnetic_heading": 139.0}  # 55° off track
        assert pipe._reject_bds60_heading_mismatch(result, "4867C2", 1.0) is False


class TestBDS50VelocityMismatch:
    """DF20/21 Comm-B BDS 5,0 carries groundspeed + true_track that
    should agree with the per-ICAO ADS-B velocity anchor populated
    from CRC-valid TC=19 frames. A wildly-off BDS 5,0 payload with
    valid-range bits is almost certainly a CRC-collision phantom
    from a nearby aircraft."""

    # Real-world phantom from KLM88T EGLL->EHAM on 2025-04-19 11:16:
    # aircraft at ~372 kt / 60° track, this DF21 frame decodes cleanly
    # as BDS 5,0 with gs=250, tas=264, true_track=49.9°, roll=4.9°.
    PHANTOM_BDS50 = "A800138D8392391F605C845078B7"

    def test_matching_anchor_keeps_bds50(self):
        pipe = PipeDecoder()
        pipe._adsb_velocity["486651"] = (1000.0, 250.0, 50.0)  # anchor matches
        r = pipe.decode(self.PHANTOM_BDS50, timestamp=1001.0)
        assert r.get("velocity_mismatch") is None
        assert r["bds"] == "5,0"
        assert r["groundspeed"] == 250
        assert r["true_airspeed"] == 264

    def test_mismatching_gs_rejects_bds50(self):
        pipe = PipeDecoder()
        # Anchor says ~372 kt — phantom says 250 kt — Δ=122, tol=20 → reject
        pipe._adsb_velocity["486651"] = (1000.0, 372.0, 60.0)
        r = pipe.decode(self.PHANTOM_BDS50, timestamp=1001.0)
        assert r["velocity_mismatch"] is True
        assert r.get("bds") is None
        assert r.get("groundspeed") is None
        assert r.get("true_airspeed") is None
        assert r.get("true_track") is None
        assert r.get("roll") is None
        assert r.get("track_rate") is None
        assert pipe.stats["velocity_mismatch"] == 1

    def test_no_anchor_passes_through(self):
        pipe = PipeDecoder()
        r = pipe.decode(self.PHANTOM_BDS50, timestamp=1001.0)
        assert r.get("velocity_mismatch") is None
        assert r["bds"] == "5,0"

    def test_stale_anchor_does_not_reject(self):
        pipe = PipeDecoder(eviction_ttl=60.0)
        pipe._adsb_velocity["486651"] = (0.0, 372.0, 60.0)
        r = pipe.decode(self.PHANTOM_BDS50, timestamp=601.0)
        assert r.get("velocity_mismatch") is None

    def test_rejection_does_not_pollute_state(self):
        pipe = PipeDecoder()
        pipe._adsb_velocity["486651"] = (1000.0, 372.0, 60.0)
        pipe.decode(self.PHANTOM_BDS50, timestamp=1001.0)
        # State[icao] would normally pick up gs/tas/track from a
        # passing BDS 5,0 — rejection must suppress that so scoring
        # on the next ambiguous Comm-B isn't driven by phantom values.
        st = pipe._state.get("486651", {})
        assert st.get("groundspeed") is None
        assert st.get("track") is None


class TestBothPairFramesCarryPosition:
    """Each CPR pair produces two frames — an even and an odd. After the
    pair resolves, the decoded lat/lon must appear on BOTH result dicts:
    the later-arriving frame (via `_resolve_pair`) and the earlier
    frame that was pending (via retro-fill using a stored reference)."""

    # Real DF17 TC=11 pair for ICAO 40058B (from TestCprPairAccumulation
    # fixtures) — resolves around (49.81755, 6.08442). 40058B is pre-
    # seeded in _position_history in these tests so the ICAO is treated
    # as locked and the motion-consistency path runs (not bootstrap).
    PAIR_A = "8D40058B58C901375147EFD09357"
    PAIR_B = "8D40058B58C904A87F402D3B8C59"

    def test_locked_icao_fills_lat_lon_on_both_frames(self):
        pipe = PipeDecoder()
        pipe._position_history["40058B"] = [
            (49.81, 6.08, 990.0),
            (49.82, 6.09, 995.0),
        ]
        first = pipe.decode(self.PAIR_A, timestamp=1000.0)
        second = pipe.decode(self.PAIR_B, timestamp=1001.0)
        # Both dicts carry the resolved position.
        assert first["latitude"] == pytest.approx(49.81755, abs=0.001)
        assert first["longitude"] == pytest.approx(6.08442, abs=0.001)
        assert second["latitude"] == pytest.approx(49.81755, abs=0.001)
        assert second["longitude"] == pytest.approx(6.08442, abs=0.001)

    def test_bootstrap_retrofills_both_frames_of_every_pair(self):
        pipe = PipeDecoder()
        first_frames = []
        second_frames = []
        for i in range(5):
            first_frames.append(pipe.decode(self.PAIR_A, timestamp=1000.0 + 2 * i))
            second_frames.append(pipe.decode(self.PAIR_B, timestamp=1001.0 + 2 * i))
        # After the 5th pair the cluster locks and retro-fill runs over
        # every cluster member's held dicts — that's both halves of all
        # five pairs.
        assert "40058B" in pipe._position_history
        for r in first_frames + second_frames:
            assert r["latitude"] == pytest.approx(49.81755, abs=0.001)
            assert r["longitude"] == pytest.approx(6.08442, abs=0.001)

    def test_superseded_same_parity_frame_retrofilled(self):
        """Two F=0 frames arrive before any F=1. Under the old single-
        entry pending, the first F=0 was orphaned (result dict returned
        with latitude=None, never retro-filled). The pending deque pairs
        the arriving F=1 with EVERY fresh same-parity entry so both F=0
        frames get a lat/lon.
        """
        pipe = PipeDecoder()
        pipe._position_history["40058B"] = [
            (49.81, 6.08, 990.0),
            (49.82, 6.09, 995.0),
        ]
        # Two F=0 frames first (same cpr for simplicity; a real stream
        # would have slightly-different cpr values reflecting aircraft
        # motion, but the code path is identical).
        first_f0 = pipe.decode(self.PAIR_A, timestamp=1000.0)
        second_f0 = pipe.decode(self.PAIR_A, timestamp=1000.5)
        # F=1 arrives — pairs with the most-recent F=0 AND retro-fills
        # the orphaned first F=0 by resolving its own independent pair
        # against the same F=1 cpr.
        f1 = pipe.decode(self.PAIR_B, timestamp=1001.0)
        for r in (first_f0, second_f0, f1):
            assert r["latitude"] == pytest.approx(49.81755, abs=0.001)
            assert r["longitude"] == pytest.approx(6.08442, abs=0.001)

    def test_motion_reject_clears_both_frames(self):
        pipe = PipeDecoder()
        # Seed history on the wrong continent so the real Luxembourg
        # pair fails motion-consistency.
        pipe._position_history["40058B"] = [
            (70.0, -40.0, 990.0),
            (70.1, -40.1, 995.0),
        ]
        first = pipe.decode(self.PAIR_A, timestamp=1000.0)
        second = pipe.decode(self.PAIR_B, timestamp=1001.0)
        assert first.get("latitude") is None
        assert first.get("longitude") is None
        assert second.get("latitude") is None
        assert second.get("longitude") is None
        assert pipe.stats["position_rejected"] == 1


class TestCprPairAccumulation:
    # Many of these tests look at the CPR resolution math, not the
    # bootstrap cluster analysis. Pre-seed `_position_history` so the
    # ICAO is treated as already locked and the resolved lat/lon
    # propagates to the result dict.
    ICAO_40058B_SEED: ClassVar[list[tuple[float, float, float]]] = [
        (49.81, 6.08, 1446332395.0),
        (49.82, 6.09, 1446332398.0),
    ]

    def test_airborne_pair_resolves_lat_lon(self):
        pipe = PipeDecoder()
        pipe._position_history["40058B"] = list(self.ICAO_40058B_SEED)
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
        # Real DF18 even/odd surface pair from jet1090 corpus (LFBO
        # taxiway). Replaces the earlier synthetic NZCH pair.
        pipe = PipeDecoder(surface_ref="LFBO")
        pipe._position_history["3A23FF"] = [(43.63, 1.37, -1.0)]
        # First frame (even) — surface_ref already resolves it via
        # single-message path, so latitude is set after this call.
        # The pair logic stores it as pending anyway for the next.
        pipe.decode("903a23ff426a38565950432ebf95", timestamp=0.0)
        # Second frame (odd) — single-message also resolves via
        # surface_ref, but the pair would also resolve it.
        result = pipe.decode("903a23ff426a4e65f7487a775d17", timestamp=2.0)
        # Either path should yield the same lat/lon
        assert result["latitude"] == pytest.approx(43.62646, abs=0.001)
        assert result["longitude"] == pytest.approx(1.37476, abs=0.001)

    def test_same_parity_appends_to_deque(self):
        pipe = PipeDecoder()
        pipe.decode("8D40058B58C901375147EFD09357", timestamp=1000.0)
        # Decode another even frame from the same ICAO — pending is a
        # deque per parity, so both entries accumulate (they'll both
        # get paired against the next opposite-parity arrival).
        pipe.decode("8D40058B58C901375147EFD09357", timestamp=1001.0)
        assert pipe.stats["pending_pairs"] == 2
        assert len(pipe._pending_even["40058B"]) == 2

    def test_odd_first_pair_resolves(self):
        # Mirror of the airborne_pair test with frames reversed: the
        # odd frame arrives first (stored as pending), then the even
        # frame arrives and resolves. This exercises the cpr_format==0
        # "current is even, other is odd" branch of _resolve_pair that
        # the even-first test skips. Because the newer (even) frame
        # dictates the reported position, the expected lat/lon differs
        # slightly from the even-first test.
        pipe = PipeDecoder()
        pipe._position_history["40058B"] = list(self.ICAO_40058B_SEED)
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
        pipe.decode("903a23ff426a38565950432ebf95", timestamp=0.0)
        result = pipe.decode("903a23ff426a4e65f7487a775d17", timestamp=2.0)
        # No crash, and no lat/lon resolved
        assert "latitude" not in result
        assert "longitude" not in result

    def test_pair_different_nl_zones_returns_none(self, monkeypatch):
        # When the even/odd pair falls in different cprNL zones,
        # airborne_position_pair returns None. The pair is still
        # popped from pending but no lat/lon is merged into the result.
        # Easier to monkeypatch the pair solver than to hand-construct
        # a pair straddling a zone boundary. _pipe.py lazy-imports the
        # resolver from `pyModeS.position`, so we patch the re-export
        # there (not the underlying _cpr module).
        import pyModeS.position

        monkeypatch.setattr(
            pyModeS.position, "airborne_position_pair", lambda *a, **kw: None
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


class TestPositionMotionConsistency:
    ICAO = "40058B"

    def test_inconsistent_jump_rejected(self):
        # Seed two close positions, then inject a "jump" position far
        # beyond any aircraft's achievable distance.
        pipe = PipeDecoder()
        pipe._position_history[self.ICAO] = [
            (49.81, 6.08, 1000.0),
            (49.82, 6.09, 1001.0),
        ]
        # Manually invoke the helper with a position in Siberia; dt=5s
        # would allow ~4 km at 1500 kt + 2 km margin ≈ 6 km; we're
        # giving it thousands of km.
        assert pipe._motion_consistent(self.ICAO, 70.0, 160.0, 1006.0) is False

    def test_consistent_continuation_accepted(self):
        pipe = PipeDecoder()
        pipe._position_history[self.ICAO] = [
            (49.81, 6.08, 1000.0),
            (49.82, 6.09, 1001.0),
        ]
        # A plausible next sample — aircraft moves a few km in 2 s
        assert pipe._motion_consistent(self.ICAO, 49.83, 6.11, 1003.0) is True

    def test_empty_history_returns_true(self):
        # The helper alone (not the full bootstrap pipeline) returns
        # True when the ICAO isn't in _position_history — but in the
        # real decode path, pre-lock ICAOs are routed to _bootstrap
        # instead so this branch never emits lat/lon.
        pipe = PipeDecoder()
        assert pipe._motion_consistent(self.ICAO, 70.0, 160.0, 1001.0) is True

    def test_haversine_against_known_distance(self):
        from pyModeS._pipe import _haversine_km

        # Amsterdam -> Madrid ≈ 1480 km
        d = _haversine_km(52.308, 4.763, 40.472, -3.561)
        assert 1450 < d < 1520

    def test_rejection_increments_stat_and_clears_fields(self):
        # Use the real CPR pair that we know resolves around (49.82,
        # 6.08). Seed the history far away so the resolved pair is
        # rejected by motion_consistency.
        pipe = PipeDecoder()
        pipe._position_history[self.ICAO] = [
            (70.0, -40.0, 990.0),
            (70.1, -40.1, 995.0),
        ]
        pipe.decode("8D40058B58C901375147EFD09357", timestamp=1000.0)
        r = pipe.decode("8D40058B58C904A87F402D3B8C59", timestamp=1003.0)
        # Pair was resolved but rejected — lat/lon must be absent or None
        assert r.get("latitude") in (None, 0, False) or r["latitude"] is None
        assert pipe.stats["position_rejected"] == 1
        # Ring buffer still updated with the rejected position
        assert len(pipe._position_history[self.ICAO]) == 3

    def test_eviction_prunes_old_position_history(self):
        pipe = PipeDecoder(eviction_ttl=10.0)
        pipe._position_history[self.ICAO] = [
            (49.81, 6.08, 0.0),
            (49.82, 6.09, 5.0),
        ]
        # Next decode with timestamp=100 s triggers eviction; both
        # history entries are older than ttl=10 → buffer cleared.
        pipe.decode("8D485020994409940838175B284F", timestamp=100.0)
        assert self.ICAO not in pipe._position_history

    def test_reset_clears_position_history(self):
        pipe = PipeDecoder()
        pipe._position_history[self.ICAO] = [(49.81, 6.08, 1000.0)]
        pipe.reset()
        assert pipe._position_history == {}

    def test_max_speed_configurable(self):
        # Tight max_speed — a 10 NM jump in 1 s should be rejected
        # even though default 1500 kt would have allowed it.
        pipe = PipeDecoder(max_speed_kt=100.0, motion_margin_km=0.1)
        pipe._position_history[self.ICAO] = [
            (49.80, 6.00, 1000.0),
            (49.81, 6.01, 1001.0),
        ]
        # 1 s later, 20 km away → at 100 kt = 52 m/s this is impossible
        assert pipe._motion_consistent(self.ICAO, 49.90, 6.30, 1002.0) is False


class TestPositionBootstrap:
    ICAO = "40058B"
    # A set of K=5 mutually-consistent positions walking near Amsterdam
    # (aircraft cruising at ~500 kt).
    GOOD_CLUSTER: ClassVar[list[tuple[float, float, float]]] = [
        (52.30, 4.76, 1000.0),
        (52.31, 4.77, 1001.0),
        (52.32, 4.79, 1002.0),
        (52.33, 4.81, 1003.0),
        (52.34, 4.82, 1004.0),
    ]

    def test_hold_until_bootstrap_k_reached(self):
        """First K-1 pairs hold lat/lon in the bootstrap buffer; the
        result's `latitude` is None and the stat increments."""
        from pyModeS._pipe import _BOOTSTRAP_K

        pipe = PipeDecoder()
        for _i, (lat, lon, t) in enumerate(self.GOOD_CLUSTER[: _BOOTSTRAP_K - 1]):
            pipe._bootstrap_accumulate({}, self.ICAO, lat, lon, t)
        # Still held — no history yet
        assert self.ICAO not in pipe._position_history
        assert len(pipe._bootstrap[self.ICAO]) == _BOOTSTRAP_K - 1
        assert pipe.stats["bootstrap_held"] == _BOOTSTRAP_K - 1

    def test_cluster_locks_on_kth_consistent_candidate(self):
        """When K mutually-consistent candidates accumulate, cluster
        analysis promotes them all into _position_history and clears
        the bootstrap buffer."""
        pipe = PipeDecoder()
        for lat, lon, t in self.GOOD_CLUSTER:
            pipe._bootstrap_accumulate({}, self.ICAO, lat, lon, t)
        assert self.ICAO in pipe._position_history
        assert self.ICAO not in pipe._bootstrap
        # All five candidates were consistent → all kept (up to ring size).
        assert len(pipe._position_history[self.ICAO]) == 5
        assert pipe.stats["bootstrap_reset"] == 0

    def test_bootstrap_picks_majority_cluster(self):
        """Feed 3 real positions + 2 scattered phantoms. The cluster
        analysis should lock on the 3 reals; phantoms are dropped."""
        pipe = PipeDecoder()
        # 3 reals around Amsterdam
        reals = self.GOOD_CLUSTER[:3]
        # 2 phantoms scattered across the world
        phantoms = [(70.0, -40.0, 999.5), (-30.0, 120.0, 1001.5)]
        for lat, lon, t in reals + phantoms:
            pipe._bootstrap_accumulate({}, self.ICAO, lat, lon, t)
        # Locked on the reals
        assert self.ICAO in pipe._position_history
        hist = pipe._position_history[self.ICAO]
        # All cluster members should be near Amsterdam, not Siberia/Indian
        for lat, lon, _ in hist:
            assert 50 < lat < 55
            assert 0 < lon < 10

    def test_bootstrap_resets_when_all_phantoms(self):
        """All K candidates are mutually inconsistent (random scatter) —
        cluster analysis finds no anchor; buffer is reset and stat
        increments."""
        pipe = PipeDecoder()
        # Five phantoms spread around the globe
        scattered = [
            (70.0, -40.0, 1000.0),
            (-30.0, 120.0, 1001.0),
            (10.0, -150.0, 1002.0),
            (60.0, 80.0, 1003.0),
            (-60.0, 40.0, 1004.0),
        ]
        for lat, lon, t in scattered:
            pipe._bootstrap_accumulate({}, self.ICAO, lat, lon, t)
        assert self.ICAO not in pipe._position_history
        # Buffer reset → empty and accumulating afresh
        assert pipe._bootstrap[self.ICAO] == []
        assert pipe.stats["bootstrap_reset"] == 1

    def test_end_to_end_lock_after_five_real_pairs(self):
        """Integration through the real pair-decode path.

        The first 5 pairs are held during bootstrap; when the 5th
        arrives, cluster analysis picks the consistent group and
        retroactively fills in ``latitude``/``longitude`` on the
        earlier result dicts. The 6th pair is emitted through the
        normal motion-consistency check.
        """
        pipe = PipeDecoder()
        results = []
        for i in range(6):
            pipe.decode("8D40058B58C901375147EFD09357", timestamp=1000.0 + 2 * i)
            r = pipe.decode("8D40058B58C904A87F402D3B8C59", timestamp=1001.0 + 2 * i)
            results.append(r)
        # All six now have lat/lon — the first five via retro-fill on
        # lock, the sixth via the steady-state motion-consistency check.
        for r in results:
            assert r["latitude"] == pytest.approx(49.81755, abs=0.001)
            assert r["longitude"] == pytest.approx(6.08442, abs=0.001)

    def test_bootstrap_eviction_clears_stale_candidates(self):
        pipe = PipeDecoder(eviction_ttl=10.0)
        # Accumulate two stale candidates
        for lat, lon, t in self.GOOD_CLUSTER[:2]:
            pipe._bootstrap_accumulate({}, self.ICAO, lat, lon, t)
        # Trigger eviction by decoding a fresh message 100 s later
        pipe.decode("8D485020994409940838175B284F", timestamp=1100.0)
        assert self.ICAO not in pipe._bootstrap

    def test_reset_clears_bootstrap(self):
        pipe = PipeDecoder()
        pipe._bootstrap_accumulate({}, self.ICAO, 52.0, 4.0, 1000.0)
        pipe.reset()
        assert pipe._bootstrap == {}
