# Changelog

All notable changes to pyModeS are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [3.1.0] — 2026-04-14

Streaming-robustness release. Adds defences against phantom positions
at stream start and against DF20 CRC-collisions that attribute a
Comm-B reply to the wrong aircraft.

### Added

- `PipeDecoder` bootstrap cluster analysis for the first position per
  ICAO: lat/lon emission is held until `_BOOTSTRAP_K` (=5) candidate
  positions agree under a motion-consistency check. Prevents an
  initial phantom frame from anchoring the rolling position history.
  On each decode the held result dicts are retro-filled once the
  cluster locks. Scattered buffers reset and accumulate a fresh K.
- `PipeDecoder` altitude cross-check on DF20 Comm-B replies: if the
  message's 13-bit AC-code disagrees with the ICAO's most recent
  ADS-B-derived altitude by more than `_altitude_tolerance(dt)` (a
  linearly growing, floored-and-capped window), the BDS payload
  fields are stripped from the result and `altitude_mismatch=True`
  is set. The AC-code altitude itself is preserved so callers see
  why the frame was flagged.
- `PipeDecoder.flush()` method that finalizes any still-bootstrapping
  ICAOs, running cluster analysis on whatever candidates are
  buffered (even if fewer than K) and retro-filling the held result
  dicts in place. Automatically called by the batch `decode(list,
  timestamps=list)` code path so batch callers get positions on
  every resolvable frame without having to reach into `PipeDecoder`.
- Four new per-stream stat counters exposed via `PipeDecoder.stats`:
  `altitude_mismatch`, `position_rejected`, `bootstrap_held`,
  `bootstrap_reset`.

### Fixed

- `airborne_position_pair` now rejects CPR pairs that resolve to
  physically impossible latitudes (|lat| > 90). Root cause: real
  DF17 pairs that straddle a `cprNL` zone can slip past the
  pre-pair `NL(lat_even) == NL(lat_odd)` check and produce
  latitudes in [90, 270) — e.g. an aircraft climbing out of
  Amsterdam resolving to lat ≈ 113° over the Bering Sea.
  Observed on ICAO 485A33 (2025-04-13 19:34:57 UTC, OpenSky feed)
  — now rejected at the pair resolver rather than poisoning the
  receiver's position history.

## [3.0.0] — 2026-04-13

First release of the v3 ground-up rewrite. **Not backwards-compatible
with pyModeS 2.x.** See [docs/migration.md](./docs/migration.md) for
the migration guide.

### Added

- Unified `pyModeS.decode(msg)` returning a `Decoded` dict with every
  decodable field populated in one call
- Batch mode: `pyModeS.decode(list_of_msgs, timestamps=...)` preserves
  list length (errors become error-dicts, no exceptions)
- `PipeDecoder` stateful streaming decoder — per-ICAO state, CPR
  pair matching, TTL eviction, DF20/21 `icao_verified` promotion
  via a trusted-ICAO set populated from clean DF17/18 plain-text
  addresses
- `full_dict=True` mode populates every key in the canonical
  `_FULL_SCHEMA` (123 fields) for pandas / parquet workflows
- Phase 3 BDS 5,0/6,0 disambiguation via a `known=` aircraft-state
  kwarg — scores candidate registers against recent observations
  of groundspeed / track / heading / mach
- Airport database (ICAO 4-letter codes only) for surface CPR
  resolution: `surface_ref="EHAM"` or `surface_ref=(lat, lon)`
- Golden-file oracle test asserting v3 decode output matches
  `pyModeS 2.21.1` on the deduplicated `tests/data/` corpus
- MkDocs + Material documentation site (docs added in a later
  commit in this release)
- `modes` command-line tool with two subcommands:
  - `modes decode MESSAGE` for one-shot decoding (pretty or compact JSON)
  - `modes decode HEX1,HEX2,HEX3` inline-batch mode with shared
    `PipeDecoder` state so CPR pairs resolve across the batch
  - `modes decode --file PATH` for batch decoding a file of hex messages
  - `modes live --network HOST:PORT` for streaming TCP decode from a
    Mode-S Beast binary feed
  - `modes live --dump-to FILE` to tee JSON lines to a file. Every
    record carries both `raw_msg` (source hex) and `timestamp` so
    captures are self-contained for offline re-decode
  - `modes live --tui` for an interactive textual-based aircraft
    table: keyboard navigation (j/k/g/G), live incremental search
    (/) that filters as you type, sort cycling (s/r), responsive
    column set (7/10/18 cols by terminal width). Requires
    `pyModeS[tui]` extra
  - Graceful SIGINT/SIGTERM shutdown with final stats line
- `pyModeS[tui]` optional dependency: pulls in `textual>=0.50` for
  the `modes live --tui` interactive display
- `pyModeS.util` public helpers for low-level message inspection
  without going through `decode()`: `hex2bin`, `bin2int`, `hex2int`,
  `bin2hex`, `crc`, `df`, `icao`, `typecode`, `altcode`, `idcode`,
  `cprNL`. Thin wrappers over `_bits.py`, `_altcode.py`, `_idcode.py`
  and `position/_cpr.py` with no logic duplication.
- `scripts/smoke_test.sh` installs the freshly built wheel
  into a clean Python 3.12 venv and verifies the public API end to
  end (single-message decode, PipeDecoder baseline, batch CPR pair
  resolution, error-dict on malformed input).

### Fixed

- BDS 5,0 / 6,0 Phase 3 disambiguation now works cold-start
  (before any ADS-B frames have been cached). Root cause: the
  BDS 5,0 validator accepted roll angles up to ±50°, the full
  wire-format range, which let garbage payloads pass as track-
  and-turn reports with physically implausible banks (observed
  -44.5° on the TU Delft live feed). Tightened the gate to ±35°
  to match the commercial-airliner envelope (30° bank ≈ 2 G in
  a level turn).
- BDS 6,0 scorer now has reference fields to compare against in
  streaming mode. PipeDecoder derives approximate IAS and mach
  from cached groundspeed + altitude using a minimal ISA
  calculator in `pyModeS._aero` (zero-wind assumption, low-Mach
  approximation). Previously the scorer's `ias`/`mach` slots
  were always empty because ADS-B airborne-velocity BDS 0,9
  subtypes 1/2 only emit groundspeed; the scorer then returned
  +inf for every BDS 6,0 candidate and BDS 5,0 won every tie by
  default.
- `modes live --tui` no longer freezes after the "detected beast
  format, resyncing" line. Two root causes: the sink context
  manager wrap was lost during a prior refactor, and the
  on-detect stderr print corrupted rich's alt-screen buffer.
  Restored the context manager and silenced stderr writes when
  `--tui` is active.

### Changed

- Python 3.11+ minimum (was 3.9+)
- Internal message representation: Python int + bit-shift primitives
  (replaces numpy arrays and the Cython `c_common` extension)
- Every decoder API → single `decode()` returning a dict
- CPR resolution API: `reference=(lat, lon)` for airborne (180 NM
  tolerance), `surface_ref="EHAM"` or `surface_ref=(lat, lon)` for
  surface (45 NM tolerance)
- Header fields (df, icao, crc, crc_valid) are computed eagerly in
  `Message.__init__` as plain attributes instead of lazy
  `cached_property` descriptors (measurably faster on streaming
  decode loads, and the decode path always needs all four)
- `modes live` stream timestamps are now derived from the Beast
  48-bit MLAT counter, with tick rate auto-calibrated per
  connection from the delta between consecutive `recv()` bursts.
  Works on both dump1090 12 MHz counters and radarcape / GNS
  AirSquitter 1 GHz nanosecond counters without configuration.
  Gives sub-microsecond per-frame precision across a TCP burst,
  replacing the previous coarse one-`time.time()`-per-batch
  behaviour.
- `modes live --tui` rewritten from `rich.live.Live` to a full
  `textual.App` with a `DataTable` widget, interactive row
  cursor, and per-tick diff-update of cells (only cells whose
  values actually change are redrawn). The result: no more
  whole-table flashing on each message, cursor and scroll
  position survive refreshes, and the default sort is now by
  ICAO address (stable) instead of last-seen (reshuffles on
  every message). Dropped the `rich>=13.0` dependency in favour
  of `textual>=0.50`.

### Removed

- Cython extension (`c_common`) and its build dependency
- Legacy function-per-field API (`pms.adsb.callsign`, `pms.commb.bds`,
  `pms.common.hex2bin`, etc.). The former submodule paths
  (`pyModeS.adsb`, `pyModeS.commb`, `pyModeS.ehs`, `pyModeS.els`,
  `pyModeS.common`, `pyModeS.bds`, `pyModeS.streamer`,
  `pyModeS.extra`) are intercepted by a meta-path finder in
  `pyModeS._v2_removed` which raises `V2APIRemovedError` (an
  `ImportError` subclass) with a migration hint pointing at
  `pyModeS.decode()` and — for `pyModeS.common` specifically —
  at the restored helpers in `pyModeS.util`. Both `from pyModeS.X
  import Y` and bare attribute access (`pms.X`) hit the same
  error message.
- numpy hard dependency.
- `modeslive` CLI entry point: replaced by `modes live` / `modes
  decode`. The v3 package still registers `modeslive` as a console
  script — running it prints a migration hint to stderr and exits
  with code 2, rather than vanishing into a bare `command not
  found` after a `pip install -U pyModeS`.
