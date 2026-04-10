"""Unit tests for Comm-B BDS register decoders (bds10 through bds60)."""

from pymodes import decode
from pymodes.decoder.bds import bds10


# MB helper: for a 28-char (112-bit) hex message, the 56-bit MB
# payload is bytes 4..11 inclusive (bits 32..87 of the full message).
def mb_of(hex_msg: str) -> int:
    assert len(hex_msg) == 28
    full = int(hex_msg, 16)
    return (full >> 24) & ((1 << 56) - 1)


class TestBds10Validator:
    def test_valid_bds10_accepts(self):
        mb = mb_of("A800178D10010080F50000D5893C")
        assert bds10.is_bds10(mb) is True

    def test_all_zeros_rejected(self):
        assert bds10.is_bds10(0) is False

    def test_wrong_bds_id_rejected(self):
        # 0x20 prefix — that's BDS20, not BDS10.
        mb = mb_of("A0001838201584F23468207CDFA5")
        assert bds10.is_bds10(mb) is False

    def test_reserved_bits_nonzero_rejected(self):
        # Take the valid BDS10 MB and flip a bit in the reserved field
        # (MB bits 9-13). Setting bit 9 gives 0x00_80_00_00_00_00_00 on
        # top of the valid MB.
        mb = mb_of("A800178D10010080F50000D5893C")
        mb_bad = mb | (1 << (55 - 9))
        assert bds10.is_bds10(mb_bad) is False


class TestBds10Decoder:
    def test_full_field_decode(self):
        mb = mb_of("A800178D10010080F50000D5893C")
        result = bds10.decode_bds10(mb)
        assert result == {
            "config": False,
            "overlay_command_capability": False,
            "acas_operational": True,
            "mode_s_subnetwork_version": 0,
            "transponder_level5": False,
            "mode_s_specific_services": True,
            "uplink_elm_throughput": 0,
            "downlink_elm_throughput": 0,
            "aircraft_identification_capability": True,
            "squitter_capability": True,
            "surveillance_identifier_code": True,
            "common_usage_gicb_capability": True,
            "acas_hybrid_surveillance": False,
            "acas_resolution_advisory": True,
            "acas_rtca_version": 1,
            "dte_status": 0,
        }


class TestCommBRoutesToBds10:
    def test_df21_bds10_end_to_end(self):
        result = decode("A800178D10010080F50000D5893C")
        assert result["df"] == 21
        assert result["bds"] == "1,0"
        assert result["acas_operational"] is True
        assert result["mode_s_subnetwork_version"] == 0
        assert result["dte_status"] == 0
