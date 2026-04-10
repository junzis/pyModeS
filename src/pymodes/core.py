"""Top-level pymodes.decode() function.

This is the primary public API. It accepts a hex string (or the
56-bit payload with explicit header) and returns a Decoded dict
with every decodable field populated. When passed a list of hex
strings, it instead runs them through a transient PipeDecoder and
returns a list of Decoded dicts of the same length.
"""

import logging
from typing import Any, overload

from pymodes.message import Decoded, Message

_log = logging.getLogger("pymodes")


@overload
def decode(
    msg: str,
    *,
    payload: str | None = None,
    df: int | None = None,
    icao: str | None = None,
    reference: tuple[float, float] | None = None,
    surface_ref: str | tuple[float, float] | None = None,
    known: dict[str, Any] | None = None,
    full_dict: bool = False,
) -> Decoded: ...


@overload
def decode(
    msg: list[str],
    *,
    timestamps: list[float] | None = None,
    surface_ref: str | tuple[float, float] | None = None,
    full_dict: bool = False,
) -> list[Decoded]: ...


def decode(
    msg: Any = None,
    *,
    payload: Any = None,
    df: Any = None,
    icao: Any = None,
    reference: Any = None,
    surface_ref: Any = None,
    known: Any = None,
    full_dict: bool = False,
    timestamps: Any = None,
) -> Any:
    """Decode a single Mode-S message or a batch of messages.

    Single-message mode (``msg`` is a ``str``):

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

    Batch mode (``msg`` is a ``list[str]``):

    Args:
        msg: List of full Mode-S hex strings.
        timestamps: Parallel list of epoch seconds, one per message,
            used by the transient PipeDecoder for CPR pair matching
            and state TTL eviction. If omitted, list-position indices
            ``[0, 1, 2, ...]`` are synthesised as timestamps and a
            WARNING is logged — pair matching will still function
            but the synthesized values are not wall-clock times.
        surface_ref: Same as single-message mode.
        full_dict: Same as single-message mode.

    Batch mode returns a ``list[Decoded]`` of the same length as
    ``msg``. Messages that fail parsing are returned as error dicts
    (``{"error": ..., "raw_msg": ...}``), preserving alignment with
    the input list. The single-message kwargs ``payload``, ``df``,
    ``icao``, ``reference`` and ``known`` are not accepted in batch
    mode and raise ``TypeError``.

    Raises:
        InvalidHexError: if the input is not valid hex (single mode).
        InvalidLengthError: if the input length is wrong (single mode).
        ValueError: if both or neither of msg/payload is provided,
            if `payload` is given without `df`/`icao`, if
            `surface_ref` is an unknown ICAO airport code, or if
            `timestamps` length does not match `msg` length in
            batch mode.
        TypeError: if a single-message-only kwarg is passed in batch
            mode.
    """
    if isinstance(msg, list):
        # Batch path — reject single-message kwargs
        for kw_name, kw_val in (
            ("payload", payload),
            ("df", df),
            ("icao", icao),
            ("reference", reference),
            ("known", known),
        ):
            if kw_val is not None:
                raise TypeError(
                    f"{kw_name}= is not allowed in batch mode "
                    f"(received list of {len(msg)} messages)"
                )
        return _decode_batch(
            msg,
            timestamps=timestamps,
            surface_ref=surface_ref,
            full_dict=full_dict,
        )

    # Single-message path — batch-only kwarg must not sneak in
    if timestamps is not None:
        raise TypeError("timestamps= is only valid in batch mode (msg must be a list)")

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


def _decode_batch(
    msgs: list[str],
    *,
    timestamps: list[float] | None,
    surface_ref: str | tuple[float, float] | None,
    full_dict: bool,
) -> list[Decoded]:
    """Run ``msgs`` through a transient PipeDecoder and return results."""
    from pymodes import PipeDecoder

    if timestamps is None:
        _log.warning(
            "decode(list[str]) called without timestamps; "
            "falling back to list-position ordering"
        )
        timestamps = [float(i) for i in range(len(msgs))]
    elif len(timestamps) != len(msgs):
        raise ValueError(
            f"timestamps length {len(timestamps)} does not match "
            f"messages length {len(msgs)}"
        )

    pipe = PipeDecoder(surface_ref=surface_ref, full_dict=full_dict)
    return [pipe.decode(m, timestamp=t) for m, t in zip(msgs, timestamps, strict=True)]
