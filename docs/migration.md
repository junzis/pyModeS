# Migrating from pyModeS 2.x to pyModeS 3

pyModeS 3 is a ground-up rewrite with a cleaner API, faster internals,
and no Cython extension. It is **not backwards-compatible** with
pyModeS 2.x.

If you aren't ready to migrate, pin the old version:

```sh
pip install "pyModeS<3"
```

pyModeS 2.21.1 continues to work and will remain available on PyPI.

## Install

```sh
# v3
pip install "pyModeS>=3"

# v2 (legacy)
pip install "pyModeS<3"
```

Versions 2 and 3 occupy the same PyPI distribution and import name.
Python package names are normalized case-insensitively, so installing
one version replaces the other in a given environment. Use separate
virtual environments when running or comparing both versions.

## Import change

```python
# pyModeS 2.x
import pyModeS as pms
pms.adsb.typecode("8D...")

# pyModeS 3
import pyModeS
result = pyModeS.decode("8D...")
result["typecode"]
```

## API change — the big one

pyModeS 2.x has a function-per-field API: you call
`pms.adsb.callsign(msg)`, then `pms.adsb.altitude(msg)`, then
`pms.adsb.velocity(msg)`, and so on. Each call re-parses the message
header.

pyModeS 3 has a single `decode()` function that returns every
decodable field in one pass:

```python
import pyModeS
result = pyModeS.decode("8D406B902015A678D4D220AA4BDA")
# Read whatever you need from the returned dict:
callsign = result.get("callsign")
altitude = result.get("altitude")
typecode = result.get("typecode")
```

The returned `Decoded` object is a `dict` subclass — JSON-serializable,
pandas/parquet-compatible, usable with `**` unpacking and all standard
dict operations. It also supports attribute-style access as a
convenience:

```python
result.callsign  # same as result["callsign"]
```

## Equivalence table

| pyModeS 2.x call | pyModeS 3 equivalent |
|---|---|
| `pms.common.df(msg)` | `pyModeS.decode(msg)["df"]` |
| `pms.common.icao(msg)` | `pyModeS.decode(msg)["icao"]` |
| `pms.common.typecode(msg)` | `pyModeS.decode(msg)["typecode"]` |
| `pms.common.altcode(msg)` | `pyModeS.decode(msg)["altitude"]` (DF4/20) |
| `pms.common.idcode(msg)` | `pyModeS.decode(msg)["squawk"]` (DF5/21) |
| `pms.adsb.callsign(msg)` | `pyModeS.decode(msg)["callsign"]` |
| `pms.adsb.category(msg)` | `pyModeS.decode(msg)["category"]` |
| `pms.adsb.altitude(msg)` | `pyModeS.decode(msg)["altitude"]` |
| `pms.adsb.velocity(msg)` | `pyModeS.decode(msg)` → `groundspeed`, `track`, `vertical_rate`, or `airspeed`/`airspeed_type`/`heading` for subtypes 3/4 |
| `pms.adsb.oe_flag(msg)` | `pyModeS.decode(msg)["cpr_format"]` |
| `pms.adsb.position(m0, m1, t0, t1)` | `pyModeS.decode([m0, m1], timestamps=[t0, t1])` |
| `pms.adsb.position_with_ref(msg, lat, lon)` | `pyModeS.decode(msg, reference=(lat, lon))` |
| `pms.adsb.surface_position_with_ref(msg, lat, lon)` | `pyModeS.decode(msg, surface_ref=(lat, lon))` |
| `pms.bds.infer(msg, mrar=True)` | `pyModeS.decode(msg, include_meteo=True)["bds"]` (for DF20/21) |
| `pms.commb.cs20(msg)` | `pyModeS.decode(msg)["callsign"]` (for BDS 2,0) |
| `pms.commb.selalt40mcp(msg)` | `pyModeS.decode(msg)["selected_altitude_mcp"]` |
| `pms.commb.selalt40fms(msg)` | `pyModeS.decode(msg)["selected_altitude_fms"]` |
| `pms.commb.p40baro(msg)` | `pyModeS.decode(msg)["baro_pressure_setting"]` |
| `pms.commb.roll50(msg)` | `pyModeS.decode(msg)["roll"]` |
| `pms.commb.trk50(msg)` | `pyModeS.decode(msg)["true_track"]` |
| `pms.commb.gs50(msg)` | `pyModeS.decode(msg)["groundspeed"]` |
| `pms.commb.tas50(msg)` | `pyModeS.decode(msg)["true_airspeed"]` |
| `pms.commb.rtrk50(msg)` | `pyModeS.decode(msg)["track_rate"]` |
| `pms.commb.hdg60(msg)` | `pyModeS.decode(msg)["magnetic_heading"]` |
| `pms.commb.ias60(msg)` | `pyModeS.decode(msg)["indicated_airspeed"]` |
| `pms.commb.mach60(msg)` | `pyModeS.decode(msg)["mach"]` |
| `pms.commb.vr60baro(msg)` | `pyModeS.decode(msg)["baro_vertical_rate"]` |
| `pms.commb.vr60ins(msg)` | `pyModeS.decode(msg)["inertial_vertical_rate"]` |

See the [API reference](api.md) for the full list of decoded fields.

## Returned fields

pyModeS 2 did not expose one unified record with a field-name surface:
individual helpers returned scalars or function-specific tuples. pyModeS 3
collects those values into explicitly named dictionary fields. The equivalence
table above is the mapping to use when replacing each v2 helper or unpacked
tuple element.

## Live streams

pyModeS 2.x required manual CPR pair accumulation and ICAO tracking.
v3 provides `PipeDecoder`, which handles both automatically:

```python
# pyModeS 2.x — manual pair accumulation
import pyModeS as pms
import time

ac_states = {}
for msg in stream:
    icao = pms.common.icao(msg)
    if icao not in ac_states:
        ac_states[icao] = {}
    tc = pms.common.typecode(msg)
    if 9 <= tc <= 18:
        oe = pms.adsb.oe_flag(msg)
        slot = "even" if oe == 0 else "odd"
        ac_states[icao][slot] = msg
        ac_states[icao][f"t_{slot}"] = time.time()
        if "even" in ac_states[icao] and "odd" in ac_states[icao]:
            lat, lon = pms.adsb.position(
                ac_states[icao]["even"],
                ac_states[icao]["odd"],
                ac_states[icao]["t_even"],
                ac_states[icao]["t_odd"],
            )

# pyModeS 3 — one line of state
from pyModeS import PipeDecoder
pipe = PipeDecoder(surface_ref="EHAM")
for msg, t in stream:
    result = pipe.decode(msg, timestamp=t)
    # A global pair seeds the track; later frames also use local CPR.
    if result.get("latitude") is not None:
        print(result["icao"], result["latitude"], result["longitude"])
```

`PipeDecoder` also handles:

- Per-ICAO state for Comm-B BDS 5,0/6,0 disambiguation (Phase 3 scoring)
- TTL eviction of stale aircraft after 5 minutes of silence
- DF20/21 `icao_verified=True` promotion via a trusted-ICAO cache
  populated from clean DF17/18 plain-text addresses

See the [PipeDecoder deep-dive](pipe.md) for the full state model
and thread-safety notes.

## CLI rename: `modeslive` → `modes live`

pyModeS 2.x shipped a single console script called `modeslive`.
pyModeS 3 replaces it with a new `modes` command that has subcommands:

```sh
# v2
modeslive --source net --connect host 30005 beast

# v3
modes live --network host:30005
```

Notable differences:

- **Subcommand-style.** `modes decode` is a new one-shot sibling
  of `modes live`.
- **Simplified network flag.** `--network HOST:PORT` replaces
  `--source net --connect HOST PORT DATATYPE`. Only the Mode-S
  Beast binary format is supported; point at dump1090's port
  30005 (or the equivalent beast port on your feed).
- **Firehose default.** `modes live` writes JSON lines to stdout
  by default — pipe to `jq`, redirect to a file, or stream into
  a parquet writer.
- **Optional TUI.** The interactive aircraft table is now
  `modes live --tui`, which requires the `pyModeS[tui]` extra
  (`pip install "pyModeS[tui]"`). Powered by `rich` instead of
  `curses`.
- **RTL-SDR.** Deferred to a follow-up release. For now, pipe
  through `dump1090 --net` and connect via `--network
  localhost:30005`.

## Removed features

- **Cython extension (`c_common`)** — v3 is pure Python. Performance depends
  on the workload: the unified decoder does more work per offered message than
  a selective sequence of v2 helpers, while its stateful streaming path avoids
  repeated parsing and scales independently of the active-aircraft count.
  Applications that consume only selected DF/typecode combinations should
  prefilter them as described in the [PipeDecoder guide](pipe.md#high-volume-pre-filtering).
- **Python 3.9 / 3.10 support** — v3 requires Python 3.11+.
- **`pyModeS.streamer` subpackage** — the legacy streamer is not
  ported. The `modeslive` entry point is replaced by `modes live`
  (see the CLI rename section above).

## Pinning strategy

If any of your code still depends on v2 behavior, pin to v2 explicitly:

```
pyModeS<3
```

and migrate incrementally. Because v2 and v3 share the `pyModeS`
distribution and import name, they cannot coexist in one virtual environment.
Use a separate environment or process for each version while comparing them.
