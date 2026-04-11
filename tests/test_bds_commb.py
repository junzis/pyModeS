"""Unit tests for Comm-B BDS register decoders (bds10 through bds60)."""

import pytest

from pyModeS import decode
from pyModeS.decoder.bds import (
    bds10,
    bds17,
    bds20,
    bds30,
    bds40,
    bds44,
    bds45,
    bds50,
    bds60,
)


# Payload helper: for a 28-char (112-bit) hex message, the 56-bit
# payload is bytes 4..11 inclusive (bits 32..87 of the full message).
def payload_of(frame_hex: str) -> int:
    assert len(frame_hex) == 28
    full = int(frame_hex, 16)
    return (full >> 24) & ((1 << 56) - 1)


class TestBds10Validator:
    def test_valid_bds10_accepts(self):
        payload = payload_of("A800178D10010080F50000D5893C")
        assert bds10.is_bds10(payload) is True

    def test_all_zeros_rejected(self):
        assert bds10.is_bds10(0) is False

    def test_wrong_bds_id_rejected(self):
        # 0x20 prefix — that's BDS20, not BDS10.
        payload = payload_of("A0001838201584F23468207CDFA5")
        assert bds10.is_bds10(payload) is False

    def test_reserved_bits_nonzero_rejected(self):
        # Take the valid BDS10 payload and flip a bit in the reserved
        # field (payload bits 9-13). Setting bit 9 gives
        # 0x00_80_00_00_00_00_00 on top of the valid payload.
        payload = payload_of("A800178D10010080F50000D5893C")
        payload_bad = payload | (1 << (55 - 9))
        assert bds10.is_bds10(payload_bad) is False


class TestBds10Decoder:
    def test_full_field_decode(self):
        payload = payload_of("A800178D10010080F50000D5893C")
        result = bds10.decode_bds10(payload)
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
        payload = payload_of("A0000638FA81C10000000081A92F")
        assert bds17.is_bds17(payload) is True

    def test_all_zeros_rejected(self):
        assert bds17.is_bds17(0) is False

    def test_bds20_bit_required(self):
        # Take a valid BDS17 payload and clear payload bit 6 (the BDS20 flag at
        # cap-map index 6). Spec says BDS20 capability is mandatory for
        # aircraft emitting BDS17, so clearing it must fail validation.
        payload = payload_of("A0000638FA81C10000000081A92F")
        payload_bad = payload & ~(1 << (55 - 6))
        assert bds17.is_bds17(payload_bad) is False

    def test_trailing_nonzero_rejected(self):
        # v2's stricter heuristic: payload bits 24-55 must all be zero
        # (32 trailing zero bits). Set bit 24 to fail.
        payload = payload_of("A0000638FA81C10000000081A92F")
        payload_bad = payload | (1 << (55 - 24))
        assert bds17.is_bds17(payload_bad) is False


class TestBds17Decoder:
    def test_full_capability_list(self):
        payload = payload_of("A0000638FA81C10000000081A92F")
        result = bds17.decode_bds17(payload)
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
        payload = payload_of("A000083E202CC371C31DE0AA1CCF")
        assert bds20.is_bds20(payload) is True

    def test_all_zeros_rejected(self):
        assert bds20.is_bds20(0) is False

    def test_wrong_bds_id_rejected(self):
        # BDS10 payload has prefix 0x10, not 0x20.
        payload = payload_of("A800178D10010080F50000D5893C")
        assert bds20.is_bds20(payload) is False

    def test_hash_char_rejected(self):
        # A forged payload with BDS ID 0x20 and all-zero callsign bits.
        # Character index 0 maps to '#' (invalid) in the ASCII-derived
        # callsign table, so every one of the 8 six-bit slots would
        # decode to '#' and the validator must reject.
        payload = 0x20 << 48  # prefix 0x20, callsign bits all zero
        assert bds20.is_bds20(payload) is False

    def test_mid_range_hash_char_rejected(self):
        # Indices 33-36 also map to '#' (invalid) but the original v2
        # heuristic missed them. Force payload prefix 0x20 with all 8
        # callsign slots at index 33 — validator must reject.
        cs = 0
        for _ in range(8):
            cs = (cs << 6) | 33
        payload = (0x20 << 48) | cs
        assert bds20.is_bds20(payload) is False

    def test_all_space_callsign_accepted(self):
        # Index 32 is ASCII space and is a valid (if blank) callsign
        # character. Pin the boundary so a future edit to the invalid
        # set cannot over-reject index 32. The decoder strips leading
        # and trailing whitespace, so an all-space callsign returns "".
        cs = 0
        for _ in range(8):
            cs = (cs << 6) | 32
        payload = (0x20 << 48) | cs
        assert bds20.is_bds20(payload) is True
        assert bds20.decode_bds20(payload) == {"callsign": ""}


class TestBds20Decoder:
    def test_decodes_callsign(self):
        payload = payload_of("A000083E202CC371C31DE0AA1CCF")
        assert bds20.decode_bds20(payload) == {"callsign": "KLM1017"}

    def test_decodes_second_callsign(self):
        payload = payload_of("A0001993202422F2E37CE038738E")
        assert bds20.decode_bds20(payload) == {"callsign": "IBK2873"}

    def test_decodes_padded_callsign(self):
        # v2 display was "EXS2MF__" (two trailing underscores as the
        # space placeholder). v3 strips trailing whitespace.
        payload = payload_of("A0001838201584F23468207CDFA5")
        assert bds20.decode_bds20(payload) == {"callsign": "EXS2MF"}


class TestCommBRoutesToBds20:
    def test_df20_bds20_end_to_end(self):
        result = decode("A000083E202CC371C31DE0AA1CCF")
        assert result["df"] == 20
        assert result["bds"] == "2,0"
        assert result["callsign"] == "KLM1017"


class TestBds30Validator:
    def test_valid_bds30_accepts(self):
        payload = 0x30_80_00_00_00_00_00
        assert bds30.is_bds30(payload) is True

    def test_all_zeros_rejected(self):
        assert bds30.is_bds30(0) is False

    def test_wrong_bds_id_rejected(self):
        # BDS20 prefix 0x20.
        payload = payload_of("A000083E202CC371C31DE0AA1CCF")
        assert bds30.is_bds30(payload) is False

    def test_tti_three_rejected(self):
        # Set TTI to 0b11 (reserved) — must reject.
        payload = 0x30_80_00_00_00_00_00 | (0b11 << (55 - 29))
        assert bds30.is_bds30(payload) is False

    def test_ara_reserved_ge_48_rejected(self):
        # Set ARA reserved bits (payload 15-21, 7 bits) to 48 = 0b0110000.
        payload = 0x30_80_00_00_00_00_00 | (48 << (55 - 21))
        assert bds30.is_bds30(payload) is False

    def test_ara_reserved_47_accepted(self):
        # Boundary: ARA reserved = 47 is the maximum accepted value.
        # Paired with test_ara_reserved_ge_48_rejected to pin the band.
        payload = 0x30_80_00_00_00_00_00 | (47 << (55 - 21))
        assert bds30.is_bds30(payload) is True


class TestBds30Decoder:
    def test_minimal_ra_no_threat(self):
        payload = 0x30_80_00_00_00_00_00
        result = bds30.decode_bds30(payload)
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
        payload = (
            0x30_80_00_00_00_00_00
            | (1 << (55 - 29))  # TTI = 0b01
            | tid  # TID in bits 30-55
        )
        result = bds30.decode_bds30(payload)
        assert result["threat_type_indicator"] == 1
        assert result["threat_icao"] == "ABCDEF"

    def test_tti_2_altitude_range_bearing(self):
        # TTI=2: payload bits 30-42 = AC13 altitude, bits 43-49 = 7-bit range,
        # bits 50-55 = 6-bit bearing. We use:
        #   altitude raw = 0x000 (decoded by altcode_to_altitude → None)
        #   range raw = 10 → (10 - 1) / 10 = 0.9 NM
        #   bearing raw = 3 → 6 * (3 - 1) + 3 = 15 degrees
        payload = (
            0x30_80_00_00_00_00_00
            | (0b10 << (55 - 29))  # TTI = 0b10
            | (10 << (55 - 49))  # range field, 7 bits ending at bit 49
            | (3 << (55 - 55))  # bearing field, 6 bits ending at bit 55
        )
        result = bds30.decode_bds30(payload)
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
        payload = (
            0x30_00_00_00_00_00_00
            | (1 << (55 - 8))  # issued_ra
            | (1 << (55 - 9))  # corrective
            | (1 << (55 - 12))  # sense_reversal
            | (1 << (55 - 23))  # no_above
            | (1 << (55 - 27))  # multiple_threat
        )
        result = bds30.decode_bds30(payload)
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
        payload = 0x30_80_00_00_00_00_00 | tti2 | (ac13 << 13)
        result = bds30.decode_bds30(payload)
        assert result["threat_type_indicator"] == 2
        assert isinstance(result["threat_altitude"], int)
        assert result["threat_altitude"] == 24600

    def test_tti_2_range_and_bearing_none_sentinel(self):
        # TTI=2 with range_raw=0 and bearing_raw=0 → both decode to None
        # (the "value not available" sentinel). Verifies the > 0 else None
        # branch for both fields.
        payload = 0x30_80_00_00_00_00_00 | (0b10 << (55 - 29))
        # All TID bits zero by default; the raw fields are:
        #   altitude AC13 = 0 → None (via altcode_to_altitude)
        #   range = 0 → None
        #   bearing = 0 → None
        result = bds30.decode_bds30(payload)
        assert result["threat_type_indicator"] == 2
        assert result["threat_altitude"] is None
        assert result["threat_range"] is None
        assert result["threat_bearing"] is None


class TestCommBRoutesToBds30:
    def test_commb_bds30_end_to_end(self):
        # Synthetic DF20 message: wrap the minimal BDS30 payload into a
        # 112-bit frame. Header bits are zero; the decoder only reads
        # the header altcode (bits 19-31), so altitude = altcode_to_altitude(0) = None.
        payload = 0x30_80_00_00_00_00_00
        n = (20 << 107) | (payload << 24)
        msg_hex = f"{n:028X}"
        result = decode(msg_hex)
        assert result["df"] == 20
        assert result["bds"] == "3,0"
        assert result["issued_ra"] is True
        assert result["threat_type_indicator"] == 0


class TestBds40Validator:
    def test_valid_bds40_accepts(self):
        payload = payload_of("A000029C85E42F313000007047D3")
        assert bds40.is_bds40(payload) is True

    def test_all_zeros_rejected(self):
        assert bds40.is_bds40(0) is False

    def test_reserved_bits_39_46_nonzero_rejected(self):
        # Set one of the reserved bits (payload bit 39) in the valid vector.
        payload = payload_of("A000029C85E42F313000007047D3")
        payload_bad = payload | (1 << (55 - 39))
        assert bds40.is_bds40(payload_bad) is False

    def test_reserved_bits_51_52_nonzero_rejected(self):
        payload = payload_of("A000029C85E42F313000007047D3")
        payload_bad = payload | (1 << (55 - 51))
        assert bds40.is_bds40(payload_bad) is False

    def test_mcp_status_clear_but_altitude_nonzero_rejected(self):
        # Pin the wrong(0, 1, 12) call: status bit 0 clear but MCP
        # altitude raw (bits 1-12) nonzero → reject. Exercises the
        # 12-bit-width status-gate arithmetic path.
        payload = payload_of("A000029C85E42F313000007047D3")
        # Clear MCP status bit (bit 0). The altitude raw bits 1-12 are
        # already nonzero in the valid vector (raw = 188 = 3008 ft),
        # so the result is an inconsistent status=0/value=188 payload.
        payload_bad = payload & ~(1 << (55 - 0))
        assert bds40.is_bds40(payload_bad) is False

    def test_target_altitude_source_status_clear_but_value_set_rejected(self):
        # Pin the wrong(53, 54, 2) call: status bit 53 clear but
        # source value bits 54-55 nonzero → reject. Exercises the
        # 2-bit-width status-gate arithmetic path.
        # Start from all-zero payload then set source value = 3 (bits 54-55 = 0b11)
        # with status bit 53 left at 0. is_bds40 must reject.
        payload_bad = 0b11 << (55 - 55)  # bits 54-55 = 0b11
        assert bds40.is_bds40(payload_bad) is False


class TestBds40Decoder:
    def test_golden_vector(self):
        payload = payload_of("A000029C85E42F313000007047D3")
        result = bds40.decode_bds40(payload)
        assert result["selected_altitude_mcp"] == 3008
        assert result["selected_altitude_fms"] == 3008
        assert result["baro_pressure_setting"] == pytest.approx(1020.0)

    def test_all_statuses_absent(self):
        # decode_bds40 on an all-zero payload returns an empty dict because
        # every gated branch short-circuits. (is_bds40 rejects this payload
        # upstream; we exercise decode_bds40 in isolation.)
        assert bds40.decode_bds40(0) == {}

    def test_mode_bits_and_target_source_decode(self):
        # Set MCP mode status (bit 47) + vnav (48) + approach (50),
        # and target alt source status (bit 53) + value 3 (bits 54-55 = 0b11).
        # Pins the last two gated branches of decode_bds40 and
        # exercises _ALT_SOURCE[3] = "fms".
        payload = (
            (1 << (55 - 47))  # MCP mode status
            | (1 << (55 - 48))  # vnav_mode = True
            | (1 << (55 - 50))  # approach_mode = True
            | (1 << (55 - 53))  # target alt source status
            | (0b11 << (55 - 55))  # source value = 3 = "fms"
        )
        result = bds40.decode_bds40(payload)
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


class TestBds44Validator:
    def test_valid_bds44_accepts(self):
        payload = payload_of("A0001692185BD5CF400000DFC696")
        assert bds44.is_bds44(payload) is True

    def test_all_zeros_rejected(self):
        assert bds44.is_bds44(0) is False

    def test_fom_above_4_rejected(self):
        # Force FOM (payload bits 0-3) to 5, exceeding the v2 heuristic max.
        payload = payload_of("A0001692185BD5CF400000DFC696")
        payload_bad = (payload & ~(0xF << (55 - 3))) | (0b0101 << (55 - 3))
        assert bds44.is_bds44(payload_bad) is False

    def test_wind_speed_above_250_rejected(self):
        # Force wind_speed = 251 with valid FOM (≤ 4) and wind_status=1.
        # All other fields zero. Validator must reject on the range check.
        payload = (
            (1 << (55 - 3))  # FOM = 1 (payload bit 3 = LSB of 4-bit FOM)
            | (1 << (55 - 4))  # wind status
            | (251 << (55 - 13))  # wind speed raw 251
        )
        assert bds44.is_bds44(payload) is False

    def test_temperature_above_60_rejected(self):
        # Force wind valid (so the wind_status and wind range pass)
        # and temperature raw = 241 → +60.25 °C → reject.
        payload = (
            (1 << (55 - 3))
            | (1 << (55 - 4))
            | (50 << (55 - 13))  # wind speed 50 kt
            | (241 << (55 - 33))  # temperature raw = 241, sign=0 → +60.25 °C
        )
        assert bds44.is_bds44(payload) is False

    def test_temperature_below_minus_80_rejected(self):
        # Sign=1 magnitude=703 → signed = 703 - 1024 = -321 → -80.25 °C.
        payload = (
            (1 << (55 - 3))
            | (1 << (55 - 4))
            | (50 << (55 - 13))  # wind speed 50 kt
            | (1 << (55 - 23))  # temperature sign bit
            | (703 << (55 - 33))  # magnitude
        )
        assert bds44.is_bds44(payload) is False

    def test_all_zero_meteo_rejected(self):
        # Valid FOM, wind_status=1, but wind_speed=wind_dir=temp=0.
        # The compound check on the last line of is_bds44 must fire
        # (NOT the payload==0 early return, because FOM bit and wind status
        # bit make payload != 0).
        payload = (1 << (55 - 3)) | (1 << (55 - 4))
        assert bds44.is_bds44(payload) is False

    def test_pressure_status_clear_but_raw_nonzero_rejected(self):
        # Valid wind + non-zero temperature to clear upstream checks.
        # Pressure status=0, pressure raw = 1 → wrong_status rejects.
        payload = (
            (1 << (55 - 3))
            | (1 << (55 - 4))
            | (50 << (55 - 13))  # wind speed 50 kt
            | (100 << (55 - 33))  # temperature raw = 100 → +25 °C
            | (1 << (55 - 45))  # pressure raw bit 45 set, status bit 34 is 0
        )
        assert bds44.is_bds44(payload) is False


class TestBds44Decoder:
    def test_golden_vector(self):
        payload = payload_of("A0001692185BD5CF400000DFC696")
        result = bds44.decode_bds44(payload)
        assert result["wind_speed"] == 22
        assert result["wind_direction"] == pytest.approx(344.5, abs=0.5)
        assert result["static_air_temperature"] == pytest.approx(-48.75, abs=0.1)
        assert result["figure_of_merit"] == 1
        assert "static_pressure" not in result
        assert "humidity" not in result

    def test_multi_field_decode(self):
        # Exercise the pressure/turbulence/humidity branches that the
        # golden vector leaves empty. All three status bits set, with
        # representative raw values.
        payload = (
            (1 << (55 - 3))  # FOM = 1
            | (1 << (55 - 4))  # wind status
            | (50 << (55 - 13))  # wind speed 50 kt
            | (256 << (55 - 22))  # wind direction raw 256 → 180.0 deg
            | (1 << (55 - 34))  # pressure status
            | (1013 << (55 - 45))  # pressure 1013 hPa
            | (1 << (55 - 46))  # turbulence status
            | (0b10 << (55 - 48))  # turbulence level 2 (Moderate)
            | (1 << (55 - 49))  # humidity status
            | (32 << (55 - 55))  # humidity raw 32 → 50.0%
        )
        result = bds44.decode_bds44(payload)
        assert result["figure_of_merit"] == 1
        assert result["wind_speed"] == 50
        assert result["wind_direction"] == pytest.approx(180.0, abs=0.01)
        assert result["static_pressure"] == 1013
        assert result["turbulence"] == 2
        assert result["humidity"] == pytest.approx(50.0, abs=0.01)


class TestCommBBds44RequiresIncludeMeteo:
    def test_bds44_hidden_from_default_infer(self):
        # BDS44 is meteorological and only appears when infer() is
        # called with include_meteo=True. CommB.decode() does not
        # enable this flag in Plan 3, so the register is not routed
        # through pyModeS.decode() directly.
        result = decode("A0001692185BD5CF400000DFC696")
        assert result["df"] == 20
        assert result.get("bds") != "4,4"


class TestBds50Validator:
    def test_valid_bds50_accepts(self):
        payload = payload_of("A000139381951536E024D4CCF6B5")
        assert bds50.is_bds50(payload) is True

    def test_signed_roll_accepts(self):
        payload = payload_of("A0001691FFD263377FFCE02B2BF9")
        assert bds50.is_bds50(payload) is True

    def test_all_zeros_rejected(self):
        assert bds50.is_bds50(0) is False

    def test_roll_status_clear_but_sign_set_rejected(self):
        # Stricter than v2: v2 skips the sign bit in its wrongstatus
        # check, but v3 includes it because status=0/sign=1 is
        # suspicious. Pin this divergence so a future refactor cannot
        # silently restore v2's looser behavior.
        payload = 1 << (55 - 1)  # Only the roll sign bit set; roll status = 0.
        assert bds50.is_bds50(payload) is False

    def test_gs_status_clear_but_raw_nonzero_rejected(self):
        # Plain unsigned wrongstatus: gs status (bit 23) = 0 but gs
        # raw (bits 24-33) = 100 → inconsistent, must reject.
        payload = 100 << (55 - 33)  # gs raw = 100, status bit unset
        assert bds50.is_bds50(payload) is False

    def test_groundspeed_above_600_rejected(self):
        # Range check: gs > 600 kt rejected. gs scale is x2, so
        # raw = 301 -> 602 kt which must fail. Set gs status + raw.
        payload = (1 << (55 - 23)) | (301 << (55 - 33))
        assert bds50.is_bds50(payload) is False

    def test_tas_minus_gs_above_200_rejected(self):
        # Cross-field check: |tas - gs| > 200 kt rejected. Set gs=300
        # (raw 150) and tas=600 (raw 300), delta=300. Both status bits
        # and both values within their own ranges, so only the
        # cross-field check fires.
        payload = (
            (1 << (55 - 23))  # gs status
            | (150 << (55 - 33))  # gs raw = 150 → 300 kt
            | (1 << (55 - 45))  # tas status
            | (300 << (55 - 55))  # tas raw = 300 → 600 kt
        )
        assert bds50.is_bds50(payload) is False


class TestBds50Decoder:
    def test_golden_full_vector(self):
        payload = payload_of("A000139381951536E024D4CCF6B5")
        result = bds50.decode_bds50(payload)
        assert result["roll"] == pytest.approx(2.1, abs=0.1)
        assert result["true_track"] == pytest.approx(114.258, abs=0.01)
        assert result["groundspeed"] == 438
        assert result["track_rate"] == pytest.approx(0.125, abs=0.01)
        assert result["true_airspeed"] == 424

    def test_signed_roll(self):
        payload = payload_of("A0001691FFD263377FFCE02B2BF9")
        result = bds50.decode_bds50(payload)
        assert result["roll"] == pytest.approx(-0.35, abs=0.05)

    def test_track_signed_and_normalised(self):
        # Track with sign=1 mag=0 -> -90 deg (raw x 90/512 where
        # signed(0, 10, 1) = -1024, times 90/512 = -180.0), then
        # normalised to 180.0 via normalise_angle's % 360 wrap.
        # This is the only test that exercises the signed track path
        # AND the non-trivial normalisation branch.
        payload = (
            (1 << (55 - 11))  # track status
            | (1 << (55 - 12))  # track sign bit
            # track raw bits 13-22 remain 0
        )
        result = bds50.decode_bds50(payload)
        assert result["true_track"] == pytest.approx(180.0, abs=0.001)

    def test_track_rate_signed_minimum_matches_v2(self):
        # v2-parity pin: signed(0, 9, sign=1) = -512, x 8/256 = -16.0.
        # This is physically implausible (aircraft cannot turn at
        # 16 deg/s sustained) but matches v2 byte-for-byte. Document
        # the behaviour as a test so a future reviewer doesn't
        # "fix" it without understanding the v2 parity constraint.
        payload = (
            (1 << (55 - 34))  # track_rate status
            | (1 << (55 - 35))  # track_rate sign bit
            # track_rate magnitude bits 36-44 remain 0
        )
        result = bds50.decode_bds50(payload)
        assert result["track_rate"] == pytest.approx(-16.0, abs=0.001)


class TestCommBRoutesToBds50:
    def test_df20_bds50_end_to_end(self):
        result = decode("A000139381951536E024D4CCF6B5")
        assert result["df"] == 20
        assert result["bds"] == "5,0"
        assert result["groundspeed"] == 438
        assert result["true_airspeed"] == 424


class TestBds60Validator:
    def test_valid_bds60_accepts(self):
        payload = payload_of("A00004128F39F91A7E27C46ADC21")
        assert bds60.is_bds60(payload) is True

    def test_all_zeros_rejected(self):
        assert bds60.is_bds60(0) is False

    def test_hdg_status_clear_but_sign_set_rejected(self):
        # Stricter than v2: status=0 sign=1 is suspicious. Pins the
        # first wrongstatus check in is_bds60.
        payload = 1 << (55 - 1)  # only the heading sign bit set
        assert bds60.is_bds60(payload) is False

    def test_ias_above_500_rejected(self):
        # Range check: indicated airspeed > 500 kt rejects.
        # Set ias status + raw = 501 (raw is unsigned, <= 1023 max).
        payload = (1 << (55 - 12)) | (501 << (55 - 22))
        assert bds60.is_bds60(payload) is False

    def test_mach_exactly_one_accepted(self):
        # Mach = 1.0 is physically meaningful (sonic flight) and must
        # be accepted. Raw 250 * 2.048/512 = 1.0 exactly. Pins the
        # `> 1.0` vs `>= 1.0` boundary decision.
        payload = (1 << (55 - 23)) | (250 << (55 - 33))
        assert bds60.is_bds60(payload) is True

    def test_mach_above_one_rejected(self):
        # Range check: Mach > 1.0 rejects. Raw 251 * 2.048/512 ~= 1.004.
        payload = (1 << (55 - 23)) | (251 << (55 - 33))
        assert bds60.is_bds60(payload) is False


class TestBds60Decoder:
    def test_golden_full_vector(self):
        payload = payload_of("A00004128F39F91A7E27C46ADC21")
        result = bds60.decode_bds60(payload)
        assert result["magnetic_heading"] == pytest.approx(42.715, abs=0.01)
        assert result["indicated_airspeed"] == 252
        assert result["mach"] == pytest.approx(0.42, abs=0.005)
        assert result["baro_vertical_rate"] == -1920
        assert result["inertial_vertical_rate"] == -1920

    def test_heading_signed_and_normalised(self):
        # Heading with sign=1 mag=0 -> signed(0, 10, 1) = -1024, times
        # 90/512 = -180.0, normalised via % 360.0 -> 180.0 exactly.
        # Exercises the only bds60 code path that hits normalise_angle.
        payload = (1 << (55 - 0)) | (1 << (55 - 1))
        result = bds60.decode_bds60(payload)
        assert result["magnetic_heading"] == pytest.approx(180.0, abs=0.001)

    def test_vertical_rate_signed_negative(self):
        # Baro vr with sign=1 mag=0 -> -512 * 32 = -16384 ft/min, which
        # exceeds the |vr| <= 6000 range check and would reject.
        # So use mag = 500: signed(500, 9, 1) = -12, * 32 = -384 ft/min.
        # Pins the signed-vr-baro decode path independent of the
        # golden vector.
        payload = (
            (1 << (55 - 34))  # vrb status
            | (1 << (55 - 35))  # vrb sign
            | (500 << (55 - 44))  # vrb mag 500
        )
        result = bds60.decode_bds60(payload)
        assert result["baro_vertical_rate"] == -384


class TestCommBRoutesToBds60:
    def test_df20_bds60_end_to_end(self):
        result = decode("A00004128F39F91A7E27C46ADC21")
        assert result["df"] == 20
        assert result["bds"] == "6,0"
        assert result["indicated_airspeed"] == 252


class TestBds45Validator:
    def test_valid_bds45_accepts(self):
        payload = payload_of("A00004190001FB80000000000000")
        assert bds45.is_bds45(payload) is True

    def test_all_zeros_rejected(self):
        assert bds45.is_bds45(0) is False

    def test_reserved_tail_nonzero_rejected(self):
        payload = payload_of("A00004190001FB80000000000000")
        payload_bad = payload | 0x1  # set lowest reserved bit
        assert bds45.is_bds45(payload_bad) is False

    def test_temperature_above_60_rejected(self):
        # Force temp status + magnitude that exceeds 60 degC.
        # Raw 241 * 0.25 = 60.25 degC (sign=0).
        payload = (1 << (55 - 15)) | (241 << (55 - 25))
        assert bds45.is_bds45(payload) is False

    def test_temperature_below_minus_80_rejected(self):
        # Sign=1 mag=191 -> signed -321 * 0.25 = -80.25 degC.
        payload = (1 << (55 - 15)) | (1 << (55 - 16)) | (191 << (55 - 25))
        assert bds45.is_bds45(payload) is False

    def test_turbulence_status_clear_but_raw_nonzero_rejected(self):
        # wrong_status: bit 0 clear but bits 1-2 nonzero.
        payload = 0b01 << (55 - 2)
        assert bds45.is_bds45(payload) is False

    def test_pressure_status_clear_but_raw_nonzero_rejected(self):
        # wrong_status: bit 26 clear but bits 27-37 nonzero.
        payload = 1 << (55 - 37)
        assert bds45.is_bds45(payload) is False


class TestBds45Decoder:
    def test_golden_temperature_only(self):
        payload = payload_of("A00004190001FB80000000000000")
        result = bds45.decode_bds45(payload)
        assert result["static_air_temperature"] == pytest.approx(-4.5, abs=0.1)
        assert "turbulence" not in result
        assert "wind_shear" not in result
        assert "microburst" not in result
        assert "icing" not in result
        assert "wake_vortex" not in result
        assert "static_pressure" not in result
        assert "radio_height" not in result

    def test_temperature_gated_by_status_bit(self):
        # Decision D (v2 bug fix): when payload bit 15 (temp status) is 0,
        # the temperature must NOT appear in the result dict even if
        # the magnitude bits are nonzero. Exercise decode_bds45
        # directly since is_bds45 would reject this payload.
        payload = 0b111111111 << (55 - 25)  # magnitude = 511, status bit 15 = 0
        result = bds45.decode_bds45(payload)
        assert "static_air_temperature" not in result

    def test_multi_hazard_decode(self):
        # Exercise the 5 hazard-level branches + pressure + radio
        # height, which the golden vector leaves empty.
        payload = (
            (1 << (55 - 0))  # turbulence status
            | (0b10 << (55 - 2))  # turbulence level 2
            | (1 << (55 - 3))  # wind shear status
            | (0b01 << (55 - 5))  # wind shear level 1
            | (1 << (55 - 6))  # microburst status
            | (0b11 << (55 - 8))  # microburst level 3
            | (1 << (55 - 9))  # icing status
            | (0b10 << (55 - 11))  # icing level 2
            | (1 << (55 - 12))  # wake vortex status
            | (0b01 << (55 - 14))  # wake vortex level 1
            | (1 << (55 - 26))  # pressure status
            | (1013 << (55 - 37))  # pressure 1013 hPa
            | (1 << (55 - 38))  # radio height status
            | (500 << (55 - 50))  # radio height raw 500 -> 8000 ft
        )
        result = bds45.decode_bds45(payload)
        assert result["turbulence"] == 2
        assert result["wind_shear"] == 1
        assert result["microburst"] == 3
        assert result["icing"] == 2
        assert result["wake_vortex"] == 1
        assert result["static_pressure"] == 1013
        assert result["radio_height"] == 8000
        assert "static_air_temperature" not in result


class TestCommBBds45RequiresIncludeMeteo:
    def test_bds45_hidden_from_default_infer(self):
        # BDS45 is meteorological and only appears when infer() is
        # called with include_meteo=True. CommB.decode() does not
        # enable this flag in Plan 3.
        result = decode("A00004190001FB80000000000000")
        assert result["df"] == 20
        assert result.get("bds") != "4,5"
