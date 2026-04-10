# pymodes

Fast, ergonomic, dictionary-first decoder for Mode-S and ADS-B messages in
pure Python. Ground-up v3 rewrite of `pyModeS` — 2.44× faster than
`pyModeS 2.21.1`'s compiled C extension on a realistic workload, with no
Cython build, no numpy hard dependency, and a single unified `decode()`
returning a plain dict.

[![license](https://img.shields.io/badge/license-GPL--3.0-blue)](https://github.com/junzis/pyModeS/blob/main/LICENSE)

## Install

```sh
pip install "pymodes>=3"
```

Python 3.11+ required.

## Quickstart

```python
import pymodes

# Single-message decode — returns a Decoded dict with every
# decodable field populated.
result = pymodes.decode("8D406B902015A678D4D220AA4BDA")
print(result["df"])         # 17
print(result["icao"])       # '406B90'
print(result["typecode"])   # 4
print(result["callsign"])   # 'EZY85MH_'

# Batch decode with timestamps — CPR pairs get resolved automatically.
results = pymodes.decode(
    ["8D40058B58C901375147EFD09357",
     "8D40058B58C904A87F402D3B8C59"],
    timestamps=[1446332400.0, 1446332405.0],
)
assert results[1]["latitude"] is not None

# Streaming decoder with per-ICAO state, CPR pair matching,
# TTL eviction, and DF20/21 ICAO verification.
from pymodes import PipeDecoder
pipe = PipeDecoder(surface_ref="EHAM")
for msg, timestamp in stream:
    decoded = pipe.decode(msg, timestamp=timestamp)
    if "latitude" in decoded:
        print(decoded["icao"], decoded["latitude"], decoded["longitude"])
```

## Features

- Unified `decode()` returns every decodable field in one dict
- Batch mode preserves list length (errors become error-dicts, not
  exceptions)
- `PipeDecoder` for streams: per-ICAO state, CPR pair accumulation,
  TTL eviction, DF20/21 ICAO verification via trusted-set promotion
- `full_dict=True` populates every key in the canonical 123-field
  schema for pandas / parquet workflows
- `known=` aircraft state disambiguates Comm-B BDS 5,0/6,0 ambiguity
- Airport ICAO database for surface CPR resolution (`surface_ref="EHAM"`)
- Type-checked under mypy strict across all source files
- Golden-file oracle regression test against `pyModeS 2.21.1`

## Performance

Measured on jet1090's
[`long_flight.csv`](https://github.com/xoolive/jet1090/blob/master/crates/rs1090/data/long_flight.csv)
(172,432 Beast-format messages, 7 runs × 1 loop, mean timings,
single-core only):

| Decoder | Wall time | Throughput | vs pymodes v3 |
|---|---|---|---|
| rs1090 (single-core Rust) | 5.60s ± 0.01 | 30,798 msg/s | 0.37× |
| pyModeS 2.21.1 (c_common, compiled C) | 5.03s ± 0.01 | 34,303 msg/s | 0.41× |
| pyModeS 2.21.1 (py_common, pure Python) | 9.09s ± 0.02 | 18,959 msg/s | 0.23× |
| **pymodes v3 (pure Python)** | **2.06s ± 0.01** | **83,549 msg/s** | **1.00×** |

pymodes v3 is **2.44× faster** than `pyModeS 2.21.1`'s compiled C
extension, **4.41× faster** than `pyModeS 2.21.1` pure-Python, and
**2.71× faster** than rs1090's single-core Rust — all while remaining
pure Python with no C/Cython build. For maximum throughput
(multi-core, compiled), [rs1090](https://github.com/xoolive/jet1090)
is the state of the art at ~250k msg/s.

Reproduce with `scripts/benchmark_decode.py`.

## Supported messages

- **DF4 / DF20:** altitude code (surveillance altitude reply)
- **DF5 / DF21:** identity code (squawk)
- **DF11:** all-call reply (partial — II/SI decoding deferred)
- **DF17 / DF18 ADS-B:**
  - TC 1-4 (BDS 0,8): identification + category
  - TC 5-8 (BDS 0,6): surface position
  - TC 9-18 (BDS 0,5): airborne position (barometric altitude)
  - TC 19 (BDS 0,9): airborne velocity (all 4 subtypes)
  - TC 20-22 (BDS 0,5): airborne position (GNSS altitude)
  - TC 28 (BDS 6,1): aircraft status
  - TC 29 (BDS 6,2): target state and status
  - TC 31 (BDS 6,5): operational status
- **DF20 / DF21 Comm-B:**
  - BDS 1,0: data link capability
  - BDS 1,7: common-usage GICB capability
  - BDS 2,0: aircraft identification
  - BDS 3,0: ACAS active resolution advisory
  - BDS 4,0: selected vertical intention
  - BDS 4,4: meteorological routine air report
  - BDS 4,5: meteorological hazard report
  - BDS 5,0: track and turn report
  - BDS 6,0: heading and speed report

## Migrating from pyModeS 2.x

pymodes 3 is **not backwards-compatible** with pyModeS 2.x. The
function-per-field API (`pms.adsb.callsign(msg)`, ...) is replaced
by a single `decode()` returning a dict. See the [migration
guide](https://pymodes.readthedocs.io/en/latest/migration/) for the full equivalence table.

If you aren't ready to migrate:

```sh
pip install "pyModeS<3"
```

Both v2 and v3 coexist on PyPI because they use different import
names (`pyModeS` vs `pymodes`).

## Links

- Source: https://github.com/junzis/pyModeS
- Changelog: [CHANGELOG.md](https://github.com/junzis/pyModeS/blob/main/CHANGELOG.md)
- Issues: https://github.com/junzis/pyModeS/issues
- License: GPL-3.0 (see `LICENSE`)

## Attribution

pyModeS is a project created by Junzi Sun, who works at
[TU Delft](https://www.tudelft.nl/en/),
[Aerospace Engineering Faculty](https://www.tudelft.nl/en/ae/),
[CNS/ATM research group](http://cs.lr.tudelft.nl/atm/). It is
supported by many
[contributors](https://github.com/junzis/pyModeS/graphs/contributors)
from different institutions.

If you use pymodes in academic work, please cite:

```bibtex
@article{sun2019pymodes,
    author={J. {Sun} and H. {V\^u} and J. {Ellerbroek} and J. M. {Hoekstra}},
    journal={IEEE Transactions on Intelligent Transportation Systems},
    title={pyModeS: Decoding Mode-S Surveillance Data for Open Air Transportation Research},
    year={2019},
    doi={10.1109/TITS.2019.2914770},
    ISSN={1524-9050},
}
```
