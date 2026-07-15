"""PipeDecoder — stateful streaming Mode-S decoder.

Processes messages one at a time, maintaining per-ICAO state across
calls so that:

- Comm-B BDS 5,0/6,0 disambiguation can use prior groundspeed/track/
  heading observations.
- DF20/21 ICAO verification can match against ICAOs learned from
  prior DF11/DF17/DF18 messages.
- Even/odd CPR frame pairs can be matched within a configurable
  time window to resolve absolute lat/lon without a reference.
- Once a validated CPR track exists, individual airborne-position
  frames are resolved locally against the last accepted position.

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

from itertools import combinations
from math import asin, cos, radians, sin, sqrt
from typing import Any

from pyModeS._aero import gs_to_ias, gs_to_mach
from pyModeS.errors import InvalidHexError, InvalidLengthError
from pyModeS.message import Decoded, Message

# Position-history size used by the motion-consistency check.
#
# Rejected global candidates still enter this history. That is deliberate: if
# a track was initially anchored to phantom positions, the first real position
# provides a new candidate and later real positions can corroborate it. Five
# entries let a short phantom burst rotate out without retaining stale motion
# indefinitely.
_POSITION_HISTORY_SIZE = 5

# Bootstrap safety and latency trade-off.
#
# Three pairwise-consistent CPR positions are enough to establish the initial
# track. Until then, resolved coordinates are held rather than emitted. The
# buffer allows five candidates so two unrelated phantoms can be ignored; if no
# three-member subset agrees by then, the buffer is reset.
_BOOTSTRAP_MIN_CLUSTER_SIZE = 3
_BOOTSTRAP_MAX_CANDIDATES = 5

_Position = tuple[float, float, float]
_BootstrapCandidate = tuple[float, float, float, list[Decoded]]


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

# Only these downlink formats can currently emit fields consumed by
# stateful Comm-B inference. Keeping the set explicit lets the hot path
# skip nine result-dict lookups for DF5/DF11 and unsupported DFs while
# still refreshing useful state that already exists for the ICAO.
_STATEFUL_DFS = frozenset((0, 4, 16, 17, 18, 20, 21))

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


def _groundspeed_tolerance(dt: float) -> float:
    """Max plausible |gs_now - gs_anchor| in kt after dt seconds.

    5 kt/s covers aggressive jet accel/decel plus ~30 kt wind gusts,
    floored at 20 kt (sample-to-sample noise + 1-kt LSB), capped at
    200 kt so a stale anchor can't rubber-stamp arbitrary jumps.
    """
    return max(20.0, min(dt * 5.0, 200.0))


def _track_tolerance(dt: float) -> float:
    """Max plausible circular |track_now - track_anchor| in degrees.

    10°/s covers a rate-3 (9°/s) commercial turn with margin, floored
    at 20° for sample noise, effectively unconstrained past ~16 s
    (capped at 180° — the maximum circular distance).
    """
    return max(20.0, min(dt * 10.0, 180.0))


class PipeDecoder:
    """Stateful Mode-S decoder with per-ICAO state and CPR pair matching.

    Args:
        surface_ref: Optional surface-position CPR reference (ICAO airport
            code or (lat, lon) tuple). Used only for BDS 0,6 surface messages.
            See pyModeS.decode for details.
        full_dict: When True, every decoded result is populated with
            every key from _FULL_SCHEMA.
        pair_window: Maximum age difference (seconds) between an even
            and odd CPR frame for them to count as a pair. Default 10s.
        local_ref_window: Maximum age (seconds) of the last accepted
            position used for locally-unambiguous airborne CPR decoding.
            Set to 0 to disable local decoding. Default 30s.
        eviction_ttl: Per-ICAO state and pending CPR frames older than
            this many seconds are ignored immediately for the aircraft
            being decoded and dropped globally by a periodic sweep.
            Default 300s (5 minutes).
        eviction_interval: Minimum timestamp gap between full cache
            eviction sweeps. The effective interval is capped at
            ``eviction_ttl``. Default 1s; set to 0 to sweep on every
            timestamped decode call.
    """

    __slots__ = (
        "_adsb_altitude",
        "_adsb_velocity",
        "_airborne_position_reference",
        "_bootstrap",
        "_eviction_interval",
        "_eviction_ttl",
        "_full_dict",
        "_local_ref_window",
        "_max_speed_kmps",
        "_motion_margin_km",
        "_next_eviction_at",
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
        local_ref_window: float = 30.0,
        eviction_ttl: float = 300.0,
        eviction_interval: float = 1.0,
        max_speed_kt: float = 1500.0,
        motion_margin_km: float = 2.0,
    ) -> None:
        self._surface_ref = surface_ref
        self._full_dict = full_dict
        self._pair_window = pair_window
        if local_ref_window < 0:
            raise ValueError("local_ref_window must be >= 0")
        self._local_ref_window = local_ref_window
        if eviction_ttl < 0:
            raise ValueError("eviction_ttl must be >= 0")
        if eviction_interval < 0:
            raise ValueError("eviction_interval must be >= 0")
        self._eviction_ttl = eviction_ttl

        # Eviction scheduling:
        # Never delay a sweep by longer than the TTL. This preserves useful
        # sub-second TTL settings without an O(cache) walk on every message in
        # normal high-rate streams.
        self._eviction_interval = min(eviction_interval, eviction_ttl)
        self._next_eviction_at = float("-inf")

        # Position motion envelope:
        # 1500 kt is roughly twice typical airliner cruise speed. It leaves
        # room for fast business jets and wind while rejecting a phantom
        # position hundreds of kilometres from the established track.
        self._max_speed_kmps = max_speed_kt * 1.852 / 3600.0
        self._motion_margin_km = motion_margin_km
        self._state: dict[str, dict[str, Any]] = {}

        # Pending CPR frames:
        # Each ICAO maps to a timestamp-ordered list of
        # (timestamp, cpr_lat, cpr_lon, result_dict). A list per parity keeps
        # earlier same-parity frames when several arrive before the opposite
        # parity; the next opposite frame can resolve each fresh entry.
        self._pending_even: dict[str, list[tuple[float, int, int, Decoded]]] = {}
        self._pending_odd: dict[str, list[tuple[float, int, int, Decoded]]] = {}
        self._trusted_icaos: set[str] = set()

        # ADS-B-derived altitude anchor per ICAO, used to reject DF20
        # messages whose AC-code altitude is inconsistent with the
        # aircraft's known position altitude (a signature of a
        # CRC-collision attributing the reply to the wrong ICAO).
        # Populated only from CRC-valid DF17/18 airborne positions
        # (BDS 0,5); value is (timestamp, altitude_ft).
        self._adsb_altitude: dict[str, tuple[float, float]] = {}

        # ADS-B-derived velocity anchor per ICAO, used to reject DF17/18
        # TC=19 airborne-velocity messages whose decoded groundspeed or
        # track jumps implausibly from the last CRC-valid sample (a
        # signature of a bit-corruption phantom that happened to pass
        # CRC with the ICAO field intact). Value is
        # (timestamp, groundspeed_kt, track_deg) and only updated on
        # messages that *pass* the cross-check.
        self._adsb_velocity: dict[str, tuple[float, float, float]] = {}

        # Rolling window of the last _POSITION_HISTORY_SIZE resolved
        # (lat, lon, timestamp) tuples per ICAO. Only populated AFTER
        # the per-ICAO bootstrap cluster analysis has locked in an
        # initial anchor — until then an ICAO's candidates live in
        # `_bootstrap` instead.
        self._position_history: dict[str, list[_Position]] = {}

        # Last accepted airborne position per ICAO. Unlike
        # `_position_history`, this never contains rejected global candidates
        # or positions derived from the optional ground-position reference,
        # so it is safe for locally-unambiguous airborne CPR decoding.
        # Value is (latitude, longitude, timestamp).
        self._airborne_position_reference: dict[str, _Position] = {}

        # Pre-lock bootstrap candidates per ICAO. An ICAO appears in
        # `_bootstrap` XOR `_position_history`: it moves from bootstrap
        # to history when a pairwise-consistent cluster is detected within
        # _BOOTSTRAP_MAX_CANDIDATES resolved positions. Each candidate retains
        # every associated result dictionary so batch callers see both CPR
        # halves, including any same-parity backlog, updated on promotion.
        self._bootstrap: dict[str, list[_BootstrapCandidate]] = {}
        self._stats: dict[str, int] = {
            "total": 0,
            "decoded": 0,
            "crc_fail": 0,
            "pending_pairs": 0,
            "altitude_mismatch": 0,
            "velocity_mismatch": 0,
            "position_rejected": 0,
            "local_positions": 0,
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
            self._maybe_evict_expired(timestamp)
        self._stats["total"] += 1

        try:
            message = Message(msg)
        except (InvalidHexError, InvalidLengthError) as e:
            return Decoded({"error": str(e), "raw_msg": msg})

        # Look up prior state for this ICAO so the decoder can use it
        # for Comm-B BDS 5,0/6,0 disambiguation. Remove the internal
        # timestamp before passing the state as `known=`.
        icao = message.icao
        if timestamp is not None:
            # Full sweeps are deliberately throttled, but stale state must
            # never influence the current aircraft's decode. This bounded
            # per-ICAO prune preserves exact TTL semantics without bringing
            # back an O(all active aircraft) operation on every message.
            prior_state = self._evict_icao_expired(icao, message.df, timestamp)
        else:
            prior_state = self._state.get(icao)
        known: dict[str, Any] | None
        if prior_state:
            # dict.copy() runs in C and is measurably cheaper in this hot
            # path than filtering the small state dict with a Python loop.
            known = prior_state.copy()
            known.pop("_last_seen", None)
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
        # DF11 is intentionally excluded: its interrogator-identifier parity
        # cannot be validated without extra context, so a corrupt all-call
        # reply must not pollute the trusted-address cache.
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

        # Altitude cross-check for CRC-valid DF17/18 airborne-position
        # (BDS 0,5) frames. A CRC-lucky FRUIT phantom can produce an
        # altitude thousands of feet off from the running anchor; reject
        # those so they don't pollute the altitude trace or pair into
        # garbage CPR positions.
        if (
            message.df in (17, 18)
            and result.get("crc_valid") is True
            and result.get("bds") == "0,5"
            and timestamp is not None
            and self._reject_df17_altitude_mismatch(result, icao, timestamp)
        ):
            return result

        # ADS-B position altitude becomes the per-ICAO anchor for the
        # next round of DF20 and DF17 cross-checks. Only plain-text-ICAO
        # frames with verified CRC qualify.
        if (
            message.df in (17, 18)
            and result.get("crc_valid") is True
            and result.get("bds") == "0,5"
            and result.get("altitude") is not None
            and timestamp is not None
            and (
                icao not in self._adsb_altitude
                or timestamp >= self._adsb_altitude[icao][0]
            )
        ):
            self._adsb_altitude[icao] = (timestamp, float(result["altitude"]))

        # Velocity cross-check: DF17/18 TC=19 subtype 1/2 carries gs +
        # track. A single frame whose values jump implausibly from the
        # most recent CRC-valid anchor is almost certainly a CRC-lucky
        # bit-corruption phantom attributed to this ICAO by mistake.
        # Rejection scrubs the velocity fields AND skips the anchor
        # update below so the phantom can't poison future checks.
        if (
            message.df in (17, 18)
            and result.get("typecode") == 19
            and result.get("crc_valid") is True
            and timestamp is not None
            and self._reject_velocity_mismatch(result, icao, timestamp)
        ):
            return result

        # ADS-B velocity becomes the per-ICAO anchor for the next
        # TC=19 cross-check — only when both gs and track are present
        # (subtype 1/2) and the message passed the check above.
        if (
            message.df in (17, 18)
            and result.get("typecode") == 19
            and result.get("crc_valid") is True
            and result.get("groundspeed") is not None
            and result.get("track") is not None
            and timestamp is not None
            and (
                icao not in self._adsb_velocity
                or timestamp >= self._adsb_velocity[icao][0]
            )
        ):
            self._adsb_velocity[icao] = (
                timestamp,
                float(result["groundspeed"]),
                float(result["track"]),
            )

        # Comm-B BDS 5,0 (track-and-turn) velocity cross-check. A DF20/21
        # reply can pass CRC (XOR'd with ICAO) while originating from a
        # different aircraft whose bits happen to land in BDS 5,0's valid
        # range. Reuse the per-ICAO ADS-B velocity anchor to reject
        # those when gs/true_track disagrees with recent TC=19.
        if (
            message.df in (20, 21)
            and result.get("bds") == "5,0"
            and timestamp is not None
            and self._reject_bds50_velocity_mismatch(result, icao, timestamp)
        ):
            return result

        # Same idea for BDS 6,0 (heading and speed): magnetic heading is
        # the cleanest discriminator (±60° covers magnetic variation and
        # wind correction). Mach and IAS are intentionally not checked —
        # they overlap too much with real variation across wind/altitude.
        if (
            message.df in (20, 21)
            and result.get("bds") == "6,0"
            and timestamp is not None
            and self._reject_bds60_heading_mismatch(result, icao, timestamp)
        ):
            return result

        global_position_resolved = self._handle_cpr_pair(result, icao, timestamp)
        if not global_position_resolved and result.get("bds") == "0,5":
            self._handle_local_cpr(result, icao, timestamp)
        self._update_state(icao, message.df, result, timestamp)
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

    def _reject_df17_altitude_mismatch(
        self,
        result: Decoded,
        icao: str,
        timestamp: float,
    ) -> bool:
        """Flag & scrub a CRC-valid DF17/18 BDS 0,5 position whose
        altitude disagrees with the recent ADS-B altitude anchor.

        A FRUIT phantom that survives CRC can land with plausible ICAO
        bits but a garbage AC-code altitude. The header altitude is
        preserved (so callers see what was flagged); the CPR fields are
        cleared so the phantom can't pair with nearby real frames and
        produce a far-off position that the motion check would catch
        only after more work.

        Returns True if rejected (caller skips anchor update and all
        downstream state mutations).
        """
        new_alt = result.get("altitude")
        if new_alt is None:
            return False
        anchor = self._adsb_altitude.get(icao)
        if anchor is None:
            return False
        adsb_t, adsb_alt = anchor
        dt = abs(timestamp - adsb_t)
        if dt > self._eviction_ttl:
            return False
        if abs(new_alt - adsb_alt) <= _altitude_tolerance(dt):
            return False

        result["altitude_mismatch"] = True
        for key in ("cpr_lat", "cpr_lon", "cpr_format"):
            if key in result:
                result[key] = None
        self._stats["altitude_mismatch"] += 1
        return True

    def _reject_velocity_mismatch(
        self,
        result: Decoded,
        icao: str,
        timestamp: float,
    ) -> bool:
        """Flag & scrub this TC=19 result if gs/track disagrees with the
        recent anchor, OR if the decoded vertical rate exceeds the
        physical envelope of a commercial aircraft (~±6000 fpm; we use
        ±10 000 fpm as an absolute cutoff).

        Returns True if rejected (caller skips state/anchor update).
        The VR check fires even without an anchor and even when gs/track
        pass, so a phantom whose gs/track match the anchor but whose VR
        is garbage (-24 704 fpm from a single corrupted frame) is still
        caught.
        """
        vr = result.get("vertical_rate")
        vr_implausible = vr is not None and abs(vr) > 10000.0

        anchor_mismatch = False
        gs = result.get("groundspeed")
        track = result.get("track")
        if gs is not None and track is not None:
            anchor = self._adsb_velocity.get(icao)
            if anchor is not None:
                a_t, a_gs, a_track = anchor
                dt = abs(timestamp - a_t)
                if dt <= self._eviction_ttl:
                    d_gs = abs(gs - a_gs)
                    d_track = abs(track - a_track) % 360.0
                    if d_track > 180.0:
                        d_track = 360.0 - d_track
                    if d_gs > _groundspeed_tolerance(dt) or d_track > _track_tolerance(
                        dt
                    ):
                        anchor_mismatch = True

        if not (vr_implausible or anchor_mismatch):
            return False

        result["velocity_mismatch"] = True
        # Scrub velocity fields — the caller would otherwise merge them
        # into state, propagating the phantom's values downstream.
        for key in (
            "groundspeed",
            "track",
            "vertical_rate",
            "heading",
            "airspeed",
            "airspeed_type",
            "velocity_type",
        ):
            if key in result:
                result[key] = None
        self._stats["velocity_mismatch"] += 1
        return True

    def _reject_bds50_velocity_mismatch(
        self,
        result: Decoded,
        icao: str,
        timestamp: float,
    ) -> bool:
        """Flag & scrub a DF20/21 BDS 5,0 reply whose gs or true_track
        disagrees with the per-ICAO ADS-B velocity anchor.

        Mirrors `_reject_velocity_mismatch` but reads `true_track`
        (BDS 5,0's heading field) instead of `track` (TC=19's).

        Returns True if rejected (caller skips handle_cpr_pair and
        _update_state so the phantom's values don't propagate).
        """
        gs = result.get("groundspeed")
        track = result.get("true_track")
        if gs is None and track is None:
            return False
        anchor = self._adsb_velocity.get(icao)
        if anchor is None:
            return False
        a_t, a_gs, a_track = anchor
        dt = abs(timestamp - a_t)
        if dt > self._eviction_ttl:
            return False

        gs_ok = True
        track_ok = True
        if gs is not None:
            gs_ok = abs(gs - a_gs) <= _groundspeed_tolerance(dt)
        if track is not None:
            d_track = abs(track - a_track) % 360.0
            if d_track > 180.0:
                d_track = 360.0 - d_track
            track_ok = d_track <= _track_tolerance(dt)

        if gs_ok and track_ok:
            return False

        result["velocity_mismatch"] = True
        # Scrub the whole BDS payload — the fields might individually
        # look valid but the frame is from a different aircraft.
        for key in _BDS_FIELDS_TO_CLEAR:
            if key in result:
                result[key] = None
        self._stats["velocity_mismatch"] += 1
        return True

    def _reject_bds60_heading_mismatch(
        self,
        result: Decoded,
        icao: str,
        timestamp: float,
    ) -> bool:
        """Flag & scrub a DF20/21 BDS 6,0 reply whose magnetic_heading
        disagrees with the per-ICAO ADS-B track anchor by more than
        magnetic variation + wind-correction angle can legitimately
        explain.

        Tolerance: ``max(60°, min(Δt · 10°, 180°))``. The 60° floor
        covers worst-case magnetic variation (±20°) + strong-crosswind
        wind-correction angle (±20°) + short lag during turns; the
        per-second slope matches the rate-3 turn envelope used elsewhere.

        Returns True if rejected.
        """
        hdg = result.get("magnetic_heading")
        if hdg is None:
            return False
        anchor = self._adsb_velocity.get(icao)
        if anchor is None:
            return False
        a_t, _a_gs, a_track = anchor
        dt = abs(timestamp - a_t)
        if dt > self._eviction_ttl:
            return False

        d = abs(hdg - a_track) % 360.0
        if d > 180.0:
            d = 360.0 - d

        tol = max(60.0, min(dt * 10.0, 180.0))
        if d <= tol:
            return False

        result["velocity_mismatch"] = True
        for key in _BDS_FIELDS_TO_CLEAR:
            if key in result:
                result[key] = None
        self._stats["velocity_mismatch"] += 1
        return True

    def _maybe_evict_expired(self, now: float) -> None:
        """Run a full eviction sweep only when its interval is due.

        A sweep touches every live per-ICAO cache, so running it for every
        message makes decode cost proportional to the number of active
        aircraft. At high message rates that dominates the actual decoder.
        Timestamp throttling bounds stale memory retention by at most
        ``eviction_interval`` while making sweep cost amortized. Exact
        per-aircraft expiry happens separately before cached state is used.
        """
        if now < self._next_eviction_at:
            return
        self._evict_expired(now)
        self._next_eviction_at = now + self._eviction_interval

    def _evict_expired(self, now: float) -> None:
        """Drop state and pending CPR entries older than eviction_ttl.

        Called periodically by :meth:`_maybe_evict_expired`. The trusted
        ICAO set is intentionally NOT evicted — once a plain-text DF17/18
        has been seen for an ICAO, it remains trusted for the lifetime of
        the PipeDecoder (until reset()).
        """
        cutoff = now - self._eviction_ttl

        # Evict pending CPR frames (and decrement the stat). Per-ICAO
        # Trim pending lists and drop ICAO keys whose lists become empty.
        for pending in (self._pending_even, self._pending_odd):
            for icao in list(pending):
                queue = pending[icao]
                fresh_queue = [entry for entry in queue if entry[0] >= cutoff]
                dropped = len(queue) - len(fresh_queue)
                if fresh_queue:
                    pending[icao] = fresh_queue
                else:
                    pending.pop(icao, None)
                self._stats["pending_pairs"] = max(
                    0, self._stats["pending_pairs"] - dropped
                )

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

        # Same for velocity anchors.
        stale_vel = [
            icao for icao, (t, _, _) in self._adsb_velocity.items() if t < cutoff
        ]
        for icao in stale_vel:
            self._adsb_velocity.pop(icao, None)

        # Locally-unambiguous CPR references follow the same lifetime as
        # the rest of the per-aircraft position state. The tighter
        # `local_ref_window` is enforced when a reference is consumed.
        stale_position_refs = [
            icao
            for icao, (_, _, t) in self._airborne_position_reference.items()
            if t < cutoff
        ]
        for icao in stale_position_refs:
            self._airborne_position_reference.pop(icao, None)

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

    def _evict_icao_expired(
        self, icao: str, downlink_format: int, now: float
    ) -> dict[str, Any] | None:
        """Drop expired caches and return usable state for one ICAO.

        Periodic full sweeps keep total memory bounded, but their interval
        must not extend the semantic lifetime of state used for Comm-B
        inference or validation. Every collection touched here has a small,
        fixed per-ICAO bound, so this remains O(1) with respect to the number
        of active aircraft.
        """
        cutoff = now - self._eviction_ttl

        state = self._state.get(icao)
        if state is not None and state.get("_last_seen", float("inf")) < cutoff:
            self._state.pop(icao, None)
            state = None

        # Short surveillance/ACAS messages cannot consume validation or
        # CPR caches. Their altitude can still refresh `_state` later, but
        # the state expiry above is the only exact-TTL work they need here.
        if downlink_format not in (17, 18, 20, 21):
            return state

        if downlink_format in (17, 18, 20):
            altitude_anchor = self._adsb_altitude.get(icao)
            if altitude_anchor is not None and altitude_anchor[0] < cutoff:
                self._adsb_altitude.pop(icao, None)

        velocity_anchor = self._adsb_velocity.get(icao)
        if velocity_anchor is not None and velocity_anchor[0] < cutoff:
            self._adsb_velocity.pop(icao, None)

        # Only ADS-B frames participate in CPR pairing, bootstrap, and
        # position-history validation.
        if downlink_format not in (17, 18):
            return state

        for pending in (self._pending_even, self._pending_odd):
            entries = pending.get(icao)
            if entries is None:
                continue
            fresh_entries = [entry for entry in entries if entry[0] >= cutoff]
            dropped = len(entries) - len(fresh_entries)
            if fresh_entries:
                pending[icao] = fresh_entries
            else:
                pending.pop(icao, None)
            self._stats["pending_pairs"] = max(
                0, self._stats["pending_pairs"] - dropped
            )

        history = self._position_history.get(icao)
        if history is not None:
            fresh_history = [entry for entry in history if entry[2] >= cutoff]
            if fresh_history:
                self._position_history[icao] = fresh_history
            else:
                self._position_history.pop(icao, None)

        position_ref = self._airborne_position_reference.get(icao)
        if position_ref is not None and position_ref[2] < cutoff:
            self._airborne_position_reference.pop(icao, None)

        bootstrap = self._bootstrap.get(icao)
        if bootstrap is not None:
            fresh_bootstrap = [entry for entry in bootstrap if entry[2] >= cutoff]
            if fresh_bootstrap:
                self._bootstrap[icao] = fresh_bootstrap
            else:
                self._bootstrap.pop(icao, None)

        return state

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
        """Insert into the per-ICAO time-ordered ring buffer.

        Called for every resolved CPR pair regardless of whether
        `_motion_consistent` accepted it — rejected positions still
        enter the buffer so future real positions can find corroborating
        neighbours even after a streak of phantoms.
        """
        history = self._position_history.setdefault(icao, [])
        history.append((lat, lon, timestamp))
        history.sort(key=lambda position: position[2])
        del history[:-_POSITION_HISTORY_SIZE]

    def _pair_consistent(
        self,
        p1: _Position,
        p2: _Position,
    ) -> bool:
        """Are two candidate positions reachable from each other at
        plausible aircraft speeds?"""
        dt = abs(p1[2] - p2[2])
        max_dist = self._max_speed_kmps * dt + self._motion_margin_km
        return _haversine_km(p1[0], p1[1], p2[0], p2[1]) <= max_dist

    def _find_bootstrap_cluster(
        self,
        points: list[_Position],
        *,
        min_cluster_size: int,
    ) -> list[int]:
        """Return the largest pairwise-consistent candidate subset.

        The bootstrap buffer contains at most five positions, so checking every
        subset is both cheap and clearer than a graph heuristic. Requiring every
        pair to agree prevents one central candidate from joining two mutually
        inconsistent neighbours into a false cluster.
        """
        for cluster_size in range(len(points), min_cluster_size - 1, -1):
            for indices in combinations(range(len(points)), cluster_size):
                if all(
                    self._pair_consistent(points[i], points[j])
                    for i, j in combinations(indices, 2)
                ):
                    return list(indices)
        return []

    def _promote_bootstrap_cluster(
        self,
        icao: str,
        candidates: list[_BootstrapCandidate],
        cluster_indices: list[int],
    ) -> None:
        """Promote a verified cluster and initialize its airborne reference."""
        cluster: list[_Position] = []
        airborne_positions: list[_Position] = []

        for i in sorted(cluster_indices, key=lambda index: candidates[index][2]):
            lat, lon, timestamp, result_dicts = candidates[i]

            # Both halves of a CPR pair are retained by batch callers. Update
            # both dictionaries when their shared position becomes trusted.
            for result in result_dicts:
                result["latitude"] = lat
                result["longitude"] = lon

            position = (lat, lon, timestamp)
            cluster.append(position)
            if any(result.get("bds") == "0,5" for result in result_dicts):
                airborne_positions.append(position)

        self._position_history[icao] = cluster[-_POSITION_HISTORY_SIZE:]

        # Surface candidates share position history with airborne candidates,
        # but they must never become a reference for airborne local CPR.
        if airborne_positions:
            self._airborne_position_reference[icao] = airborne_positions[-1]

        self._bootstrap.pop(icao, None)

    def _bootstrap_try_lock(
        self,
        icao: str,
        *,
        min_cluster_size: int,
    ) -> bool:
        """Promote the largest pairwise-consistent bootstrap cluster.

        Live decoding requires three corroborating positions. ``flush()`` uses
        a lower threshold so a finite batch can release its remaining results.

        Returns ``False`` when too few candidates exist or no subset meets the
        requested size. The caller decides whether to keep collecting or reset.
        """
        candidates = self._bootstrap.get(icao)
        if candidates is None or len(candidates) < min_cluster_size:
            return False

        points: list[_Position] = [(lat, lon, t) for lat, lon, t, _ in candidates]
        cluster_indices = self._find_bootstrap_cluster(
            points,
            min_cluster_size=min_cluster_size,
        )
        if not cluster_indices:
            return False

        self._promote_bootstrap_cluster(icao, candidates, cluster_indices)
        return True

    def _bootstrap_accumulate(
        self,
        results: Decoded | list[Decoded],
        icao: str,
        lat: float,
        lon: float,
        timestamp: float,
    ) -> None:
        """Hold a candidate until a pairwise-consistent cluster is available.

        ``results`` accepts a single dict (back-compat for tests that
        supply synthetic candidates) or a list of dicts. In the normal
        decode path the caller passes both halves of the resolved pair
        so both get retro-filled together when a cluster locks.
        """
        result_dicts = results if isinstance(results, list) else [results]
        buf = self._bootstrap.setdefault(icao, [])
        buf.append((lat, lon, timestamp, result_dicts))
        # Don't emit lat/lon while the anchor is still being chosen;
        # the CPR raw fields remain on each result so callers can see
        # that a pair was seen.
        for rd in result_dicts:
            rd["latitude"] = None
            rd["longitude"] = None
        self._stats["bootstrap_held"] += 1

        if len(buf) >= _BOOTSTRAP_MIN_CLUSTER_SIZE and self._bootstrap_try_lock(
            icao,
            min_cluster_size=_BOOTSTRAP_MIN_CLUSTER_SIZE,
        ):
            return

        if len(buf) >= _BOOTSTRAP_MAX_CANDIDATES:
            # The full buffer contains no three-member consistent subset.
            # Discard it so later real positions can establish a fresh track.
            self._bootstrap[icao] = []
            self._stats["bootstrap_reset"] += 1

    def flush(self) -> None:
        """Finalize any still-bootstrapping ICAOs, retro-filling lat/lon
        on held result dicts wherever possible.

        * ≥ 2 candidates → accept the largest pairwise-consistent subset
          containing at least two positions.
        * exactly 1 candidate → accept as-is; with a single observation
          there's nothing to corroborate against.

        Designed for batch callers who have finished feeding the
        stream and want positions released even if the stream ended
        before cluster analysis could run.
        """
        for icao in list(self._bootstrap):
            buf = self._bootstrap[icao]
            if len(buf) == 1:
                self._promote_bootstrap_cluster(icao, buf, [0])
            else:
                self._bootstrap_try_lock(icao, min_cluster_size=2)

    def _handle_cpr_pair(
        self,
        result: Decoded,
        icao: str,
        timestamp: float | None,
    ) -> bool:
        """Resolve a CPR pair if the opposite parity frame is pending.

        Stores this frame as pending if no opposite is available.
        Skips entirely without a timestamp (pair matching needs a clock).
        Returns True when a global position was resolved, including a
        candidate held by bootstrap or rejected by the motion check. This
        prevents a failed global validation from being replaced by the local
        fallback in the same call.
        """
        bds = result.get("bds")
        if bds not in ("0,5", "0,6") or "cpr_format" not in result:
            return False
        if timestamp is None:
            return False  # cannot pair without timestamps

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

        opposite_queue = other_pending.get(icao, [])
        fresh = [
            entry
            for entry in opposite_queue
            if abs(timestamp - entry[0]) <= self._pair_window
        ]

        if fresh:
            # Primary = the most-recent fresh opposite. That pair gives
            # the best estimate of the current (arriving) frame's
            # position; older fresh opposites become "orphan pairs"
            # resolved independently so each gets its own lat/lon.
            fresh.sort(key=lambda e: e[0], reverse=True)
            primary_t, primary_lat, primary_lon, primary_result = fresh[0]
            position_timestamp = max(timestamp, primary_t)

            self._resolve_pair(
                result,
                bds,
                cpr_format,
                cpr_lat,
                cpr_lon,
                timestamp,
                primary_lat,
                primary_lon,
                primary_t,
            )
            lat = result.get("latitude")
            lon = result.get("longitude")

            paired_dicts: list[Decoded] = [result, primary_result]
            if lat is not None and lon is not None:
                primary_result["latitude"] = lat
                primary_result["longitude"] = lon

            # Orphan pairs — each opposite entry older than the primary
            # pairs independently with the arriving frame's cpr values.
            for o_t, o_lat, o_lon, o_result in fresh[1:]:
                temp: Decoded = Decoded({"cpr_format": cpr_format})
                self._resolve_pair(
                    temp,
                    bds,
                    cpr_format,
                    cpr_lat,
                    cpr_lon,
                    timestamp,
                    o_lat,
                    o_lon,
                    o_t,
                )
                o_lat_out = temp.get("latitude")
                o_lon_out = temp.get("longitude")
                if o_lat_out is not None:
                    o_result["latitude"] = o_lat_out
                    o_result["longitude"] = o_lon_out
                paired_dicts.append(o_result)

            # Fresh opposites have all been consumed. Retain stale entries
            # until the next eviction sweep.
            stale = [
                entry
                for entry in opposite_queue
                if abs(timestamp - entry[0]) > self._pair_window
            ]
            if stale:
                other_pending[icao] = stale
            else:
                other_pending.pop(icao, None)
            self._stats["pending_pairs"] = max(
                0, self._stats["pending_pairs"] - len(fresh)
            )

            # Position-filter dispatch: bootstrapping ICAOs hold every
            # paired dict (primary + orphans) as a single candidate so
            # that nothing unverified reaches the caller; locked ICAOs
            # run the motion check against the primary resolution and
            # share the verdict with the orphans.
            if lat is not None and lon is not None:
                if icao in self._position_history:
                    accepted = self._motion_consistent(
                        icao, lat, lon, position_timestamp
                    )
                    if not accepted:
                        for d in paired_dicts:
                            d["latitude"] = None
                            d["longitude"] = None
                        self._stats["position_rejected"] += 1
                    self._update_position_history(icao, lat, lon, position_timestamp)
                    if (
                        accepted
                        and bds == "0,5"
                        and (
                            icao not in self._airborne_position_reference
                            or position_timestamp
                            >= self._airborne_position_reference[icao][2]
                        )
                    ):
                        self._airborne_position_reference[icao] = (
                            lat,
                            lon,
                            position_timestamp,
                        )
                else:
                    self._bootstrap_accumulate(
                        paired_dicts, icao, lat, lon, position_timestamp
                    )
                return True
            return False

        # No fresh opposite — append this frame to its own parity list,
        # keeping a reference to its result dict for later retro-fill.
        queue = this_pending.setdefault(icao, [])
        queue.append((timestamp, cpr_lat, cpr_lon, result))
        self._stats["pending_pairs"] += 1
        return False

    def _handle_local_cpr(
        self,
        result: Decoded,
        icao: str,
        timestamp: float | None,
    ) -> None:
        """Resolve one airborne CPR frame from the last accepted position.

        Global even/odd decoding remains the source of initial trust. Local
        decoding starts only after bootstrap has established an accepted
        reference, and the reference must be recent enough. The resulting
        position passes the same motion envelope as global candidates before
        it is returned or allowed to advance the reference.
        """
        if (
            timestamp is None
            or self._local_ref_window == 0
            or result.get("bds") != "0,5"
            or "cpr_format" not in result
            or result.get("latitude") is not None
        ):
            return

        reference = self._airborne_position_reference.get(icao)
        if reference is None:
            return
        lat_ref, lon_ref, ref_timestamp = reference
        age = timestamp - ref_timestamp
        if age < 0 or age > self._local_ref_window:
            return

        from pyModeS.position import airborne_position_with_ref

        lat, lon = airborne_position_with_ref(
            result["cpr_format"],
            result["cpr_lat"],
            result["cpr_lon"],
            lat_ref,
            lon_ref,
        )
        if not self._motion_consistent(icao, lat, lon, timestamp):
            result["latitude"] = None
            result["longitude"] = None
            self._stats["position_rejected"] += 1
            return

        result["latitude"] = lat
        result["longitude"] = lon
        self._update_position_history(icao, lat, lon, timestamp)
        self._airborne_position_reference[icao] = (lat, lon, timestamp)
        self._stats["local_positions"] += 1

    def _resolve_pair(
        self,
        result: Decoded,
        bds: str,
        cpr_format: int,
        cpr_lat: int,
        cpr_lon: int,
        timestamp: float,
        other_lat: int,
        other_lon: int,
        other_timestamp: float,
    ) -> None:
        """Call the appropriate pair resolver and merge lat/lon in place."""
        from pyModeS.position import (
            airborne_position_pair,
            resolve_surface_ref,
            surface_position_pair,
        )

        # Arrival order and source time can differ during capture replay or
        # network reordering. CPR needs the newer timestamped parity, not the
        # frame that happened to reach this method last.
        current_is_newer = timestamp >= other_timestamp
        if cpr_format == 0:
            elat, elon = cpr_lat, cpr_lon
            olat, olon = other_lat, other_lon
            even_is_newer = current_is_newer
        else:
            elat, elon = other_lat, other_lon
            olat, olon = cpr_lat, cpr_lon
            even_is_newer = not current_is_newer

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
        downlink_format: int,
        result: Decoded,
        timestamp: float | None,
    ) -> None:
        """Merge tracked fields from the result into per-ICAO state."""
        existing = self._state.get(icao)
        last_seen = existing.get("_last_seen") if existing is not None else None
        stale_update = (
            timestamp is not None and last_seen is not None and timestamp < last_seen
        )
        if downlink_format not in _STATEFUL_DFS:
            if existing is not None and timestamp is not None and not stale_update:
                existing["_last_seen"] = timestamp
            return

        if stale_update:
            return

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

        if not new_fields:
            # A timestamp alone is not useful state. Creating an entry here
            # used to retain every parseable message's derived ICAO — even
            # for untracked DFs and corrupt traffic — and made the periodic
            # eviction scan much larger than the active-aircraft set.
            if existing is not None and timestamp is not None:
                existing["_last_seen"] = timestamp
            return

        if existing is None:
            existing = {}
            self._state[icao] = existing
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
        self._adsb_velocity.clear()
        self._position_history.clear()
        self._airborne_position_reference.clear()
        self._bootstrap.clear()
        self._next_eviction_at = float("-inf")
        for k in self._stats:
            self._stats[k] = 0
