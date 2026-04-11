# Changelog

All notable changes to pyModeS are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

First alpha of the v3 ground-up rewrite. **Not backwards-compatible
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
- `scripts/smoke_test_alpha.sh` installs the freshly built wheel
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

### Performance

pyModeS v3 is **4.41× faster** than `pyModeS 2.21.1`
pure-Python, **2.44× faster** than `pyModeS 2.21.1`
with the compiled `c_common` extension, and **2.71×
faster** than rs1090 single-core Rust. Measured on jet1090's
`long_flight.csv` (172,432 Beast-format messages, 7 runs × 1 loop,
single-core). See `scripts/benchmark_decode.py`.

The speedup comes from:
- A 256-entry CRC-24 lookup table replacing the bit-by-bit CRC
  remainder loop (cross-checked against FlightAware dump1090)
- Byte-level hex parsing via `int(hexstr, 16)` instead of
  Python-level hex-char validation
- Eager computation of Message header fields in `__init__` instead
  of `cached_property` descriptor indirection
- Hoisting the decoder dispatch table import out of the per-call
  decode hot path
