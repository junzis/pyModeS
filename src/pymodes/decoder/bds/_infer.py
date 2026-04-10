"""Two-phase BDS inference dispatch for Comm-B (DF20/21).

Phase 1 -- format-ID fast path
    The top 8 bits of the payload (bits 0-7) contain an explicit
    BDS identifier for registers 1,0 / 2,0 / 3,0. We check these
    first: the validator is still run so reserved-bit and field-range
    checks apply, but the fast path terminates after the first format
    match (a valid BDS1,0 message will never also match BDS2,0).

    BDS 1,7 also belongs conceptually to the fast path, but its
    payload has no fixed prefix byte -- bits 0-23 are a capability
    map. Its entry uses ``None`` as the expected prefix and runs its
    validator directly.

Phase 2 -- heuristic slow path
    Registers 4,0 / 5,0 / 6,0 have no format identifier and must be
    detected by status-bit and range heuristics. Each heuristic
    validator is run unconditionally and every match is added to the
    candidate list.

    BDS 4,4 and 4,5 (meteorological) are heuristic slow-path registers
    too, but they share bit patterns with non-meteorological traffic
    and produce false positives unless the caller opts in via
    ``include_meteo=True``.

Phase 3 -- reference-assisted disambiguation
    When multiple candidates survive Phase 2 and the caller passes
    ``known=`` aircraft state (altitude, groundspeed, track), the
    candidates can be scored against the reference and the best
    single match returned. Plan 3 defers this -- ``infer()`` returns
    the raw candidate list and the CommB class exposes it as
    ``bds_candidates`` so callers can choose.
"""

from collections.abc import Callable
from typing import Any

from pymodes.decoder.bds import (
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

# Validators keyed by BDS code, used by `matches()` for third-party
# callers that only want a single-register check. Task 11 promoted the
# primary dispatch path to `infer()` below.
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


def infer(
    payload: int,
    *,
    include_meteo: bool = False,
    known: dict[str, Any] | None = None,
) -> list[str]:
    """Return plausible BDS codes for a Comm-B payload.

    The first element (when non-empty) is the best candidate -- either
    the format-ID'd register (Phase 1) or the first heuristic match
    (Phase 2). Any additional heuristic matches follow.

    Args:
        payload: The 56-bit Comm-B payload as a Python int.
        include_meteo: When True, also try BDS 4,4 and 4,5 heuristic
            validators. Defaults to False because these share bit
            patterns with non-meteorological traffic.
        known: Optional aircraft state for reference-assisted
            disambiguation. Accepted but not used in Plan 3 -- reserved
            for a future plan.

    Returns:
        A list of BDS code strings (e.g. "1,0", "5,0"). Empty list if
        nothing plausible matched or `payload == 0`.
    """
    _ = known  # reserved for future reference disambiguation

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

    return candidates
