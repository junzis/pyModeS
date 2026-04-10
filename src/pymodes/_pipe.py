"""PipeDecoder — stateful streaming Mode-S decoder.

Processes messages one at a time, maintaining per-ICAO state across
calls so that:

- Comm-B BDS 5,0/6,0 disambiguation can use prior groundspeed/track/
  heading observations.
- DF20/21 ICAO verification can match against ICAOs learned from
  prior DF11/DF17/DF18 messages.
- Even/odd CPR frame pairs can be matched within a configurable
  time window to resolve absolute lat/lon without a reference.

Not thread-safe by default. Wrap with threading.Lock if concurrent
access is needed.

This file is the Plan 4b Task 4 skeleton: state tracking, pair
accumulation, and TTL eviction land in subsequent tasks.
"""

from __future__ import annotations

from typing import Any

from pymodes.errors import InvalidHexError, InvalidLengthError
from pymodes.message import Decoded, Message

# Maps decoded field names → "known" dict key names. The known
# keys MUST match what _infer._SCORE_FIELDS_BDS50 / _BDS60 expect,
# otherwise Phase 3 disambiguation will silently fail.
_DECODED_TO_KNOWN: dict[str, str] = {
    "groundspeed": "groundspeed",  # BDS 0,9 + BDS 0,6 + BDS 5,0
    "track": "track",  # BDS 0,9 + BDS 0,6
    "true_track": "track",  # BDS 5,0
    "heading": "heading",  # BDS 0,9 sub 3/4
    "magnetic_heading": "heading",  # BDS 6,0
    "indicated_airspeed": "ias",  # BDS 6,0
    "true_airspeed": "tas",  # BDS 5,0
    "mach": "mach",  # BDS 6,0
    "altitude": "altitude",  # informational; not in scoring tables
}


class PipeDecoder:
    """Stateful Mode-S decoder with per-ICAO state and CPR pair matching.

    Args:
        surface_ref: Surface CPR reference (ICAO airport code or
            (lat, lon) tuple). See pymodes.decode for details.
        full_dict: When True, every decoded result is populated with
            every key from _FULL_SCHEMA.
        pair_window: Maximum age difference (seconds) between an even
            and odd CPR frame for them to count as a pair. Default 10s.
        eviction_ttl: Per-ICAO state and pending CPR frames older than
            this many seconds are dropped lazily on the next decode
            call. Default 300s (5 minutes).
    """

    __slots__ = (
        "_eviction_ttl",
        "_full_dict",
        "_pair_window",
        "_pending_even",
        "_pending_odd",
        "_state",
        "_stats",
        "_surface_ref",
        "_trusted_icaos",
    )

    def __init__(
        self,
        *,
        surface_ref: str | tuple[float, float] | None = None,
        full_dict: bool = False,
        pair_window: float = 10.0,
        eviction_ttl: float = 300.0,
    ) -> None:
        self._surface_ref = surface_ref
        self._full_dict = full_dict
        self._pair_window = pair_window
        self._eviction_ttl = eviction_ttl
        self._state: dict[str, dict[str, Any]] = {}
        self._pending_even: dict[str, tuple[float, int, int]] = {}
        self._pending_odd: dict[str, tuple[float, int, int]] = {}
        self._trusted_icaos: set[str] = set()
        self._stats: dict[str, int] = {
            "total": 0,
            "decoded": 0,
            "crc_fail": 0,
            "pending_pairs": 0,
        }

    def decode(
        self,
        msg: str,
        *,
        timestamp: float | None = None,
    ) -> Decoded:
        """Decode a single message.

        Looks up any prior per-ICAO state and forwards it as ``known=``
        to :meth:`Message.decode` so Comm-B BDS 5,0/6,0 disambiguation
        can score candidates against recent observations. After the
        decode returns, tracked fields in the result are merged back
        into state for future calls.
        """
        self._stats["total"] += 1

        try:
            message = Message(msg)
        except (InvalidHexError, InvalidLengthError) as e:
            return Decoded({"error": str(e), "raw_msg": msg})

        # Look up prior state for this ICAO so the decoder can use it
        # for Comm-B BDS 5,0/6,0 disambiguation. Filter out housekeeping
        # keys (those starting with _) before passing as `known=`.
        icao = message.icao
        prior_state = self._state.get(icao)
        known: dict[str, Any] | None
        if prior_state:
            known = {k: v for k, v in prior_state.items() if not k.startswith("_")}
            if not known:
                known = None
        else:
            known = None

        result = message.decode(
            surface_ref=self._surface_ref,
            known=known,
            full_dict=self._full_dict,
        )

        self._stats["decoded"] += 1
        if result.get("crc_valid") is False:
            self._stats["crc_fail"] += 1

        # Promote ICAO to trusted set if this message has a plain-text
        # ICAO (DF17/18) and CRC validated. Subsequent DF20/21 decodes
        # for the same ICAO get icao_verified=True because the
        # CRC-derived ICAO matches one we've seen in plain text.
        #
        # DF11 is intentionally excluded: Message.crc_valid for DF11 is
        # hardcoded True (no actual II/SI syndrome check), so a corrupt
        # DF11 with a garbage ICAO would pollute the trusted set. When
        # full DF11 II/SI handling lands in a future plan, DF11 can join
        # the promotion list.
        if message.df in (17, 18) and result.get("crc_valid") is True:
            self._trusted_icaos.add(icao)
        elif message.df in (20, 21) and icao in self._trusted_icaos:
            result["icao_verified"] = True

        self._handle_cpr_pair(result, icao, timestamp)
        self._update_state(icao, result, timestamp)
        return result

    def _handle_cpr_pair(
        self,
        result: Decoded,
        icao: str,
        timestamp: float | None,
    ) -> None:
        """Resolve a CPR pair if the opposite parity frame is pending.

        Stores this frame as pending if no opposite is available.
        Skips entirely without a timestamp (pair matching needs a clock).
        """
        bds = result.get("bds")
        if bds not in ("0,5", "0,6") or "cpr_format" not in result:
            return
        if timestamp is None:
            return  # cannot pair without timestamps

        cpr_format = result["cpr_format"]
        cpr_lat = result["cpr_lat"]
        cpr_lon = result["cpr_lon"]

        # Pick which dict this frame goes into and which holds the opposite
        if cpr_format == 0:
            this_pending = self._pending_even
            other_pending = self._pending_odd
        else:
            this_pending = self._pending_odd
            other_pending = self._pending_even

        opposite = other_pending.get(icao)
        if opposite is not None:
            opp_t, opp_lat, opp_lon = opposite
            if abs(timestamp - opp_t) <= self._pair_window:
                # Pair found — resolve and pop
                self._resolve_pair(
                    result,
                    bds,
                    cpr_format,
                    cpr_lat,
                    cpr_lon,
                    opp_lat,
                    opp_lon,
                )
                other_pending.pop(icao, None)
                self._stats["pending_pairs"] = max(0, self._stats["pending_pairs"] - 1)
                return

        # No pair (or out of window) — store this frame as pending
        if icao not in this_pending:
            self._stats["pending_pairs"] += 1
        this_pending[icao] = (timestamp, cpr_lat, cpr_lon)

    def _resolve_pair(
        self,
        result: Decoded,
        bds: str,
        cpr_format: int,
        cpr_lat: int,
        cpr_lon: int,
        other_lat: int,
        other_lon: int,
    ) -> None:
        """Call the appropriate pair resolver and merge lat/lon in place."""
        from pymodes.position import (
            airborne_position_pair,
            resolve_surface_ref,
            surface_position_pair,
        )

        # The current frame is the newer one (we just received it).
        # cpr_format == 0 means we're the even, opposite is odd,
        # so even is newer.
        if cpr_format == 0:
            elat, elon = cpr_lat, cpr_lon
            olat, olon = other_lat, other_lon
            even_is_newer = True
        else:
            elat, elon = other_lat, other_lon
            olat, olon = cpr_lat, cpr_lon
            even_is_newer = False

        resolved: tuple[float, float] | None
        if bds == "0,5":
            resolved = airborne_position_pair(
                elat, elon, olat, olon, even_is_newer=even_is_newer
            )
        else:  # 0,6
            if self._surface_ref is None:
                return
            lat_ref, lon_ref = resolve_surface_ref(self._surface_ref)
            resolved = surface_position_pair(
                elat,
                elon,
                olat,
                olon,
                lat_ref=lat_ref,
                lon_ref=lon_ref,
                even_is_newer=even_is_newer,
            )

        if resolved is not None:
            result["latitude"], result["longitude"] = resolved

    def _update_state(
        self,
        icao: str,
        result: Decoded,
        timestamp: float | None,
    ) -> None:
        """Merge tracked fields from the result into per-ICAO state."""
        new_fields: dict[str, Any] = {}
        for decoded_key, known_key in _DECODED_TO_KNOWN.items():
            val = result.get(decoded_key)
            if val is not None:
                new_fields[known_key] = val

        # BDS 0,9 subtype 3/4 emits a polymorphic `airspeed` field
        # discriminated by `airspeed_type` ("IAS" or "TAS"). Route to
        # the appropriate known-state slot so Phase 3 disambiguation
        # can use it for downstream BDS 5,0/6,0 ambiguous Comm-B.
        airspeed = result.get("airspeed")
        airspeed_type = result.get("airspeed_type")
        if airspeed is not None and airspeed_type == "IAS":
            new_fields["ias"] = airspeed
        elif airspeed is not None and airspeed_type == "TAS":
            new_fields["tas"] = airspeed

        if not new_fields and timestamp is None:
            return

        existing = self._state.setdefault(icao, {})
        existing.update(new_fields)
        if timestamp is not None:
            existing["_last_seen"] = timestamp

    @property
    def stats(self) -> dict[str, int]:
        """Return a snapshot of internal counters."""
        return dict(self._stats)

    def reset(self) -> None:
        """Clear all per-ICAO state and counters."""
        self._state.clear()
        self._pending_even.clear()
        self._pending_odd.clear()
        self._trusted_icaos.clear()
        for k in self._stats:
            self._stats[k] = 0
