#!/usr/bin/env bash
# Alpha smoke test: install the freshly-built wheel into a clean
# venv and verify the public API works end-to-end. Run manually,
# not in CI.
#
# Usage: scripts/smoke_test_alpha.sh [/path/to/wheel]
#
# If no argument: uses the most recently built dist/*.whl. PyPI
# normalises the distribution name to lowercase (PEP 503), so the
# wheel file on disk is named `pymodes-3.0.0.dev0-*.whl` even
# though the package imports as `pyModeS`.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

WHEEL="${1:-}"
if [ -z "$WHEEL" ]; then
    WHEEL=$(ls -t dist/pymodes-*.whl 2>/dev/null | head -1 || true)
fi

if [ -z "$WHEEL" ] || [ ! -f "$WHEEL" ]; then
    echo "ERROR: no wheel found under dist/. Run 'uv build' first." >&2
    exit 1
fi

echo "Testing wheel: $WHEEL"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

uv venv --python 3.12 "$TMPDIR/venv" >/dev/null
# `uv venv` doesn't ship pip; use `uv pip install` with the venv
# as the target interpreter instead.
uv pip install --quiet --python "$TMPDIR/venv/bin/python" "$WHEEL"

"$TMPDIR/venv/bin/python" - <<'PY'
import pyModeS
from pyModeS import PipeDecoder

# Version sanity — whatever pyproject.toml says at build time.
# Passes at 3.0.0.dev0 today, will still pass at 3.0.0a1 after
# the pre-publish version bump.
print(f"pyModeS.__version__ = {pyModeS.__version__}")
assert pyModeS.__version__.startswith("3."), (
    f"unexpected version: {pyModeS.__version__}"
)

# Single-message decode
r = pyModeS.decode("8D406B902015A678D4D220AA4BDA")
assert r["df"] == 17, r
assert r["icao"] == "406B90", r
assert r["crc_valid"] is True, r
assert r["typecode"] == 4, r
assert r["bds"] == "0,8", r
assert r["callsign"] == "EZY85MH", r
assert r["category"] == 0, r

# PipeDecoder construction + stats baseline. Check the counters we
# have always guaranteed rather than pinning the full dict — newer
# releases can add counters without breaking this smoke test.
p = PipeDecoder()
for _k in ("total", "decoded", "crc_fail", "pending_pairs"):
    assert p.stats[_k] == 0, p.stats

# Batch mode with CPR pair resolution on an even/odd airborne
# position pair (same ICAO, closely-spaced timestamps).
results = pyModeS.decode(
    [
        "8D40058B58C901375147EFD09357",
        "8D40058B58C904A87F402D3B8C59",
    ],
    timestamps=[1.0, 2.0],
)
assert len(results) == 2
# First frame yields no position yet (no pair partner).
assert results[0].get("latitude") is None, results[0]
# Second frame completes the pair — latitude/longitude filled.
assert results[1]["latitude"] is not None, results[1]
assert results[1]["longitude"] is not None, results[1]
# Sanity-check the decoded coordinates land in the expected
# ballpark (Luxembourg area, roughly 49.8 N, 6.1 E).
assert 49.0 < results[1]["latitude"] < 50.5, results[1]
assert 5.5 < results[1]["longitude"] < 7.0, results[1]

# Error-dict in batch on malformed input (errors become dicts,
# never exceptions, so the result list length always matches
# the input).
err_results = pyModeS.decode(["not hex"])
assert len(err_results) == 1
assert "error" in err_results[0], err_results[0]
assert "raw_msg" in err_results[0], err_results[0]

# pyModeS.util surface: the restored public helpers.
from pyModeS.util import hex2bin, crc, icao, typecode

assert hex2bin("8D")[:8] == "10001101"
assert crc("8D406B902015A678D4D220AA4BDA") == 0
assert icao("8D406B902015A678D4D220AA4BDA") == "406B90"
assert typecode("8D406B902015A678D4D220AA4BDA") == 4

# v2 removal shim: a legacy import still fails, but with the
# migration-pointing error instead of a bare ModuleNotFoundError.
from pyModeS._v2_removed import V2APIRemovedError

try:
    from pyModeS.adsb import callsign  # noqa: F401

    raise AssertionError("pyModeS.adsb should have raised")
except V2APIRemovedError as e:
    assert "pyModeS.adsb" in str(e)
    assert "decode(" in str(e)
    assert "migration.md" in str(e)

print("smoke test PASSED")
PY
