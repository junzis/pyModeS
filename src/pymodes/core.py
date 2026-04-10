"""Top-level pymodes.decode() function.

This is the primary public API. It accepts a hex string (or the
56-bit payload with explicit header) and returns a Decoded dict
with every decodable field populated.

Phase 1 ships only the single-message path with minimal fields (df,
icao, crc_valid). Later phases plug in the decoder classes via the
dispatch table in pymodes.decoder.
"""

from pymodes.message import Decoded, Message


def decode(
    msg: str | None = None,
    *,
    payload: str | None = None,
    df: int | None = None,
    icao: str | None = None,
) -> Decoded:
    """Decode a single Mode-S message.

    Args:
        msg: Full Mode-S message as a hex string. Either 14 chars (short,
            56 bits) or 28 chars (long, 112 bits).
        payload: Alternative input path - the 56-bit payload (ADS-B ME
            or Comm-B MB) alone as 14 hex chars. Requires `df` and
            `icao` to be provided.
        df: Downlink format override, used only when `payload` is
            provided.
        icao: ICAO address hint. For the `payload=` path it is required.
            For the `msg=` path it is optional: if provided for DF20/21
            it overrides the CRC-derived ICAO and sets
            `icao_verified=True` in the result (see spec 11.4).

    Returns:
        A Decoded dict with at least `df`, `icao`, and `crc_valid`.
        Additional fields are added by the decoder class dispatched
        based on DF.

    Raises:
        InvalidHexError: if the input is not valid hex.
        InvalidLengthError: if the input length is wrong.
        ValueError: if both or neither of msg/payload is provided, or
            if `payload` is given without `df`/`icao`.
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

    return message.decode()
