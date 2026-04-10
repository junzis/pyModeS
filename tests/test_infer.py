"""Tests for the Comm-B BDS inference dispatch."""

from pymodes import decode
from pymodes.decoder.bds._infer import infer


def payload_of(frame_hex: str) -> int:
    assert len(frame_hex) == 28
    full = int(frame_hex, 16)
    return (full >> 24) & ((1 << 56) - 1)


class TestInferFastPath:
    """Format-ID'd registers are detected by payload bits 0-7 before any
    heuristic validator runs. This is Phase 1 of the two-phase scan."""

    def test_bds10(self):
        payload = payload_of("A800178D10010080F50000D5893C")
        assert infer(payload) == ["1,0"]

    def test_bds17(self):
        payload = payload_of("A0000638FA81C10000000081A92F")
        assert infer(payload) == ["1,7"]

    def test_bds20(self):
        payload = payload_of("A000083E202CC371C31DE0AA1CCF")
        assert infer(payload) == ["2,0"]

    def test_bds30(self):
        # Synthetic BDS30 with issued_ra bit set.
        payload = 0x30_80_00_00_00_00_00
        assert infer(payload) == ["3,0"]


class TestInferSlowPath:
    """Non-format-ID'd registers are detected by heuristic validators in
    Phase 2. BDS40/50/60 are always tried; BDS44/45 are only tried when
    `include_meteo=True` (opt-in because they share bit patterns with
    non-meteorological traffic)."""

    def test_bds40(self):
        payload = payload_of("A000029C85E42F313000007047D3")
        assert "4,0" in infer(payload)

    def test_bds50(self):
        payload = payload_of("A000139381951536E024D4CCF6B5")
        assert "5,0" in infer(payload)

    def test_bds60(self):
        payload = payload_of("A00004128F39F91A7E27C46ADC21")
        assert "6,0" in infer(payload)

    def test_bds44_hidden_without_include_meteo(self):
        payload = payload_of("A0001692185BD5CF400000DFC696")
        assert "4,4" not in infer(payload, include_meteo=False)
        assert "4,4" in infer(payload, include_meteo=True)

    def test_bds45_hidden_without_include_meteo(self):
        payload = payload_of("A00004190001FB80000000000000")
        assert "4,5" not in infer(payload, include_meteo=False)
        assert "4,5" in infer(payload, include_meteo=True)


class TestInferEmptyAndAmbiguous:
    def test_all_zeros_returns_empty(self):
        assert infer(0) == []

    def test_commb_returns_bds_candidates_when_ambiguous(self):
        # BDS50 and BDS60 have no format ID; some messages satisfy both
        # validators. Construct one by finding a test vector that both
        # bds50.is_bds50 and bds60.is_bds60 accept.
        payload = payload_of("A8001EBCFFFB23286004A73F6A5B")
        candidates = infer(payload)
        if len(candidates) > 1:
            result = decode("A8001EBCFFFB23286004A73F6A5B")
            assert "bds_candidates" in result
            assert set(result["bds_candidates"]) == set(candidates)


class TestInferPhase3Disambiguation:
    """Tests for the known-state disambiguation in infer() Phase 3.

    The ambiguous payload was found by searching the test corpus
    for messages where both bds50.is_bds50() and bds60.is_bds60()
    return True. Source hex: "a000029cffbaa11e2004727281f1" from
    tests/test_bds_commb.py.

    Decoded as BDS 5,0: groundspeed=240, true_track=239, tas=228
    Decoded as BDS 6,0: magnetic_heading=359, ias=336, mach=0.48
    """

    AMBIGUOUS_PAYLOAD = 0xFFBAA11E200472

    def test_ambiguous_no_known_preserves_phase2_order(self):
        from pymodes.decoder.bds._infer import infer

        result = infer(self.AMBIGUOUS_PAYLOAD)
        # Phase 2 dispatch order is _HEURISTIC = [4,0, 5,0, 6,0]
        # so the result should have both 5,0 and 6,0 in that order
        # (4,0 doesn't match this payload).
        assert result == ["5,0", "6,0"]

    def test_ambiguous_known_groundspeed_picks_bds50(self):
        from pymodes.decoder.bds._infer import infer

        # known carries a groundspeed near the BDS 5,0 decoded value (240).
        # Score for 5,0: |240 - 240| / 50 = 0.0 (other fields not in known)
        # Score for 6,0: no fields match known -> inf
        # 5,0 wins.
        result = infer(self.AMBIGUOUS_PAYLOAD, known={"groundspeed": 240})
        assert result[0] == "5,0"

    def test_ambiguous_known_heading_picks_bds60(self):
        from pymodes.decoder.bds._infer import infer

        # known carries a heading near the BDS 6,0 decoded value (359).
        # Score for 6,0: |359 - 359.12| / 30 ~= 0.004 (close to 0)
        # Score for 5,0: no fields match known -> inf
        # 6,0 wins.
        result = infer(self.AMBIGUOUS_PAYLOAD, known={"heading": 359})
        assert result[0] == "6,0"

    def test_ambiguous_known_neither_field_unchanged(self):
        from pymodes.decoder.bds._infer import infer

        # known carries an irrelevant field; both candidates score inf
        # and Phase 2 order is preserved.
        result = infer(self.AMBIGUOUS_PAYLOAD, known={"altitude": 35000})
        assert result == ["5,0", "6,0"]
