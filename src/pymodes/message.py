"""Message base class and Decoded return type for pymodes v3.

This module defines two public types:

- Decoded: the dict subclass returned by decode() calls. Adds
  attribute access and a to_json() helper while behaving as a plain
  dict for json.dumps, pandas, iteration, and all dict operations.

- Message: the canonical internal representation of a Mode-S message.
  Holds a single int (56 or 112 bits) and exposes lazy cached_property
  accessors for df, icao, crc, typecode. Dispatches to decoder classes
  via decode().
"""

import json
from functools import cached_property
from typing import Any, Self

from pymodes._bits import crc_remainder, extract_unsigned
from pymodes.errors import InvalidHexError, InvalidLengthError, UnknownDFError

_HEX_CHARS = frozenset("0123456789abcdefABCDEF")
_VALID_LENGTHS = (56, 112)
_HEX_LENGTHS = (14, 28)


class Decoded(dict[str, Any]):
    """A decoded Mode-S message.

    Behaves as a plain dict in every way that matters: JSON-serializable
    via `json.dumps`, works with `pd.DataFrame([msg1, msg2, ...])`,
    iterable, unpackable via `**`, supports `.get("key")` for missing keys.

    Adds attribute access as a convenience:
        msg["typecode"]  # standard dict access
        msg.typecode     # attribute access — equivalent

    Missing-key semantics differ by access style:
        msg.get("foo")     # → None (safe lookup)
        msg["foo"]         # → KeyError (dict semantics)
        msg.foo            # → AttributeError (attribute semantics)
    """

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None

    def to_json(self, *, indent: int | None = None) -> str:
        """Serialize to a JSON string.

        Uses `default=str` as a defensive fallback for any
        non-JSON-native value, but every pymodes-decoded field is
        already JSON-native (int, float, str, bool, None, list, dict).
        """
        return json.dumps(self, indent=indent, default=str)


class Message:
    """Canonical internal representation of a Mode-S message.

    Stores the message as a Python int of 56 or 112 bits. Field
    accessors are lazy `cached_property`s that extract via
    `pymodes._bits.extract_unsigned`.

    Construction:
        Message("8D406B902015A678D4D220AA4BDA")  # long from hex
        Message("20000000000000")                 # short from hex
        Message(0x8D406B9020..., length=112)      # from int with explicit length

    Alternative construction from the payload alone:
        Message.from_payload("2015A678D4D220", df=17, icao="406B90")

    Note: no `__slots__` — `cached_property` stores cached values in
    `__dict__`, so slot-based instances are incompatible. Per the v3
    design, the small per-instance memory overhead is acceptable.
    """

    def __init__(
        self,
        msg: str | int | bytes,
        /,
        *,
        length: int | None = None,
        icao_hint: str | None = None,
    ) -> None:
        if isinstance(msg, str):
            self._n, self._length = self._parse_hex(msg)
        elif isinstance(msg, bytes):
            self._n = int.from_bytes(msg, "big")
            self._length = len(msg) * 8
            if self._length not in _VALID_LENGTHS:
                raise InvalidLengthError(actual=len(msg) * 2, expected=_HEX_LENGTHS)
        elif isinstance(msg, int):
            self._n = msg
            self._length = length if length is not None else 112
            if self._length not in _VALID_LENGTHS:
                raise InvalidLengthError(
                    actual=self._length // 4, expected=_HEX_LENGTHS
                )
        else:
            raise TypeError(f"msg must be str, int, or bytes; got {type(msg).__name__}")

        # Optional out-of-band ICAO hint for DF20/21 (and other
        # CRC-ICAO formats). Stored so `icao` can prefer it over the
        # CRC-derived value, and so `decode()` can set `icao_verified`.
        self._icao_hint = (
            self._normalize_icao(icao_hint) if icao_hint is not None else None
        )

    @staticmethod
    def _parse_hex(hexstr: str) -> tuple[int, int]:
        """Parse a hex string to (int value, bit length). Raises on error."""
        if not all(c in _HEX_CHARS for c in hexstr):
            raise InvalidHexError(hexstr)
        if len(hexstr) not in _HEX_LENGTHS:
            raise InvalidLengthError(actual=len(hexstr), expected=_HEX_LENGTHS)
        return int(hexstr, 16), len(hexstr) * 4

    @staticmethod
    def _normalize_icao(icao: str) -> str:
        """Validate and uppercase a 6-character hex ICAO address."""
        if len(icao) != 6 or not all(c in _HEX_CHARS for c in icao):
            raise InvalidHexError(icao)
        return icao.upper()

    @classmethod
    def from_payload(cls, payload: str, *, df: int, icao: str) -> Self:
        """Construct a Message from the 56-bit payload alone plus explicit headers.

        Useful when the full message is not available (e.g., logs that
        strip the outer CRC and header) but the caller knows the
        downlink format and ICAO out of band.

        Args:
            payload: The 56-bit payload (ADS-B ME / Comm-B MB) as 14
                hex characters.
            df: Downlink format (used to build the synthetic full message).
            icao: 24-bit ICAO address as a 6-character hex string.

        Returns:
            A Message with `_length == 112` representing a synthetic long
            message: header(df) + icao + payload + zero CRC. The CRC
            will not validate; `crc_valid` returns False.
        """
        if len(payload) != 14 or not all(c in _HEX_CHARS for c in payload):
            raise InvalidLengthError(actual=len(payload), expected=(14,))
        icao = cls._normalize_icao(icao)
        if df < 0 or df > 31:
            raise UnknownDFError(df)

        payload_int = int(payload, 16)
        icao_int = int(icao, 16)
        # Build 112-bit message: [df:5][ca:3][icao:24][payload:56][parity:24]
        # For from_payload we set ca=0 and parity=0 (synthetic, CRC not valid).
        n = (df << 107) | (icao_int << 80) | (payload_int << 24)
        obj = cls.__new__(cls)
        obj._n = n
        obj._length = 112
        return obj

    @cached_property
    def df(self) -> int:
        """Downlink format (bits 0-4)."""
        return extract_unsigned(self._n, 0, 5, self._length)

    @cached_property
    def icao(self) -> str:
        """24-bit ICAO address as uppercase hex string.

        For DF11/17/18, ICAO is at bits 8-31 of the message. For
        DF0/4/5/16/20/21, ICAO is derived from the CRC remainder
        (see crc property), unless an `icao_hint` was supplied at
        construction time, in which case the hint is used verbatim.
        """
        if self.df in (11, 17, 18):
            return f"{extract_unsigned(self._n, 8, 24, self._length):06X}"
        if self._icao_hint is not None:
            return self._icao_hint
        # DF0, 4, 5, 16, 20, 21 - ICAO comes from CRC
        return f"{self.crc:06X}"

    @cached_property
    def crc(self) -> int:
        """Raw 24-bit CRC remainder.

        For DF17/18, a valid message has crc == 0.
        For DF20/21 and other ICAO-encoded DFs, crc equals the ICAO
        address (possibly XORed with a BDS overlay from interrogation —
        see spec §11.4).
        """
        return crc_remainder(self._n, self._length)

    @cached_property
    def crc_valid(self) -> bool:
        """Whether the message CRC is consistent with a plausible ICAO."""
        if self.df in (17, 18):
            return self.crc == 0
        # For CRC-encoded ICAO formats (DF0/4/5/11/16/20/21), we can't verify
        # without out-of-band context. Return True if the computed remainder
        # falls in the plausible 24-bit range (always true by definition of
        # CRC), and rely on `icao_verified` in the decoded dict for stronger
        # verification.
        return self.df in (0, 4, 5, 11, 16, 20, 21)

    @cached_property
    def typecode(self) -> int | None:
        """ADS-B type code (bits 32-36), only defined for DF17/18."""
        if self.df not in (17, 18):
            return None
        return extract_unsigned(self._n, 32, 5, self._length)

    def decode(
        self,
        *,
        reference: tuple[float, float] | None = None,
        airport: str | tuple[float, float] | None = None,
    ) -> Decoded:
        """Decode every field of this message.

        Returns a Decoded dict containing df, icao, crc_valid, and
        whatever DF-specific fields the appropriate decoder class
        extracts. For DF20/21 the dict also includes `icao_verified`
        (True when an `icao_hint` was supplied at construction time,
        False when the ICAO was derived from the CRC remainder).

        Args:
            reference: Optional (lat, lon) for single-message airborne
                CPR resolution. Must be within 180 NM of the true
                position. If provided and the decoded message is a
                BDS 0,5 airborne position, the result dict gains
                `latitude` and `longitude` fields.
            airport: Optional airport ICAO code or (lat, lon) tuple for
                surface CPR (BDS 0,6) resolution. Required for surface
                position decoding; if omitted, only raw CPR fields are
                returned. Unknown airport codes raise ValueError.
        """
        # Import locally to avoid circular import at module load time
        from pymodes.decoder import _DECODERS

        result: Decoded = Decoded(
            {
                "df": self.df,
                "icao": self.icao,
                "crc_valid": self.crc_valid,
            }
        )

        if self.df in (20, 21):
            result["icao_verified"] = self._icao_hint is not None

        decoder_cls = _DECODERS.get(self.df)
        if decoder_cls is not None:
            decoder = decoder_cls(
                self._n, df=self.df, icao=self.icao, length=self._length
            )
            result.update(decoder.decode())

        self._resolve_position(result, reference=reference, airport=airport)

        return result

    @staticmethod
    def _resolve_position(
        result: Decoded,
        *,
        reference: tuple[float, float] | None,
        airport: str | tuple[float, float] | None,
    ) -> None:
        """Resolve single-msg CPR lat/lon in-place.

        Only runs for BDS 0,5 (airborne, needs `reference`) or BDS 0,6
        (surface, needs `airport`). Pair resolution is handled by
        PipeDecoder in phase 9.
        """
        bds = result.get("bds")
        if bds not in ("0,5", "0,6"):
            return
        if "cpr_format" not in result:
            return

        # Import locally to avoid loading position module at import time
        from pymodes.position import (
            airborne_position_with_ref,
            resolve_airport,
            surface_position_with_ref,
        )

        cpr_format = result["cpr_format"]
        cpr_lat = result["cpr_lat"]
        cpr_lon = result["cpr_lon"]

        if bds == "0,5":
            if reference is None:
                return
            lat_ref, lon_ref = reference
            lat, lon = airborne_position_with_ref(
                cpr_format, cpr_lat, cpr_lon, lat_ref, lon_ref
            )
        else:  # 0,6
            if airport is None:
                return
            lat_ref, lon_ref = resolve_airport(airport)
            lat, lon = surface_position_with_ref(
                cpr_format, cpr_lat, cpr_lon, lat_ref, lon_ref
            )

        result["latitude"] = lat
        result["longitude"] = lon
