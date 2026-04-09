"""Top-level pymodes.decode() function.

This is the primary public API. It accepts a hex string (or ME field
with explicit header) and returns a DecodedMessage dict with every
decodable field populated.

Phase 1 ships only the single-message path with minimal fields (df,
icao, crc_valid). Later phases plug in the decoder classes via the
dispatch table in pymodes.decoder.
"""

from __future__ import annotations

from pymodes.message import DecodedMessage, Message


def decode(
    msg: str | None = None,
    *,
    me: str | None = None,
    df: int | None = None,
    icao: str | None = None,
) -> DecodedMessage:
    """Decode a single Mode-S message.

    Args:
        msg: Full Mode-S message as a hex string. Either 14 chars (short,
            56 bits) or 28 chars (long, 112 bits).
        me: Alternative input path — the 56-bit ME field alone as 14
            hex chars. Requires `df` and `icao` to be provided.
        df: Downlink format override, used only when `me` is provided.
        icao: ICAO address override (6-char hex), used only when `me`
            is provided, OR for DF20/21 where the caller knows the ICAO
            out of band (see spec §11.4).

    Returns:
        A DecodedMessage dict with at least `df`, `icao`, and `crc_valid`.
        Additional fields are added by the decoder class dispatched
        based on DF (see phases 2-4).

    Raises:
        InvalidHexError: if the input is not valid hex.
        InvalidLengthError: if the input length is wrong.
        ValueError: if both or neither of msg/me is provided.
    """
    if msg is None and me is None:
        raise ValueError("exactly one of msg or me must be provided")
    if msg is not None and me is not None:
        raise ValueError("exactly one of msg or me must be provided")

    if me is not None:
        if df is None or icao is None:
            raise ValueError("df and icao are required when me is provided")
        message = Message.from_me(me, df=df, icao=icao)
    else:
        assert msg is not None  # mypy narrowing
        message = Message(msg)

    # Phase 1 scaffold: return minimal header fields. Later phases
    # dispatch to decoder classes that add fields based on DF.
    result: DecodedMessage = DecodedMessage(
        {
            "df": message.df,
            "icao": message.icao,
            "crc_valid": message.crc_valid,
        }
    )
    return result
