"""Plausibility filters used by :class:`pyModeS.PipeDecoder`.

Keeping the rejection policies together makes their safety envelopes and field
scrubbing rules reviewable without interleaving them with cache eviction and
CPR pairing.
"""

from __future__ import annotations

from pyModeS.message import Decoded

_BDS_FIELDS_TO_CLEAR: tuple[str, ...] = (
    "bds",
    "bds_candidates",
    # Capability and identification registers.
    "supported_bds",
    "callsign",
    # BDS 4,0 selected vertical intention.
    "selected_altitude_mcp",
    "selected_altitude_fms",
    "baro_pressure_setting",
    "vnav_mode",
    "altitude_hold_mode",
    "approach_mode",
    "target_altitude_source",
    # Opt-in BDS 4,4 / 4,5 meteorological fields.
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
    # BDS 5,0 track and turn.
    "true_airspeed",
    "true_track",
    "roll",
    "track_rate",
    "groundspeed",
    # BDS 6,0 heading and speed.
    "magnetic_heading",
    "indicated_airspeed",
    "mach",
    "baro_vertical_rate",
    "inertial_vertical_rate",
)


def _altitude_tolerance(dt: float) -> float:
    """Return the allowed ADS-B/Comm-B altitude difference.

    The 500 ft floor covers quantisation and sample lag. Growth at 100 ft/s
    covers roughly 6000 fpm emergency descent, while the 5000 ft cap prevents
    an old anchor from accepting an arbitrary altitude.
    """
    return max(500.0, min(dt * 100.0, 5000.0))


def _groundspeed_tolerance(dt: float) -> float:
    """Return the allowed groundspeed difference.

    The 20 kt floor covers measurement noise and gusts. Five kt/s leaves room
    for aggressive acceleration; the 200 kt cap bounds stale-anchor trust.
    """
    return max(20.0, min(dt * 5.0, 200.0))


def _track_tolerance(dt: float) -> float:
    """Return the allowed circular track difference.

    Ten degrees/s covers a rate-3 turn with margin. The 20 degree floor absorbs
    short-sample noise and 180 degrees is the maximum circular distance.
    """
    return max(20.0, min(dt * 10.0, 180.0))


class ValidationMixin:
    """State requirements and rejection methods mixed into PipeDecoder."""

    _adsb_altitude: dict[str, tuple[float, float]]
    _adsb_velocity: dict[str, tuple[float, float, float]]
    _eviction_ttl: float
    _stats: dict[str, int]

    def _reject_on_altitude_mismatch(
        self, result: Decoded, icao: str, timestamp: float
    ) -> bool:
        """Reject DF20 BDS data that disagrees with recent ADS-B altitude."""
        cb_alt = result.get("altitude")
        anchor = self._adsb_altitude.get(icao)
        if cb_alt is None or anchor is None:
            return False
        adsb_t, adsb_alt = anchor
        dt = abs(timestamp - adsb_t)
        if dt > self._eviction_ttl:
            return False
        if abs(cb_alt - adsb_alt) <= _altitude_tolerance(dt):
            return False

        result["altitude_mismatch"] = True
        # Preserve the header AC-code that triggered the mismatch, but discard
        # every field inferred from the now-untrusted BDS payload.
        for key in _BDS_FIELDS_TO_CLEAR:
            if key in result:
                result[key] = None
        self._stats["altitude_mismatch"] += 1
        return True

    def _reject_df17_altitude_mismatch(
        self, result: Decoded, icao: str, timestamp: float
    ) -> bool:
        """Reject CRC-valid ADS-B CPR data with an implausible altitude jump."""
        new_alt = result.get("altitude")
        anchor = self._adsb_altitude.get(icao)
        if new_alt is None or anchor is None:
            return False
        adsb_t, adsb_alt = anchor
        dt = abs(timestamp - adsb_t)
        if dt > self._eviction_ttl:
            return False
        if abs(new_alt - adsb_alt) <= _altitude_tolerance(dt):
            return False

        result["altitude_mismatch"] = True
        # Keep the decoded altitude for diagnosis, but remove CPR so this frame
        # cannot poison pairing or local-position state.
        for key in ("cpr_lat", "cpr_lon", "cpr_format"):
            if key in result:
                result[key] = None
        self._stats["altitude_mismatch"] += 1
        return True

    def _reject_velocity_mismatch(
        self, result: Decoded, icao: str, timestamp: float
    ) -> bool:
        """Reject TC=19 velocity jumps or physically implausible vertical rate."""
        vr = result.get("vertical_rate")
        vr_implausible = vr is not None and abs(vr) > 10000.0

        anchor_mismatch = False
        gs = result.get("groundspeed")
        track = result.get("track")
        if gs is not None and track is not None:
            anchor = self._adsb_velocity.get(icao)
            if anchor is not None:
                anchor_t, anchor_gs, anchor_track = anchor
                dt = abs(timestamp - anchor_t)
                if dt <= self._eviction_ttl:
                    d_track = abs(track - anchor_track) % 360.0
                    d_track = min(d_track, 360.0 - d_track)
                    anchor_mismatch = abs(gs - anchor_gs) > _groundspeed_tolerance(
                        dt
                    ) or d_track > _track_tolerance(dt)

        if not (vr_implausible or anchor_mismatch):
            return False

        result["velocity_mismatch"] = True
        # These fields share the suspect TC=19 payload and must not enter state.
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
        self, result: Decoded, icao: str, timestamp: float
    ) -> bool:
        """Reject Comm-B BDS 5,0 speed or track inconsistent with ADS-B."""
        gs = result.get("groundspeed")
        track = result.get("true_track")
        if gs is None and track is None:
            return False
        anchor = self._adsb_velocity.get(icao)
        if anchor is None:
            return False
        anchor_t, anchor_gs, anchor_track = anchor
        dt = abs(timestamp - anchor_t)
        if dt > self._eviction_ttl:
            return False

        gs_ok = gs is None or abs(gs - anchor_gs) <= _groundspeed_tolerance(dt)
        d_track = 0.0 if track is None else abs(track - anchor_track) % 360.0
        d_track = min(d_track, 360.0 - d_track)
        track_ok = track is None or d_track <= _track_tolerance(dt)
        if gs_ok and track_ok:
            return False

        result["velocity_mismatch"] = True
        # A parity collision makes the entire inferred BDS payload suspect.
        for key in _BDS_FIELDS_TO_CLEAR:
            if key in result:
                result[key] = None
        self._stats["velocity_mismatch"] += 1
        return True

    def _reject_bds60_heading_mismatch(
        self, result: Decoded, icao: str, timestamp: float
    ) -> bool:
        """Reject Comm-B BDS 6,0 heading inconsistent with ADS-B track."""
        heading = result.get("magnetic_heading")
        anchor = self._adsb_velocity.get(icao)
        if heading is None or anchor is None:
            return False
        anchor_t, _anchor_gs, anchor_track = anchor
        dt = abs(timestamp - anchor_t)
        if dt > self._eviction_ttl:
            return False

        distance = abs(heading - anchor_track) % 360.0
        distance = min(distance, 360.0 - distance)
        tolerance = max(60.0, min(dt * 10.0, 180.0))
        if distance <= tolerance:
            return False

        result["velocity_mismatch"] = True
        # A parity collision makes the entire inferred BDS payload suspect.
        for key in _BDS_FIELDS_TO_CLEAR:
            if key in result:
                result[key] = None
        self._stats["velocity_mismatch"] += 1
        return True
