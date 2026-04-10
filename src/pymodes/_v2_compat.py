"""Compatibility tables bridging pyModeS 2.22.0 output to pymodes v3.

Two tables live here and serve as the single source of truth for both
the golden-file oracle test (``tests/test_golden_v2_corpus.py``) and
the migration guide (``docs/migration.md`` auto-generates its renamed-
keys table from ``V2_DEPRECATED_KEYS``).

This module is internal. Nothing in ``pymodes.__init__`` re-exports it.
It lives under ``src/pymodes`` rather than ``tests/`` so both the test
and the migration doc generator can import it cleanly.

Populated incrementally as the oracle test surfaces real mismatches.
Every entry should have a one-line comment explaining the rename or
the tolerance reason.
"""

from __future__ import annotations

# v2 key name -> v3 key name for fields intentionally renamed in v3.
# Consulted by test_golden_v2_corpus.py after loading golden_v2.json:
# for every v2-emitted key, look up the v3 key and assert value match.
V2_DEPRECATED_KEYS: dict[str, str] = {
    # populated as mismatches emerge during Task 1.5
}

# Numeric fields that need approximate comparison rather than exact
# equality (e.g., because v2 used numpy float32 while v3 uses Python
# float, or because the two take different rounding paths). Key is
# the v3 key name (after rename); value is the absolute tolerance.
V2_VALUE_TOLERANCE: dict[str, float] = {
    # populated as mismatches emerge during Task 1.5
}
