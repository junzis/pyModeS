# Quickstart

## Single-message decode

```python
import pymodes

result = pymodes.decode("8D406B902015A678D4D220AA4BDA")
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

The returned object is a `Decoded` — a subclass of `dict` with
attribute-style access, JSON serialization, and pandas/parquet
compatibility. Read individual fields either by key or as an
attribute:

```python
result["icao"]      # '406B90'
result.icao         # '406B90' — same thing
result["callsign"]  # 'EZY85MH'
result.get("altitude")  # None — missing keys are safe via .get()
```

## Batch decode

Pass a list of messages plus timestamps to run them through a
transient `PipeDecoder`. The batch can mix any downlink formats,
typecodes, and Comm-B registers — the dispatcher picks the right
decoder per message:

```python
results = pymodes.decode(
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

assert results[0]["callsign"] == "EZY85MH"       # identification
assert results[1]["groundspeed"] == 159          # velocity
assert results[3]["latitude"] is not None        # CPR pair resolved
assert results[4]["bds"] == "1,0"                # Comm-B capability
assert results[5]["magnetic_heading"] is not None  # Comm-B BDS 6,0
```

Errors in the batch become error-dicts (`{"error": ..., "raw_msg": ...}`)
so the output list length always matches the input length.

## Streaming decoder

`PipeDecoder` holds per-ICAO state across calls. This lets it:

- Resolve CPR pairs from consecutive even/odd frames
- Disambiguate BDS 5,0/6,0 Comm-B using recently-observed state
- Verify DF20/21 ICAO addresses against ones learned from DF17/18

```python
from pymodes import PipeDecoder

pipe = PipeDecoder(surface_ref="EHAM")
for msg, timestamp in stream:
    decoded = pipe.decode(msg, timestamp=timestamp)
    if "latitude" in decoded:
        print(decoded["icao"], decoded["latitude"], decoded["longitude"])

print(pipe.stats)  # {'total': ..., 'decoded': ..., 'crc_fail': ..., 'pending_pairs': ...}
```

See the [PipeDecoder deep-dive](pipe.md) for the full state model.

## Surface positions

Surface CPR (BDS 0,6) needs a reference within ~45 NM. Pass either
an ICAO airport code (looked up in the shipped database) or an
explicit `(lat, lon)` tuple:

```python
# Airport code — real DF18 surface movement from the jet1090 corpus,
# aircraft on LFBO (Toulouse-Blagnac) taxiway
r = pymodes.decode("903a23ff426a4e65f7487a775d17", surface_ref="LFBO")
print(r["latitude"], r["longitude"])  # 43.6264..., 1.3747...

# Explicit tuple (e.g., receiver location)
r = pymodes.decode("903a23ff426a4e65f7487a775d17", surface_ref=(43.63, 1.37))
```

## Full-dict mode

For pandas / parquet workflows that need uniform column shapes:

```python
result = pymodes.decode("8D406B902015A678D4D220AA4BDA", full_dict=True)
# Result contains all ~123 schema keys; missing values default to None
```

## Error handling

Malformed input raises an exception in single-message mode:

```python
from pymodes.errors import InvalidHexError

try:
    pymodes.decode("not hex")
except InvalidHexError:
    pass
```

In batch mode, the same input becomes an error-dict instead:

```python
results = pymodes.decode(
    ["not hex", "8D406B902015A678D4D220AA4BDA"],
    timestamps=[0, 1],
)
assert "error" in results[0]
assert results[1]["icao"] == "406B90"
```

## CLI

pymodes ships with a `modes` command-line tool, installed as a
console script when you run `pip install pymodes`.

### `modes decode`

```
modes decode [--compact] [--full-dict] [--surface-ref REF]
             (MESSAGE [--reference LAT LON] | --file PATH)
```

Three input shapes:

- **Single message** — `modes decode HEX` prints a pretty-printed
  JSON object (or one-line compact JSON with `--compact`).
- **Inline batch** — `modes decode HEX1,HEX2,HEX3` comma-separated
  messages, sharing a transient `PipeDecoder` so CPR pairs resolve
  automatically.
- **File mode** — `modes decode --file PATH` reads from a file (one
  hex per line or `timestamp,hex` CSV). Use `-` as `PATH` for stdin.

Output format is **pretty-printed JSON by default** in all three
shapes — one indented `{...}` block per message, separated by a
blank line. Pass `--compact` to switch to one-line-per-message
output that composes with `jq`, pandas, parquet writers, etc.

Flags:

- `--compact` — emit one-line JSON instead of pretty-printed. In
  batch shapes this yields one JSON line per message (JSONL).
- `--full-dict` — populate every key in the canonical schema
- `--reference LAT LON` — airborne CPR reference (only valid with
  a single positional MESSAGE — not with `--file` or comma-batch,
  since one reference cannot apply to multiple aircraft)
- `--surface-ref REF` — surface CPR reference (airport ICAO code
  like `LFBO`, or a `lat,lon` string)
- `--file PATH` — read from a file; use `-` for stdin

Examples:

```sh
# Single message, pretty
modes decode 8D406B902015A678D4D220AA4BDA

# Single message + airborne reference
modes decode 8D40058B58C901375147EFD09357 --reference 49.0 6.0

# Inline batch — comma-separated, one pretty JSON block per message
modes decode 8D40058B58C901375147EFD09357,8D40058B58C904A87F402D3B8C59,8D406B902015A678D4D220AA4BDA

# Inline batch compact output (JSONL) for piping to jq
modes decode 8D40058B58C901375147EFD09357,8D40058B58C904A87F402D3B8C59,8D406B902015A678D4D220AA4BDA --compact

# Single message, compact JSON for piping
modes decode 8D406B902015A678D4D220AA4BDA --compact | jq .

# File + surface reference (all aircraft at LFBO)
modes decode --file captures/lfbo.csv --surface-ref LFBO

# File from stdin
cat flight.log | modes decode --file -
```

### `modes live`

```
modes live --network HOST:PORT [--surface-ref REF]
                               [--full-dict]
                               [--dump-to FILE]
                               [--tui]
                               [--quiet]
```

Opens a TCP connection to a Mode-S Beast binary feed (dump1090's
default port 30005, dump1090-fa, readsb, piaware, AirSquitter) and
emits decoded JSON lines to stdout as they arrive. Legacy AVR raw
text format is not supported in the alpha.

Flags:

- `--network HOST:PORT` — required TCP endpoint
- `--surface-ref REF` — forwarded to the internal `PipeDecoder`
  for surface CPR resolution
- `--full-dict` — emit every schema key per line
- `--dump-to FILE` — tee JSON lines to a file in addition to
  stdout (incompatible with `--tui`)
- `--tui` — interactive live aircraft table (requires
  `pymodes[tui]` extra; incompatible with `--dump-to` and
  `--quiet`)
- `--quiet` — suppress stdout (use with `--dump-to`)

Examples:

```sh
# Basic streaming to stdout
modes live --network localhost:30005

# Public test feed over Europe (TU Delft)
modes live --network airsquitter.lr.tudelft.nl:10006

# Tee to a file for later analysis
modes live --network host:30005 --dump-to flight.jsonl

# Interactive TUI
pip install "pymodes[tui]"
modes live --network host:30005 --tui
```

Signal handling: Ctrl-C (SIGINT) and SIGTERM trigger a clean
shutdown and print a final stats line to stderr.

Reconnect: the network source automatically reconnects on dropped
connections with exponential backoff (0.5 s → 10 s cap).
