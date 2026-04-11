# pyModeS

Fast, ergonomic, dictionary-first decoder for Mode-S and ADS-B messages in
pure Python. Ground-up v3 rewrite of `pyModeS` — 2.44× faster than
`pyModeS 2.21.1`'s compiled C extension on a realistic workload, with no
Cython build, no numpy hard dependency, and a single unified `decode()`
returning a plain dict.

[![license](https://img.shields.io/badge/license-GPL--3.0-blue)](https://github.com/junzis/pyModeS/blob/main/LICENSE)

## Install

```sh
pip install "pyModeS>=3"
```

Python 3.11+ required.

## Usage examples

### Single-message decode

`pyModeS.decode()` returns a `Decoded` dict with every decodable
field populated in one pass.

```python
import pyModeS

result = pyModeS.decode("8D406B902015A678D4D220AA4BDA")
print(result)
# {
#     'df': 17,
#     'icao': '406B90',
#     'crc_valid': True,
#     'typecode': 4,
#     'bds': '0,8',
#     'callsign': 'EZY85MH',
#     'category': 0,
#     'wake_vortex': 'No category information',
# }
```

### Batch decode (mixed message types)

Pass a list of hex strings and parallel timestamps. Any mix of
downlink formats, typecodes, and Comm-B registers is fine —
the dispatcher routes each message to the right decoder and
uses the timestamps to resolve CPR pairs and disambiguate
ambiguous Comm-B registers.

```python
import pyModeS

results = pyModeS.decode(
    [
        "8D406B902015A678D4D220AA4BDA",  # DF17 BDS 0,8 identification
        "8D485020994409940838175B284F",  # DF17 BDS 0,9 airborne velocity
        "8D40058B58C901375147EFD09357",  # DF17 BDS 0,5 airborne pos (even)
        "8D40058B58C904A87F402D3B8C59",  # DF17 BDS 0,5 airborne pos (odd)
        "A000178D10010080F50000D5893C",  # DF20 BDS 1,0 data link capability
        "A8000D9FA55A032DBFFC000D8123",  # DF21 BDS 6,0 heading & speed
    ],
    timestamps=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
)
assert results[0]["callsign"] == "EZY85MH"
assert results[1]["groundspeed"] == 159
assert results[3]["latitude"] is not None  # CPR pair resolved
```

### Surface position with airport reference

Surface CPR needs a reference within ~45 NM. Pass an ICAO airport
code (looked up in the shipped airport database) or an explicit
`(lat, lon)` tuple.

```python
import pyModeS

# Real DF18 surface movement on LFBO (Toulouse-Blagnac).
r = pyModeS.decode("903a23ff426a4e65f7487a775d17", surface_ref="LFBO")
print(r["latitude"], r["longitude"])  # 43.6264..., 1.3747...
```

### Streaming decoder

`PipeDecoder` is stateful — it holds per-ICAO state across calls,
matches CPR pairs automatically, evicts stale aircraft after a
TTL, and flags DF20/21 messages as `icao_verified` when their
CRC-derived ICAO was already seen in a clean DF17/18 plaintext.

```python
from pyModeS import PipeDecoder

pipe = PipeDecoder(surface_ref="EHAM")
for msg, timestamp in stream:
    decoded = pipe.decode(msg, timestamp=timestamp)
    if "latitude" in decoded:
        print(decoded["icao"], decoded["latitude"], decoded["longitude"])
```

See [`docs/quickstart.md`](./docs/quickstart.md) for the full tour
(full-dict mode, error handling, attribute access).

## CLI

pyModeS ships with a `modes` command-line tool for ad-hoc decoding
and live streaming.

### `modes decode` — one-shot and file mode

```sh
# Decode one hex message (pretty-printed JSON)
modes decode 8D406B902015A678D4D220AA4BDA

# Decode several messages inline — comma-separated, emits JSON lines
modes decode 8D40058B58C901375147EFD09357,8D40058B58C904A87F402D3B8C59,8D406B902015A678D4D220AA4BDA

# With airborne CPR reference (single message only)
modes decode 8D40058B58C901375147EFD09357 --reference 49.0 6.0

# Compact JSON piped to jq
modes decode 8D406B902015A678D4D220AA4BDA --compact | jq .

# Decode a file of hex messages (one per line OR timestamp,hex CSV)
modes decode --file captures/flight.log

# Stdin + surface CPR
cat taxi.log | modes decode --file - --surface-ref LFBO
```

### `modes live` — streaming TCP source

```sh
# Stream decoded JSON lines from a dump1090-style beast feed
modes live --network localhost:30005

# Tee output to a file
modes live --network host:30005 --dump-to flight.jsonl

# Stream from the TU Delft public feed (live aircraft over Europe)
modes live --network airsquitter.lr.tudelft.nl:10006

# Interactive live aircraft table (requires pyModeS[tui] extra)
pip install "pyModeS[tui]"
modes live --network host:30005 --tui
```

Mode-S Beast binary format is supported (dump1090 port 30005 and
equivalents). See [`docs/quickstart.md`](./docs/quickstart.md) for
the full command reference.

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

| Decoder | Wall time | Throughput | vs pyModeS v3 |
|---|---|---|---|
| **pyModeS v3 (pure Python)** | **2.06s ± 0.01** | **83,549 msg/s** | **1.00×** |
| pyModeS 2.21.1 (Python with compiled C) | 5.03s ± 0.01 | 34,303 msg/s | 0.41× |
| rs1090 (Rust) | 5.60s ± 0.01 | 30,798 msg/s | 0.37× |
| pyModeS 2.21.1 (Python) | 9.09s ± 0.02 | 18,959 msg/s | 0.23× |

pyModeS v3 is **2.44× faster** than `pyModeS 2.21.1`'s compiled C
extension, **4.41× faster** than `pyModeS 2.21.1` pure-Python, and
**2.71× faster** than rs1090's single-core Rust — all while remaining
pure Python with no C/Cython build.

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

pyModeS 3 is **not backwards-compatible** with pyModeS 2.x. The
function-per-field API (`pms.adsb.callsign(msg)`, ...) is replaced
by a single `decode()` returning a dict. See the [migration
guide](https://github.com/junzis/pyModeS/blob/main/docs/migration.md) for the full equivalence table.

If you aren't ready to migrate:

```sh
pip install "pyModeS<3"
```

Both v2 and v3 coexist on PyPI because they use different import
names (`pyModeS` vs `pyModeS`).

## Links

- Source: https://github.com/junzis/pyModeS
- Changelog: [CHANGELOG.md](https://github.com/junzis/pyModeS/blob/main/CHANGELOG.md)
- Issues: https://github.com/junzis/pyModeS/issues
- License: GPL-3.0 (see `LICENSE`)

## Attribution

pyModeS is a project created by Junzi Sun, who works at TU Delft,
[Aerospace Engineering Faculty](https://tudelft.nl/en/ae/). It is
supported by many
[contributors](https://github.com/junzis/pyModeS/graphs/contributors)
from different institutions.

If you use pyModeS in academic work, please cite:

```bibtex
@article{sun2019pyModeS,
    author={J. {Sun} and H. {V\^u} and J. {Ellerbroek} and J. M. {Hoekstra}},
    journal={IEEE Transactions on Intelligent Transportation Systems},
    title={pyModeS: Decoding Mode-S Surveillance Data for Open Air Transportation Research},
    year={2019},
    doi={10.1109/TITS.2019.2914770},
    ISSN={1524-9050},
}
```
