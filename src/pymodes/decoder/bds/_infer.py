"""Two-phase BDS inference dispatch for Comm-B (DF20/21).

Phase 1 (format-ID fast path) checks the top 4 bits of the MB field
for the fixed BDS identifier of 1,0 / 1,7 / 2,0 / 3,0. Phase 2
(heuristic slow path) runs range-and-status-bit validators for
4,0 / 5,0 / 6,0 (and 4,4 / 4,5 when `include_meteo=True`).

This module starts as a near-empty stub in Task 1 and grows as each
BDS register lands. Task 11 replaces the walking-skeleton dispatch
inside CommB.decode() with a single call to `infer()` defined here.
"""

from collections.abc import Callable

# BDS code -> validator. Populated by each BDS task as it lands, in the
# same order validators are tried during inference.
_VALIDATORS: dict[str, Callable[[int], bool]] = {}


def matches(bds_code: str, mb: int) -> bool:
    """Return True if the registered validator for `bds_code` accepts `mb`.

    Returns False if `bds_code` has no registered validator (used during
    the walking-skeleton phase before Task 11).
    """
    validator = _VALIDATORS.get(bds_code)
    if validator is None:
        return False
    return validator(mb)
