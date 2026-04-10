"""Top-level pymodes.decode() function.

This is the primary public API. It accepts a hex string (or the
56-bit payload with explicit header) and returns a Decoded dict
with every decodable field populated.
"""

from typing import Any

from pymodes.message import Decoded, Message


def decode(
    msg: str | None = None,
    *,
    payload: str | None = None,
    df: int | None = None,
    icao: str | None = None,
    reference: tuple[float, float] | None = None,
    surface_ref: str | tuple[float, float] | None = None,
    known: dict[str, Any] | None = None,
    full_dict: bool = False,
) -> Decoded:
    """Decode a single Mode-S message.

    Args:
        msg: Full Mode-S message as a hex string. Either 14 chars
            (short, 56 bits) or 28 chars (long, 112 bits).
        payload: Alternative input path — the 56-bit payload alone
            as 14 hex chars. Requires `df` and `icao`.
        df: Downlink format override, used only with `payload`.
        icao: ICAO address hint. Optional for `msg=`; required for
            `payload=`. For the `msg=` path with DF20/21 it overrides
            the CRC-derived ICAO and sets `icao_verified=True`.
        reference: (lat, lon) for single-message airborne CPR
            position decoding (BDS 0,5). Must be within 180 NM of
            the true position. If omitted, only raw CPR fields are
            returned.
        surface_ref: Reference for surface CPR (BDS 0,6) decoding.
            Either an ICAO airport code (e.g. "EHAM") looked up in
            the shipped database, or an explicit (lat, lon) tuple
            (typically the receiver location). Must be within 45 NM
            of the true position. If omitted, only raw CPR fields
            are returned. Unknown airport codes raise ValueError.
        known: Optional aircraft state dict (e.g. {"groundspeed":
            420, "track": 90, "altitude": 35000}) used by the
            Comm-B BDS inference to disambiguate BDS 5,0 vs 6,0
            when both heuristic validators pass. Ignored for
            non-Comm-B downlink formats.
        full_dict: When True, the result dict is augmented with
            every key from `_FULL_SCHEMA`, defaulting missing keys
            to `None`. Useful for pandas/parquet workflows that
            need a uniform shape across messages.

    Returns:
        A Decoded dict with at least `df`, `icao`, `crc_valid`. For
        airborne/surface positions, `latitude` and `longitude` are
        added when sufficient context is provided.

    Raises:
        InvalidHexError: if the input is not valid hex.
        InvalidLengthError: if the input length is wrong.
        ValueError: if both or neither of msg/payload is provided,
            if `payload` is given without `df`/`icao`, or if
            `surface_ref` is an unknown ICAO airport code.
    """
    if msg is None and payload is None:
        raise ValueError("exactly one of msg or payload must be provided")
    if msg is not None and payload is not None:
        raise ValueError("exactly one of msg or payload must be provided")

    if payload is not None:
        if df is None or icao is None:
            raise ValueError("df and icao are required when payload is provided")
        message = Message.from_payload(payload, df=df, icao=icao)
    else:
        assert msg is not None
        message = Message(msg, icao_hint=icao)

    return message.decode(
        reference=reference,
        surface_ref=surface_ref,
        known=known,
        full_dict=full_dict,
    )
