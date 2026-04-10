# Quickstart

## Single-message decode

```python
import pymodes

result = pymodes.decode("8D406B902015A678D4D220AA4BDA")
print(result["df"])         # 17
print(result["icao"])       # '406B90'
print(result["typecode"])   # 4
print(result["callsign"])   # 'EZY85MH_'
```

The returned object is a `Decoded` — a subclass of `dict` with
attribute-style access, JSON serialization, and pandas/parquet
compatibility.

```python
print(result.df)       # 17 — same as result["df"]
print(result.callsign) # 'EZY85MH_'
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
