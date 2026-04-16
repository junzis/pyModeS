"""PipeDecoder — stateful streaming Mode-S decoder.

Processes messages one at a time, maintaining per-ICAO state across
calls so that:

- Comm-B BDS 5,0/6,0 disambiguation can use prior groundspeed/track/
  heading observations.
- DF20/21 ICAO verification can match against ICAOs learned from
  prior DF11/DF17/DF18 messages.
- Even/odd CPR frame pairs can be matched within a configurable
  time window to resolve absolute lat/lon without a reference.

Not thread-safe. Every `decode()` call mutates `_state`,
`_pending_even`, `_pending_odd`, `_trusted_icaos`, and `_stats`
without locking. Wrap the instance with a lock if multiple threads
feed it concurrently::

    import threading
    from pyModeS import PipeDecoder

    pipe = PipeDecoder()
    lock = threading.Lock()

    def decode_one(msg: str, ts: float):
        with lock:
            return pipe.decode(msg, timestamp=ts)

For single-producer pipelines (one reader thread draining a socket)
no locking is needed -- just don't share the decoder across threads.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any

from pyModeS._aero import gs_to_ias, gs_to_mach
from pyModeS.errors import InvalidHexError, InvalidLengthError
from pyModeS.message import Decoded, Message

# Size of the rolling per-ICAO position-history window used for the
# motion-consistency check. Five entries is large enough that a short
# burst of phantom positions at stream start cannot permanently poison
# the anchor: each new position is added to the ring buffer regardless
# of accept/reject verdict, so real positions eventually outnumber the
# phantoms and rotate them out.
_POSITION_HISTORY_SIZE = 5

# Number of candidate positions collected per ICAO before running the
# bootstrap cluster analysis that picks the initial anchor. With 5
# candidates, a scenario of up to 2 phantoms among real positions still
# yields a ≥ 3-member consistent cluster that out-votes the outliers.
# During bootstrap, resolved lat/lon is NOT emitted to the caller — we
# hold the candidates until a cluster is confirmed, then promote them
# into the rolling history.
_BOOTSTRAP_K = 5


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points, in km."""
    earth_radius_km = 6371.0088
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlam = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlam / 2) ** 2
    return 2 * earth_radius_km * asin(sqrt(a))


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

# BDS-payload fields cleared from a DF20 result that fails altitude
# cross-check. The `altitude` field itself is preserved (it's the
# 13-bit AC-code that triggered the mismatch — callers want it to
# see why the message was flagged).
_BDS_FIELDS_TO_CLEAR: tuple[str, ...] = (
    "bds",
    "bds_candidates",
    # BDS 1,0 / 1,7 — data-link capability / supported-BDS bitmap
    "supported_bds",
    # BDS 2,0 — aircraft identification
    "callsign",
    # BDS 4,0 — selected vertical intention
    "selected_altitude_mcp",
    "selected_altitude_fms",
    "baro_pressure_setting",
    "vnav_mode",
    "altitude_hold_mode",
    "approach_mode",
    "target_altitude_source",
    # BDS 4,4 / 4,5 — meteorological routine (only populated when
    # include_meteo is enabled, but strip the slots regardless)
    "wind_speed",
    "wind_direction",
    "static_air_temperature",
    "static_pressure",
    "humidity",
    "turbulence",
    "figure_of_merit",
    "wind_shear",
    "microburst",
    "icing",
    "radio_height",
    # BDS 5,0 — track and turn
    "true_airspeed",
    "true_track",
    "roll",
    "track_rate",
    "groundspeed",
    # BDS 6,0 — heading and speed
    "magnetic_heading",
    "indicated_airspeed",
    "mach",
    "baro_vertical_rate",
    "inertial_vertical_rate",
)


def _altitude_tolerance(dt: float) -> float:
    """Max plausible |ADS-B - Comm-B AC-code| altitude diff after dt seconds.

    Grows linearly with dt at 100 ft/s (≈ 6000 fpm, emergency descent
    rate for commercial jets), floored at 500 ft (signal noise +
    between-sample rounding) and capped at 5000 ft so stale ADS-B
    doesn't accept arbitrarily-wrong Comm-B altitudes.
    """
    return max(500.0, min(dt * 100.0, 5000.0))


class PipeDecoder:
    """Stateful Mode-S decoder with per-ICAO state and CPR pair matching.

    Args:
        surface_ref: Surface CPR reference (ICAO airport code or
            (lat, lon) tuple). See pyModeS.decode for details.
        full_dict: When True, every decoded result is populated with
            every key from _FULL_SCHEMA.
        pair_window: Maximum age difference (seconds) between an even
            and odd CPR frame for them to count as a pair. Default 10s.
        eviction_ttl: Per-ICAO state and pending CPR frames older than
            this many seconds are dropped lazily on the next decode
            call. Default 300s (5 minutes).
    """

    __slots__ = (
        "_adsb_altitude",
        "_bootstrap",
        "_eviction_ttl",
        "_full_dict",
        "_max_speed_kmps",
        "_motion_margin_km",
        "_pair_window",
        "_pending_even",
        "_pending_odd",
        "_position_history",
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
        max_speed_kt: float = 1500.0,
        motion_margin_km: float = 2.0,
    ) -> None:
        self._surface_ref = surface_ref
        self._full_dict = full_dict
        self._pair_window = pair_window
        self._eviction_ttl = eviction_ttl
        # 1500 kt is ~2x typical airliner cruise — loose enough not to
        # reject fast business jets or wind-boosted ground speed, tight
        # enough that a phantom position hundreds of km away cannot
        # masquerade as a continuation of the real track.
        self._max_speed_kmps = max_speed_kt * 1.852 / 3600.0
        self._motion_margin_km = motion_margin_km
        self._state: dict[str, dict[str, Any]] = {}
        self._pending_even: dict[str, tuple[float, int, int]] = {}
        self._pending_odd: dict[str, tuple[float, int, int]] = {}
        self._trusted_icaos: set[str] = set()
        # ADS-B-derived altitude anchor per ICAO, used to reject DF20
        # messages whose AC-code altitude is inconsistent with the
        # aircraft's known position altitude (a signature of a
        # CRC-collision attributing the reply to the wrong ICAO).
        # Populated only from CRC-valid DF17/18 airborne positions
        # (BDS 0,5); value is (timestamp, altitude_ft).
        self._adsb_altitude: dict[str, tuple[float, float]] = {}
        # Rolling window of the last _POSITION_HISTORY_SIZE resolved
        # (lat, lon, timestamp) tuples per ICAO. Only populated AFTER
        # the per-ICAO bootstrap cluster analysis has locked in an
        # initial anchor — until then an ICAO's candidates live in
        # `_bootstrap` instead.
        self._position_history: dict[str, list[tuple[float, float, float]]] = {}
        # Pre-lock bootstrap candidates per ICAO. An ICAO appears in
        # `_bootstrap` XOR `_position_history`: it moves from bootstrap
        # to history when a consistent cluster is detected among its
        # first _BOOTSTRAP_K resolved positions. Each entry carries a
        # reference to the result dict that produced it — when the
        # cluster locks, we retroactively set latitude/longitude on
        # those dicts so batch callers (who keep the list around) still
        # see the resolved positions for their early samples.
        self._bootstrap: dict[str, list[tuple[float, float, float, Decoded]]] = {}
        self._stats: dict[str, int] = {
            "total": 0,
            "decoded": 0,
            "crc_fail": 0,
            "pending_pairs": 0,
            "altitude_mismatch": 0,
            "position_rejected": 0,
            "bootstrap_held": 0,
            "bootstrap_reset": 0,
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
        if timestamp is not None:
            self._evict_expired(timestamp)
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
            # Derive the BDS 6,0 scoring fields (ias, mach) and the
            # BDS 5,0 tas slot from cached groundspeed + altitude
            # when the caller hasn't supplied observed values. Most
            # airborne-velocity frames (BDS 0,9 subtype 1/2) give us
            # gs but never populate ias/mach/tas directly, which
            # used to leave BDS 6,0 scoring without any matching
            # reference field. TAS=GS under the zero-wind
            # assumption in `_aero`.
            gs = known.get("groundspeed")
            alt = known.get("altitude")
            if gs is not None and alt is not None:
                if "ias" not in known:
                    known["ias"] = gs_to_ias(gs, alt)
                if "mach" not in known:
                    known["mach"] = gs_to_mach(gs, alt)
                if "tas" not in known:
                    known["tas"] = gs
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

        # Altitude cross-check: DF20 carries a 13-bit AC-code altitude in
        # its header. It should agree with the most recent CRC-validated
        # ADS-B position altitude for the same ICAO. A large disagreement
        # is a strong signal that the message's derived ICAO is a
        # CRC-collision artifact from a different aircraft entirely —
        # scrub the (meaningless) BDS payload we inferred from its bits.
        if (
            message.df == 20
            and timestamp is not None
            and self._reject_on_altitude_mismatch(result, icao, timestamp)
        ):
            # State would be poisoned if updated from this message.
            return result

        # ADS-B position altitude becomes the per-ICAO anchor for the
        # next round of DF20 cross-checks. Only plain-text-ICAO frames
        # with verified CRC qualify.
        if (
            message.df in (17, 18)
            and result.get("crc_valid") is True
            and result.get("bds") == "0,5"
            and result.get("altitude") is not None
            and timestamp is not None
        ):
            self._adsb_altitude[icao] = (timestamp, float(result["altitude"]))

        self._handle_cpr_pair(result, icao, timestamp)
        self._update_state(icao, result, timestamp)
        return result

    def _reject_on_altitude_mismatch(
        self,
        result: Decoded,
        icao: str,
        timestamp: float,
    ) -> bool:
        """Flag & scrub this DF20 result if its AC-code altitude disagrees
        with the recent ADS-B-anchored altitude for the same ICAO.

        Returns True if the message was rejected (caller should skip
        state updates). No-ops if we have no ADS-B anchor yet or the
        message has no altitude field.
        """
        cb_alt = result.get("altitude")
        if cb_alt is None:
            return False
        anchor = self._adsb_altitude.get(icao)
        if anchor is None:
            return False
        adsb_t, adsb_alt = anchor
        dt = abs(timestamp - adsb_t)
        if dt > self._eviction_ttl:
            return False  # anchor too stale to trust
        if abs(cb_alt - adsb_alt) <= _altitude_tolerance(dt):
            return False

        result["altitude_mismatch"] = True
        for key in _BDS_FIELDS_TO_CLEAR:
            if key in result:
                result[key] = None
        self._stats["altitude_mismatch"] += 1
        return True

    def _evict_expired(self, now: float) -> None:
        """Drop state and pending CPR entries older than eviction_ttl.

        Runs lazily at the start of each decode() call when a timestamp
        is provided. The trusted ICAO set is intentionally NOT evicted —
        once a plain-text DF17/18 has been seen for an ICAO, it remains
        trusted for the lifetime of the PipeDecoder (until reset()).
        """
        cutoff = now - self._eviction_ttl

        # Evict pending CPR frames (and decrement the stat)
        for pending in (self._pending_even, self._pending_odd):
            stale = [icao for icao, (t, _, _) in pending.items() if t < cutoff]
            for icao in stale:
                pending.pop(icao, None)
                self._stats["pending_pairs"] = max(0, self._stats["pending_pairs"] - 1)

        # Evict per-ICAO state. Only entries with a _last_seen timestamp
        # are evictable; entries without (decoded with timestamp=None)
        # never expire — but in practice they always have _last_seen
        # because state is only written from a decode call.
        stale_icaos = [
            icao
            for icao, st in self._state.items()
            if st.get("_last_seen", float("inf")) < cutoff
        ]
        for icao in stale_icaos:
            self._state.pop(icao, None)

        # Evict stale ADS-B altitude anchors.
        stale_anchors = [
            icao for icao, (t, _) in self._adsb_altitude.items() if t < cutoff
        ]
        for icao in stale_anchors:
            self._adsb_altitude.pop(icao, None)

        # Prune position-history entries older than cutoff; drop the
        # ICAO key entirely once its buffer is empty.
        for icao in list(self._position_history):
            history = self._position_history[icao]
            fresh = [entry for entry in history if entry[2] >= cutoff]
            if fresh:
                self._position_history[icao] = fresh
            else:
                del self._position_history[icao]

        # Same treatment for bootstrap buffers that haven't locked yet.
        for icao in list(self._bootstrap):
            buf = self._bootstrap[icao]
            fresh_buf = [entry for entry in buf if entry[2] >= cutoff]
            if fresh_buf:
                self._bootstrap[icao] = fresh_buf
            else:
                del self._bootstrap[icao]

    def _motion_consistent(
        self,
        icao: str,
        lat: float,
        lon: float,
        timestamp: float,
    ) -> bool:
        """True iff (lat, lon, timestamp) is reachable from at least one
        position in the per-ICAO history.

        Assumes the ICAO has already passed bootstrap (i.e. is present in
        ``_position_history``). Callers should route pre-lock candidates
        through ``_bootstrap_accumulate`` instead.
        """
        history = self._position_history.get(icao)
        if not history:
            return True
        for plat, plon, pt in history:
            dt = abs(timestamp - pt)
            max_dist = self._max_speed_kmps * dt + self._motion_margin_km
            if _haversine_km(lat, lon, plat, plon) <= max_dist:
                return True
        return False

    def _update_position_history(
        self,
        icao: str,
        lat: float,
        lon: float,
        timestamp: float,
    ) -> None:
        """Append to the per-ICAO ring buffer; drop oldest when full.

        Called for every resolved CPR pair regardless of whether
        `_motion_consistent` accepted it — rejected positions still
        enter the buffer so future real positions can find corroborating
        neighbours even after a streak of phantoms.
        """
        history = self._position_history.setdefault(icao, [])
        history.append((lat, lon, timestamp))
        if len(history) > _POSITION_HISTORY_SIZE:
            history.pop(0)

    def _pair_consistent(
        self,
        p1: tuple[float, float, float],
        p2: tuple[float, float, float],
    ) -> bool:
        """Are two candidate positions reachable from each other at
        plausible aircraft speeds?"""
        dt = abs(p1[2] - p2[2])
        max_dist = self._max_speed_kmps * dt + self._motion_margin_km
        return _haversine_km(p1[0], p1[1], p2[0], p2[1]) <= max_dist

    def _bootstrap_try_lock(self, icao: str, *, min_candidates: int) -> bool:
        """Run cluster analysis over the bootstrap buffer: pick the
        candidate with the most motion-consistent neighbours, promote
        it plus those neighbours into ``_position_history``, retro-fill
        ``latitude``/``longitude`` on the held result dicts, and clear
        the bootstrap buffer for this ICAO.

        ``min_candidates`` gates the attempt; callers use
        ``_BOOTSTRAP_K`` for the standard on-arrival lock and 2 when
        flushing an incomplete buffer at end of input.

        Returns True on successful lock; False when no candidate has a
        consistent neighbour (implies the buffer is all scattered
        phantoms — caller decides whether to reset or accept).
        """
        candidates = self._bootstrap.get(icao)
        if candidates is None or len(candidates) < min_candidates:
            return False

        points: list[tuple[float, float, float]] = [
            (lat, lon, t) for lat, lon, t, _ in candidates
        ]

        best_idx = -1
        best_neighbors: list[int] = []
        for i, pi in enumerate(points):
            neighbors = [
                j
                for j, pj in enumerate(points)
                if i != j and self._pair_consistent(pi, pj)
            ]
            if len(neighbors) > len(best_neighbors):
                best_idx = i
                best_neighbors = neighbors

        if best_idx < 0 or not best_neighbors:
            return False  # no corroboration

        cluster_indices = sorted(
            {best_idx, *best_neighbors}, key=lambda i: candidates[i][2]
        )
        cluster: list[tuple[float, float, float]] = []
        for i in cluster_indices:
            lat, lon, t, result_dict = candidates[i]
            # Retroactively emit the resolved position on the held
            # result dict so callers who kept it (e.g. batch-mode
            # consumers via ``pms.decode(list)``) now see a valid
            # lat/lon.
            result_dict["latitude"] = lat
            result_dict["longitude"] = lon
            cluster.append((lat, lon, t))
        # Seed the history with the (up to _POSITION_HISTORY_SIZE) most
        # recent members of the cluster.
        self._position_history[icao] = cluster[-_POSITION_HISTORY_SIZE:]
        self._bootstrap.pop(icao, None)
        return True

    def _bootstrap_accumulate(
        self,
        result: Decoded,
        icao: str,
        lat: float,
        lon: float,
        timestamp: float,
    ) -> None:
        """Hold a pre-lock candidate position. Clears lat/lon from the
        result (we don't emit unverified positions) and — when the buffer
        reaches _BOOTSTRAP_K — triggers cluster analysis.
        """
        buf = self._bootstrap.setdefault(icao, [])
        buf.append((lat, lon, timestamp, result))
        # Don't emit lat/lon while the anchor is still being chosen;
        # the CPR raw fields remain on the result so callers can see
        # that a pair was seen.
        result["latitude"] = None
        result["longitude"] = None
        self._stats["bootstrap_held"] += 1

        if len(buf) >= _BOOTSTRAP_K and not self._bootstrap_try_lock(
            icao, min_candidates=_BOOTSTRAP_K
        ):
            # No consistent cluster among the K candidates — they're
            # all scattered. Drop them and accumulate a fresh K.
            self._bootstrap[icao] = []
            self._stats["bootstrap_reset"] += 1

    def flush(self) -> None:
        """Finalize any still-bootstrapping ICAOs, retro-filling lat/lon
        on held result dicts wherever possible.

        * ≥ 2 candidates → cluster analysis (same as the on-arrival
          lock, but accepts any best-neighbour count ≥ 1 rather than
          waiting for _BOOTSTRAP_K).
        * exactly 1 candidate → accept as-is; with a single observation
          there's nothing to corroborate against.

        Designed for batch callers who have finished feeding the
        stream and want positions released even if the stream ended
        before cluster analysis could run.
        """
        for icao in list(self._bootstrap):
            buf = self._bootstrap[icao]
            if len(buf) == 1:
                lat, lon, t, result_dict = buf[0]
                result_dict["latitude"] = lat
                result_dict["longitude"] = lon
                self._position_history[icao] = [(lat, lon, t)]
                self._bootstrap.pop(icao, None)
            else:
                self._bootstrap_try_lock(icao, min_candidates=2)

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
                # Position-filter dispatch: bootstrapping ICAOs have
                # their candidates held in `_bootstrap` until a cluster
                # analysis picks a good anchor; locked ICAOs fall
                # through to the motion-consistency check.
                lat = result.get("latitude")
                lon = result.get("longitude")
                if lat is not None and lon is not None:
                    if icao in self._position_history:
                        if not self._motion_consistent(icao, lat, lon, timestamp):
                            result["latitude"] = None
                            result["longitude"] = None
                            self._stats["position_rejected"] += 1
                        self._update_position_history(icao, lat, lon, timestamp)
                    else:
                        self._bootstrap_accumulate(result, icao, lat, lon, timestamp)
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
        from pyModeS.position import (
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
        self._adsb_altitude.clear()
        self._position_history.clear()
        self._bootstrap.clear()
        for k in self._stats:
            self._stats[k] = 0
