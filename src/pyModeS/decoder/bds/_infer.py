"""BDS inference dispatch for ADS-B ES (DF17/18) and Comm-B (DF20/21).

ADS-B ES path (DF 17/18)
    ES ME payloads carry an explicit Type Code (TC) in the top 5 bits.
    ``infer()`` extracts TC and maps it to the ICAO-standard BDS-like
    code via ``_infer_es()``. This path ignores ``include_meteo`` and
    ``known`` (the TC is deterministic; no heuristic is needed).

Phase 1 -- format-ID fast path (Comm-B only)
    The top 8 bits of the payload (bits 0-7) contain an explicit
    BDS identifier for registers 1,0 / 2,0 / 3,0. We check these
    first: the validator is still run so reserved-bit and field-range
    checks apply, but the fast path terminates after the first format
    match (a valid BDS1,0 message will never also match BDS2,0).

    BDS 1,7 also belongs conceptually to the fast path, but its
    payload has no fixed prefix byte -- bits 0-23 are a capability
    map. Its entry uses ``None`` as the expected prefix and runs its
    validator directly.

Phase 2 -- heuristic slow path (Comm-B only)
    Registers 4,0 / 5,0 / 6,0 have no format identifier and must be
    detected by status-bit and range heuristics. Each heuristic
    validator is run unconditionally and every match is added to the
    candidate list.

    BDS 4,4 and 4,5 (meteorological) are heuristic slow-path registers
    too, but they share bit patterns with non-meteorological traffic
    and produce false positives unless the caller opts in via
    ``include_meteo=True``.

Phase 3 -- reference-assisted disambiguation (Comm-B only)
    When multiple heuristic candidates (5,0 / 6,0) survive Phase 2
    and the caller passes ``known=`` aircraft state (groundspeed,
    track, heading, IAS, mach), each candidate is decoded and
    scored against the reference; the best match is moved to the
    front of the heuristic block. Format-ID candidates in front
    and meteo candidates at the back keep their positions. When
    the scorer can't disambiguate (e.g. no cached state at all),
    ``infer()`` returns the raw candidate list and the CommB class
    exposes it as ``bds_candidates`` so callers can choose.
"""

from collections.abc import Callable
from typing import Any

from pyModeS.decoder.bds import (
    bds10,
    bds17,
    bds20,
    bds30,
    bds40,
    bds44,
    bds45,
    bds50,
    bds60,
)

# Format-ID registers. Each entry is (bds_code, expected_id_byte, validator).
# BDS17 has no fixed prefix byte (its payload bits 0-23 are a capability map),
# so its entry uses None and falls through to the validator directly.
_FORMAT_ID: list[tuple[str, int | None, Callable[[int], bool]]] = [
    ("1,0", 0x10, bds10.is_bds10),
    ("1,7", None, bds17.is_bds17),
    ("2,0", 0x20, bds20.is_bds20),
    ("3,0", 0x30, bds30.is_bds30),
]

# Heuristic (non-format-ID) validators tried in order during Phase 2.
_HEURISTIC: list[tuple[str, Callable[[int], bool]]] = [
    ("4,0", bds40.is_bds40),
    ("5,0", bds50.is_bds50),
    ("6,0", bds60.is_bds60),
]

# Meteorological heuristics (opt-in via include_meteo=True).
_HEURISTIC_METEO: list[tuple[str, Callable[[int], bool]]] = [
    ("4,4", bds44.is_bds44),
    ("4,5", bds45.is_bds45),
]

# Field-by-field scoring config for Phase 3 disambiguation.
# Each tuple: (decoded_key, known_key, scale). Lower normalized
# distance = better match against the caller-supplied aircraft state.
_SCORE_FIELDS_BDS50: list[tuple[str, str, float]] = [
    ("groundspeed", "groundspeed", 50.0),
    ("true_track", "track", 30.0),
    ("true_airspeed", "tas", 50.0),
]
_SCORE_FIELDS_BDS60: list[tuple[str, str, float]] = [
    ("magnetic_heading", "heading", 30.0),
    ("indicated_airspeed", "ias", 50.0),
    ("mach", "mach", 0.1),
]


def _score_candidate(bds_code: str, payload: int, known: dict[str, Any]) -> float:
    """Score how well a candidate matches the known aircraft state.

    Lower score = better match. Returns inf if no fields could be
    compared (i.e., `known` doesn't carry any of the fields this BDS
    register would emit).
    """
    if bds_code == "5,0":
        decoded = bds50.decode_bds50(payload)
        fields = _SCORE_FIELDS_BDS50
    elif bds_code == "6,0":
        decoded = bds60.decode_bds60(payload)
        fields = _SCORE_FIELDS_BDS60
    else:
        return float("inf")

    score = 0.0
    matched = 0
    for decoded_key, known_key, scale in fields:
        d_val = decoded.get(decoded_key)
        k_val = known.get(known_key)
        if d_val is None or k_val is None:
            continue
        score += abs(float(d_val) - float(k_val)) / scale
        matched += 1

    return score if matched > 0 else float("inf")


# Validators keyed by BDS code, used by `matches()` for third-party
# callers that only want a single-register check. The primary
# dispatch path goes through `infer()` below, not this table.
_VALIDATORS: dict[str, Callable[[int], bool]] = {
    code: fn for code, _id, fn in _FORMAT_ID
}
_VALIDATORS.update(dict(_HEURISTIC))
_VALIDATORS.update(dict(_HEURISTIC_METEO))


def matches(bds_code: str, payload: int) -> bool:
    """Return True if the registered validator for `bds_code` accepts `payload`."""
    validator = _VALIDATORS.get(bds_code)
    if validator is None:
        return False
    return validator(payload)


def _infer_es(payload: int) -> list[str]:
    """Classify an ADS-B ES (DF 17/18) payload by Type Code.

    TC is the top 5 bits of the 56-bit ME field: ``(payload >> 51) & 0x1F``.

    Returns:
        A single-element list with the ICAO-standard BDS-like code, or
        an empty list for reserved / unused Type Codes (0, 23-27, 30).
    """
    tc = (payload >> 51) & 0x1F
    if 1 <= tc <= 4:
        return ["0,8"]
    if 5 <= tc <= 8:
        return ["0,6"]
    if 9 <= tc <= 18 or 20 <= tc <= 22:
        return ["0,5"]
    if tc == 19:
        return ["0,9"]
    if tc == 28:
        return ["6,1"]
    if tc == 29:
        return ["6,2"]
    if tc == 31:
        return ["6,5"]
    return []


def infer(
    payload: int,
    df: int,
    *,
    include_meteo: bool = False,
    known: dict[str, Any] | None = None,
) -> list[str]:
    """Return plausible BDS codes for a payload, routing on DF.

    **ADS-B ES path (DF 17 or 18)**
        The Type Code in the top 5 bits of the 56-bit ME field
        unambiguously identifies the message type. ``include_meteo``
        and ``known`` are ignored on this path -- the TC is
        deterministic and no heuristic scoring is needed.

    **Comm-B path (DF 20 or 21)**
        Three-phase scan:

        Phase 1 -- format-ID fast path.
            The first element (when non-empty) is the best candidate --
            either the format-ID'd register (Phase 1) or the first
            heuristic match (Phase 2). Any additional heuristic matches
            follow.

        Phase 2 -- heuristic slow path.
            BDS 4,0 / 5,0 / 6,0 validators run unconditionally.
            BDS 4,4 / 4,5 are tried only when ``include_meteo=True``.

        Phase 3 -- known-state disambiguation.
            When multiple heuristic candidates (BDS 5,0 / 6,0) survive
            Phase 2, each is scored against the known aircraft state and
            the best match is moved to the front.

    Args:
        payload: The 56-bit payload (ME field for ES, MB field for
            Comm-B) as a Python int.
        df: Downlink Format. Must be 17, 18 (ADS-B ES) or 20, 21
            (Comm-B). Any other value raises ``ValueError``.
        include_meteo: Comm-B only. When True, also try BDS 4,4 and
            4,5 heuristic validators. Ignored for DF 17/18.
        known: Comm-B only. Optional aircraft state for Phase 3
            disambiguation of BDS 5,0 / 6,0. Ignored for DF 17/18.

    Returns:
        A list of BDS code strings (e.g. ``"1,0"``, ``"5,0"``,
        ``"0,5"``). Empty list if nothing plausible matched or
        ``payload == 0``.

    Raises:
        ValueError: If ``df`` is not 17, 18, 20, or 21.
    """
    if df == 17 or df == 18:
        return _infer_es(payload)

    if df != 20 and df != 21:
        raise ValueError(
            "infer() only supports DF 17/18 (ADS-B) or DF 20/21 (Comm-B),"
            f" got df={df}"
        )

    if payload == 0:
        return []

    candidates: list[str] = []

    # Phase 1 -- format-ID fast path.
    id_byte = (payload >> 48) & 0xFF
    for code, expected, validator in _FORMAT_ID:
        if expected is None:
            # BDS17 has no fixed prefix byte; run its validator directly.
            if validator(payload):
                candidates.append(code)
                break
        elif id_byte == expected and validator(payload):
            candidates.append(code)
            # Format IDs are exclusive: a valid BDS1,0 can never also
            # be a valid BDS2,0. Stop the fast path as soon as one hits.
            break

    # Phase 2 -- heuristic slow path.
    for code, validator in _HEURISTIC:
        if validator(payload):
            candidates.append(code)

    if include_meteo:
        for code, validator in _HEURISTIC_METEO:
            if validator(payload):
                candidates.append(code)

    # Phase 3 -- known-state disambiguation.
    # When multiple candidates survive AND the caller gave us a
    # reference state, re-rank only the 5,0 / 6,0 heuristic block.
    # Format-ID candidates (1,0 / 1,7 / 2,0 / 3,0) are mutually
    # exclusive and keep their leading position. Meteo candidates
    # (4,4 / 4,5) aren't scored and stay at the back in their
    # original order.
    if known and len(candidates) > 1:
        heuristic_candidates = [c for c in candidates if c in ("5,0", "6,0")]
        if len(heuristic_candidates) > 1:
            scored = sorted(
                heuristic_candidates,
                key=lambda c: _score_candidate(c, payload, known),
            )
            first_heuristic_idx = next(
                i for i, c in enumerate(candidates) if c in ("5,0", "6,0")
            )
            pre = candidates[:first_heuristic_idx]
            tail = [
                c
                for c in candidates[first_heuristic_idx:]
                if c not in ("5,0", "6,0")
            ]
            candidates = pre + scored + tail

    return candidates
