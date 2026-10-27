"""Uplink migration checks against frozen v2 outputs and the public API."""

import json
from pathlib import Path

import pytest

from pyModeS import Decoded, Message, decode
from pyModeS._schema import _FULL_SCHEMA
from pyModeS.errors import InvalidHexError, InvalidLengthError

# Frozen from v2 commit 8ae51f9's decoder/uplink.py, with deterministic
# synthetic short/long messages. Expected keys use the documented v3 mapping.
_V2_CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "golden_v2_uplink.json").read_text()
)


@pytest.mark.parametrize("case", _V2_CASES, ids=lambda case: case["msg"])
def test_v2_uplink_parity(case):
    expected = case["expected"].copy()
    if expected["uf"] == 11:
        # v3 adds parity validation against the fixed all-call address.
        expected["crc_valid"] = expected["icao"] == "FFFFFF"
    assert decode(case["msg"], uplink=True) == expected


# Independently encoded UF11 with PR=0, IC=II0 and address FFFFFF, plus a
# one-bit parity error and an interrogation encoded with address 000000.
_ALLCALL_CASES = [
    ("580000004A430A", "FFFFFF", True),
    ("580000004A430B", "FFFFFE", False),
    ("58000000E0EF0D", "000000", False),
]


@pytest.mark.parametrize(("msg", "address", "valid"), _ALLCALL_CASES)
@pytest.mark.parametrize("hint", [None, "000000", "FFFFFE", "ffffff"])
def test_allcall_uses_fixed_address(msg, address, valid, hint):
    message = Message(msg, uplink=True, icao_hint=hint)
    assert message.icao == address
    assert message.crc_valid is valid
    result = decode(msg, uplink=True, icao=hint)
    assert result == message.decode()
    assert result.uf == 11
    assert result.icao == address
    assert result.crc_valid is valid


@pytest.mark.parametrize("full_dict", [False, True])
def test_allcall_batch_validation(full_dict):
    results = decode(
        [msg for msg, _, _ in _ALLCALL_CASES], uplink=True, full_dict=full_dict
    )
    assert [result.crc_valid for result in results] == [True, False, False]


def test_direction_is_explicit():
    msg = "2097AB60000000"
    uplink = decode(msg, uplink=True)
    downlink = decode(msg)
    assert uplink.uf == 4
    assert uplink.bds == "2,B"
    assert "df" not in uplink
    assert "altitude" not in uplink
    assert downlink.df == 4
    assert "uf" not in downlink
    assert "altitude" in downlink
    assert uplink.icao != downlink.icao


@pytest.mark.parametrize(("rr", "bds"), [(0, None), (15, None), (16, "0,0")])
def test_reply_request_boundary(rr, bds):
    # UF4, DI0: BDS2 defaults to zero. RR16 is the first BDS request.
    msg = f"{(4 << 51) | (rr << 43):014X}"
    result = decode(msg, uplink=True)
    assert result.reply_request == rr
    assert result.get("bds") == bds


@pytest.mark.parametrize("length", [56, 112])
def test_message_input_types(length):
    msg = "20000000000000" if length == 56 else "A097AB600123456789ABCD123456"
    expected = decode(msg, uplink=True)
    for raw in (msg.lower(), bytes.fromhex(msg), int(msg, 16)):
        message = Message(raw, length=length, uplink=True)
        assert message.uf == expected.uf
        assert message.typecode is None
        assert message.decode() == expected
    assert isinstance(expected, Decoded)
    assert json.loads(expected.to_json()) == expected


def test_uplink_format_17_does_not_decode_adsb():
    message = Message("8D406B902015A678D4D220AA4BDA", uplink=True)
    assert message.uf == 17
    assert message.typecode is None
    assert set(message.decode()) == {"uf", "icao", "crc_valid"}


def test_icao_hint_checks_recovered_address():
    msg = "A097AB600123456789ABCD123456"
    assert decode(msg, uplink=True).icao == "F2EDD2"
    assert decode(msg, uplink=True).crc_valid is None
    assert decode(msg, uplink=True, icao="f2edd2").crc_valid is True
    assert decode(msg, uplink=True, icao="000000").crc_valid is False


@pytest.mark.parametrize("full_dict", [False, True])
def test_batch_preserves_order_and_errors(full_dict):
    messages = ["20000000000000", "XYZ", "20", "A097AB600123456789ABCD123456"]
    results = decode(messages, uplink=True, full_dict=full_dict)
    assert len(results) == len(messages)
    for index in (0, 3):
        assert results[index] == decode(
            messages[index], uplink=True, full_dict=full_dict
        )
    for index in (1, 2):
        assert results[index].raw_msg == messages[index]
        assert results[index].error
    if full_dict:
        assert all(set(result) == set(_FULL_SCHEMA) for result in results)


def test_full_dict_preserves_fields():
    result = decode("2097AB60000000", uplink=True, full_dict=True)
    assert set(result) == set(_FULL_SCHEMA)
    assert result.uf == 4
    assert result.df is None
    assert result.bds == "2,B"
    assert result.altitude is None


def test_batch_timestamps():
    messages = ["20000000000000", "20000000000000"]
    assert decode(messages, uplink=True, timestamps=[2.0, 1.0]) == decode(
        messages, uplink=True
    )
    assert decode([], uplink=True) == []
    with pytest.raises(ValueError, match="timestamps length"):
        decode(messages, uplink=True, timestamps=[1.0])


def test_payload_only_is_rejected():
    with pytest.raises(ValueError, match=r"payload=.*uplink"):
        decode(payload="2015A678D4D220", df=20, icao="406B90", uplink=True)


@pytest.mark.parametrize(
    ("raw", "error"), [("XYZ", InvalidHexError), ("20", InvalidLengthError)]
)
def test_invalid_input(raw, error):
    with pytest.raises(error):
        decode(raw, uplink=True)
