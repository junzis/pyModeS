"""Tests for the Comm-B BDS inference dispatch."""

from pymodes import decode
from pymodes.decoder.bds._infer import infer


def mb_of(hex_msg: str) -> int:
    assert len(hex_msg) == 28
    full = int(hex_msg, 16)
    return (full >> 24) & ((1 << 56) - 1)


class TestInferFastPath:
    """Format-ID'd registers are detected by MB bits 0-7 before any
    heuristic validator runs. This is Phase 1 of the two-phase scan."""

    def test_bds10(self):
        mb = mb_of("A800178D10010080F50000D5893C")
        assert infer(mb) == ["1,0"]

    def test_bds17(self):
        mb = mb_of("A0000638FA81C10000000081A92F")
        assert infer(mb) == ["1,7"]

    def test_bds20(self):
        mb = mb_of("A000083E202CC371C31DE0AA1CCF")
        assert infer(mb) == ["2,0"]

    def test_bds30(self):
        # Synthetic BDS30 with issued_ra bit set.
        mb = 0x30_80_00_00_00_00_00
        assert infer(mb) == ["3,0"]


class TestInferSlowPath:
    """Non-format-ID'd registers are detected by heuristic validators in
    Phase 2. BDS40/50/60 are always tried; BDS44/45 are only tried when
    `include_meteo=True` (opt-in because they share bit patterns with
    non-meteorological traffic)."""

    def test_bds40(self):
        mb = mb_of("A000029C85E42F313000007047D3")
        assert "4,0" in infer(mb)

    def test_bds50(self):
        mb = mb_of("A000139381951536E024D4CCF6B5")
        assert "5,0" in infer(mb)

    def test_bds60(self):
        mb = mb_of("A00004128F39F91A7E27C46ADC21")
        assert "6,0" in infer(mb)

    def test_bds44_hidden_without_include_meteo(self):
        mb = mb_of("A0001692185BD5CF400000DFC696")
        assert "4,4" not in infer(mb, include_meteo=False)
        assert "4,4" in infer(mb, include_meteo=True)

    def test_bds45_hidden_without_include_meteo(self):
        mb = mb_of("A00004190001FB80000000000000")
        assert "4,5" not in infer(mb, include_meteo=False)
        assert "4,5" in infer(mb, include_meteo=True)


class TestInferEmptyAndAmbiguous:
    def test_all_zeros_returns_empty(self):
        assert infer(0) == []

    def test_commb_returns_bds_candidates_when_ambiguous(self):
        # BDS50 and BDS60 have no format ID; some messages satisfy both
        # validators. Construct one by finding a test vector that both
        # bds50.is_bds50 and bds60.is_bds60 accept.
        mb = mb_of("A8001EBCFFFB23286004A73F6A5B")
        candidates = infer(mb)
        if len(candidates) > 1:
            result = decode("A8001EBCFFFB23286004A73F6A5B")
            assert "bds_candidates" in result
            assert set(result["bds_candidates"]) == set(candidates)
