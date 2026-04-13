#!/usr/bin/env bash
# Manual integration smoke test for the `modes` CLI.
#
# Runs three checks: single-message decode, stdin file decode, and
# a 5-second sample against the TU Delft public Mode-S feed. Not
# intended for CI (requires network + hangs on feed outages). Run
# manually during release prep.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo ">>> 1. Single message decode"
uv run modes decode 8D406B902015A678D4D220AA4BDA \
    | grep -q '"callsign": "EZY85MH"'
echo "    PASSED"

echo ">>> 2. File decode via stdin"
echo "8D406B902015A678D4D220AA4BDA" \
    | uv run modes decode --file - --compact \
    | grep -q '"df":17'
echo "    PASSED"

echo ">>> 3. Live against TU Delft feed (5 second sample)"
# Use timeout to cap the run; the command exits 124 on timeout or
# 0 on graceful SIGINT, both acceptable.
set +e
timeout --signal=INT 5 uv run modes live \
    --network airsquitter.lr.tudelft.nl:10006 \
    > /tmp/pyModeS_live_sample.jsonl 2>/tmp/pyModeS_live_sample.err
rc=$?
set -e
if [ $rc -ne 0 ] && [ $rc -ne 124 ]; then
    echo "    FAILED: modes live exit code $rc"
    cat /tmp/pyModeS_live_sample.err
    exit 1
fi
n_lines=$(wc -l < /tmp/pyModeS_live_sample.jsonl)
if [ "$n_lines" -lt 1 ]; then
    echo "    FAILED: no JSON lines captured"
    cat /tmp/pyModeS_live_sample.err
    exit 1
fi
head -1 /tmp/pyModeS_live_sample.jsonl | grep -q '"df"'
echo "    PASSED ($n_lines lines captured)"

echo
echo "=== modes CLI smoke test PASSED ==="
