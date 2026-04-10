# Changelog

All notable changes to pymodes are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

First alpha of the v3 ground-up rewrite. **Not backwards-compatible
with pyModeS 2.x.** See [docs/migration.md](./docs/migration.md) for
the migration guide.

### Added

- Unified `pymodes.decode(msg)` returning a `Decoded` dict with every
  decodable field populated in one call
- Batch mode: `pymodes.decode(list_of_msgs, timestamps=...)` preserves
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

### Changed

- Package renamed: `pyModeS` → `pymodes` (lowercase import)
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

### Removed

- Cython extension (`c_common`) and its build dependency
- Legacy function-per-field API (`pms.adsb.callsign`, etc.)
- numpy hard dependency
- `pyModeS.streamer` subpackage (deferred to a future CLI / streamer
  spec)

### Performance

pymodes v3 is **4.41× faster** than `pyModeS 2.21.1`
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
