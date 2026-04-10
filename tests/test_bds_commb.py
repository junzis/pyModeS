"""Unit tests for Comm-B BDS register decoders (bds10 through bds60)."""

import pytest

from pymodes import decode
from pymodes.decoder.bds import bds10, bds17, bds20, bds30, bds40


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


class TestBds17Validator:
    def test_valid_bds17_accepts(self):
        mb = mb_of("A0000638FA81C10000000081A92F")
        assert bds17.is_bds17(mb) is True

    def test_all_zeros_rejected(self):
        assert bds17.is_bds17(0) is False

    def test_bds20_bit_required(self):
        # Take a valid BDS17 MB and clear MB bit 6 (the BDS20 flag at
        # cap-map index 6). Spec says BDS20 capability is mandatory for
        # aircraft emitting BDS17, so clearing it must fail validation.
        mb = mb_of("A0000638FA81C10000000081A92F")
        mb_bad = mb & ~(1 << (55 - 6))
        assert bds17.is_bds17(mb_bad) is False

    def test_trailing_nonzero_rejected(self):
        # v2's stricter heuristic: MB bits 24-55 must all be zero
        # (32 trailing zero bits). Set bit 24 to fail.
        mb = mb_of("A0000638FA81C10000000081A92F")
        mb_bad = mb | (1 << (55 - 24))
        assert bds17.is_bds17(mb_bad) is False


class TestBds17Decoder:
    def test_full_capability_list(self):
        mb = mb_of("A0000638FA81C10000000081A92F")
        result = bds17.decode_bds17(mb)
        assert result == {
            "supported_bds": [
                "0,5",
                "0,6",
                "0,7",
                "0,8",
                "0,9",
                "2,0",
                "4,0",
                "5,0",
                "5,1",
                "5,2",
                "6,0",
            ],
        }


class TestCommBRoutesToBds17:
    def test_df20_bds17_end_to_end(self):
        result = decode("A0000638FA81C10000000081A92F")
        assert result["df"] == 20
        assert result["bds"] == "1,7"
        assert "2,0" in result["supported_bds"]


class TestBds20Validator:
    def test_valid_bds20_accepts(self):
        mb = mb_of("A000083E202CC371C31DE0AA1CCF")
        assert bds20.is_bds20(mb) is True

    def test_all_zeros_rejected(self):
        assert bds20.is_bds20(0) is False

    def test_wrong_bds_id_rejected(self):
        # BDS10 MB has prefix 0x10, not 0x20.
        mb = mb_of("A800178D10010080F50000D5893C")
        assert bds20.is_bds20(mb) is False

    def test_hash_char_rejected(self):
        # A forged MB with BDS ID 0x20 and all-zero callsign bits.
        # Character index 0 maps to '#' (invalid) in the ASCII-derived
        # callsign table, so every one of the 8 six-bit slots would
        # decode to '#' and the validator must reject.
        mb = 0x20 << 48  # prefix 0x20, callsign bits all zero
        assert bds20.is_bds20(mb) is False

    def test_mid_range_hash_char_rejected(self):
        # Indices 33-36 also map to '#' (invalid) but the original v2
        # heuristic missed them. Force MB prefix 0x20 with all 8
        # callsign slots at index 33 — validator must reject.
        cs = 0
        for _ in range(8):
            cs = (cs << 6) | 33
        mb = (0x20 << 48) | cs
        assert bds20.is_bds20(mb) is False

    def test_all_space_callsign_accepted(self):
        # Index 32 is ASCII space and is a valid (if blank) callsign
        # character. Pin the boundary so a future edit to the invalid
        # set cannot over-reject index 32. The decoder strips leading
        # and trailing whitespace, so an all-space callsign returns "".
        cs = 0
        for _ in range(8):
            cs = (cs << 6) | 32
        mb = (0x20 << 48) | cs
        assert bds20.is_bds20(mb) is True
        assert bds20.decode_bds20(mb) == {"callsign": ""}


class TestBds20Decoder:
    def test_decodes_callsign(self):
        mb = mb_of("A000083E202CC371C31DE0AA1CCF")
        assert bds20.decode_bds20(mb) == {"callsign": "KLM1017"}

    def test_decodes_second_callsign(self):
        mb = mb_of("A0001993202422F2E37CE038738E")
        assert bds20.decode_bds20(mb) == {"callsign": "IBK2873"}

    def test_decodes_padded_callsign(self):
        # v2 display was "EXS2MF__" (two trailing underscores as the
        # space placeholder). v3 strips trailing whitespace.
        mb = mb_of("A0001838201584F23468207CDFA5")
        assert bds20.decode_bds20(mb) == {"callsign": "EXS2MF"}


class TestCommBRoutesToBds20:
    def test_df20_bds20_end_to_end(self):
        result = decode("A000083E202CC371C31DE0AA1CCF")
        assert result["df"] == 20
        assert result["bds"] == "2,0"
        assert result["callsign"] == "KLM1017"


class TestBds30Validator:
    def test_valid_bds30_accepts(self):
        mb = 0x30_80_00_00_00_00_00
        assert bds30.is_bds30(mb) is True

    def test_all_zeros_rejected(self):
        assert bds30.is_bds30(0) is False

    def test_wrong_bds_id_rejected(self):
        # BDS20 prefix 0x20.
        mb = mb_of("A000083E202CC371C31DE0AA1CCF")
        assert bds30.is_bds30(mb) is False

    def test_tti_three_rejected(self):
        # Set TTI to 0b11 (reserved) — must reject.
        mb = 0x30_80_00_00_00_00_00 | (0b11 << (55 - 29))
        assert bds30.is_bds30(mb) is False

    def test_ara_reserved_ge_48_rejected(self):
        # Set ARA reserved bits (MB 15-21, 7 bits) to 48 = 0b0110000.
        mb = 0x30_80_00_00_00_00_00 | (48 << (55 - 21))
        assert bds30.is_bds30(mb) is False

    def test_ara_reserved_47_accepted(self):
        # Boundary: ARA reserved = 47 is the maximum accepted value.
        # Paired with test_ara_reserved_ge_48_rejected to pin the band.
        mb = 0x30_80_00_00_00_00_00 | (47 << (55 - 21))
        assert bds30.is_bds30(mb) is True


class TestBds30Decoder:
    def test_minimal_ra_no_threat(self):
        mb = 0x30_80_00_00_00_00_00
        result = bds30.decode_bds30(mb)
        assert result == {
            "threat_type_indicator": 0,
            "issued_ra": True,
            "corrective": False,
            "downward_sense": False,
            "increased_rate": False,
            "sense_reversal": False,
            "altitude_crossing": False,
            "positive": False,
            "no_below": False,
            "no_above": False,
            "no_left": False,
            "no_right": False,
            "ra_terminated": False,
            "multiple_threat": False,
        }

    def test_tti_1_icao_threat(self):
        # TTI=1 with a threat ICAO of 0xABCDEF in bits 30-53.
        # The ICAO occupies only bits 30-53 (24 bits); bits 54-55 are zero.
        tid = 0xABCDEF << 2  # shift into bits 30-53 of the 26-bit TID field
        mb = (
            0x30_80_00_00_00_00_00
            | (1 << (55 - 29))  # TTI = 0b01
            | tid  # TID in bits 30-55
        )
        result = bds30.decode_bds30(mb)
        assert result["threat_type_indicator"] == 1
        assert result["threat_icao"] == "ABCDEF"

    def test_tti_2_altitude_range_bearing(self):
        # TTI=2: MB bits 30-42 = AC13 altitude, bits 43-49 = 7-bit range,
        # bits 50-55 = 6-bit bearing. We use:
        #   altitude raw = 0x000 (decoded by altcode_to_altitude → None)
        #   range raw = 10 → (10 - 1) / 10 = 0.9 NM
        #   bearing raw = 3 → 6 * (3 - 1) + 3 = 15 degrees
        mb = (
            0x30_80_00_00_00_00_00
            | (0b10 << (55 - 29))  # TTI = 0b10
            | (10 << (55 - 49))  # range field, 7 bits ending at bit 49
            | (3 << (55 - 55))  # bearing field, 6 bits ending at bit 55
        )
        result = bds30.decode_bds30(mb)
        assert result["threat_type_indicator"] == 2
        assert result["threat_range"] == pytest.approx(0.9)
        assert result["threat_bearing"] == 15
        # Altitude raw == 0 → altcode_to_altitude returns None.
        assert result["threat_altitude"] is None

    def test_multi_flag_decode(self):
        # Set issued_ra (bit 8), corrective (bit 9), sense_reversal (bit 12),
        # no_above (bit 23), and multiple_threat (bit 27). The full dict
        # assertion pins every shift constant in decode_bds30 so a future
        # off-by-one in any ARA/RAC/terminal bit is caught immediately.
        mb = (
            0x30_00_00_00_00_00_00
            | (1 << (55 - 8))  # issued_ra
            | (1 << (55 - 9))  # corrective
            | (1 << (55 - 12))  # sense_reversal
            | (1 << (55 - 23))  # no_above
            | (1 << (55 - 27))  # multiple_threat
        )
        result = bds30.decode_bds30(mb)
        assert result == {
            "threat_type_indicator": 0,
            "issued_ra": True,
            "corrective": True,
            "downward_sense": False,
            "increased_rate": False,
            "sense_reversal": True,
            "altitude_crossing": False,
            "positive": False,
            "no_below": False,
            "no_above": True,
            "no_left": False,
            "no_right": False,
            "ra_terminated": False,
            "multiple_threat": True,
        }

    def test_tti_2_altitude_delegates_to_altcode(self):
        # Non-zero AC13 exercises the altcode_to_altitude delegation
        # (the zero-AC13 path in test_tti_2_altitude_range_bearing
        # short-circuits before any real decoding). AC13 = 0x1010
        # takes the Q=1 linear branch and decodes to 24600 ft; the
        # exact value matters less than proving a non-None int flows
        # through the delegation, pinning the bit-30..42 extraction.
        tti2 = 0b10 << (55 - 29)
        ac13 = 0x1010
        mb = 0x30_80_00_00_00_00_00 | tti2 | (ac13 << 13)
        result = bds30.decode_bds30(mb)
        assert result["threat_type_indicator"] == 2
        assert isinstance(result["threat_altitude"], int)
        assert result["threat_altitude"] == 24600

    def test_tti_2_range_and_bearing_none_sentinel(self):
        # TTI=2 with range_raw=0 and bearing_raw=0 → both decode to None
        # (the "value not available" sentinel). Verifies the > 0 else None
        # branch for both fields.
        mb = 0x30_80_00_00_00_00_00 | (0b10 << (55 - 29))
        # All TID bits zero by default; the raw fields are:
        #   altitude AC13 = 0 → None (via altcode_to_altitude)
        #   range = 0 → None
        #   bearing = 0 → None
        result = bds30.decode_bds30(mb)
        assert result["threat_type_indicator"] == 2
        assert result["threat_altitude"] is None
        assert result["threat_range"] is None
        assert result["threat_bearing"] is None


class TestCommBRoutesToBds30:
    def test_commb_bds30_end_to_end(self):
        # Synthetic DF20 message: wrap the minimal BDS30 MB into a
        # 112-bit frame. Header bits are zero; the decoder only reads
        # the header altcode (bits 19-31), so altitude = altcode_to_altitude(0) = None.
        mb = 0x30_80_00_00_00_00_00
        n = (20 << 107) | (mb << 24)
        msg_hex = f"{n:028X}"
        result = decode(msg_hex)
        assert result["df"] == 20
        assert result["bds"] == "3,0"
        assert result["issued_ra"] is True
        assert result["threat_type_indicator"] == 0


class TestBds40Validator:
    def test_valid_bds40_accepts(self):
        mb = mb_of("A000029C85E42F313000007047D3")
        assert bds40.is_bds40(mb) is True

    def test_all_zeros_rejected(self):
        assert bds40.is_bds40(0) is False

    def test_reserved_bits_39_46_nonzero_rejected(self):
        # Set one of the reserved bits (MB bit 39) in the valid vector.
        mb = mb_of("A000029C85E42F313000007047D3")
        mb_bad = mb | (1 << (55 - 39))
        assert bds40.is_bds40(mb_bad) is False

    def test_reserved_bits_51_52_nonzero_rejected(self):
        mb = mb_of("A000029C85E42F313000007047D3")
        mb_bad = mb | (1 << (55 - 51))
        assert bds40.is_bds40(mb_bad) is False

    def test_mcp_status_clear_but_altitude_nonzero_rejected(self):
        # Pin the wrong(0, 1, 12) call: status bit 0 clear but MCP
        # altitude raw (bits 1-12) nonzero → reject. Exercises the
        # 12-bit-width status-gate arithmetic path.
        mb = mb_of("A000029C85E42F313000007047D3")
        # Clear MCP status bit (bit 0). The altitude raw bits 1-12 are
        # already nonzero in the valid vector (raw = 188 = 3008 ft),
        # so the result is an inconsistent status=0/value=188 MB.
        mb_bad = mb & ~(1 << (55 - 0))
        assert bds40.is_bds40(mb_bad) is False

    def test_target_altitude_source_status_clear_but_value_set_rejected(self):
        # Pin the wrong(53, 54, 2) call: status bit 53 clear but
        # source value bits 54-55 nonzero → reject. Exercises the
        # 2-bit-width status-gate arithmetic path.
        # Start from all-zero MB then set source value = 3 (bits 54-55 = 0b11)
        # with status bit 53 left at 0. is_bds40 must reject.
        mb_bad = 0b11 << (55 - 55)  # bits 54-55 = 0b11
        assert bds40.is_bds40(mb_bad) is False


class TestBds40Decoder:
    def test_golden_vector(self):
        mb = mb_of("A000029C85E42F313000007047D3")
        result = bds40.decode_bds40(mb)
        assert result["selected_altitude_mcp"] == 3008
        assert result["selected_altitude_fms"] == 3008
        assert result["baro_pressure_setting"] == pytest.approx(1020.0)

    def test_all_statuses_absent(self):
        # decode_bds40 on an all-zero MB returns an empty dict because
        # every gated branch short-circuits. (is_bds40 rejects this MB
        # upstream; we exercise decode_bds40 in isolation.)
        assert bds40.decode_bds40(0) == {}

    def test_mode_bits_and_target_source_decode(self):
        # Set MCP mode status (bit 47) + vnav (48) + approach (50),
        # and target alt source status (bit 53) + value 3 (bits 54-55 = 0b11).
        # Pins the last two gated branches of decode_bds40 and
        # exercises _ALT_SOURCE[3] = "fms".
        mb = (
            (1 << (55 - 47))  # MCP mode status
            | (1 << (55 - 48))  # vnav_mode = True
            | (1 << (55 - 50))  # approach_mode = True
            | (1 << (55 - 53))  # target alt source status
            | (0b11 << (55 - 55))  # source value = 3 = "fms"
        )
        result = bds40.decode_bds40(mb)
        assert result == {
            "vnav_mode": True,
            "altitude_hold_mode": False,
            "approach_mode": True,
            "target_altitude_source": "fms",
        }


class TestCommBRoutesToBds40:
    def test_df20_bds40_end_to_end(self):
        result = decode("A000029C85E42F313000007047D3")
        assert result["df"] == 20
        assert result["bds"] == "4,0"
        assert result["selected_altitude_mcp"] == 3008
        assert result["baro_pressure_setting"] == pytest.approx(1020.0)
