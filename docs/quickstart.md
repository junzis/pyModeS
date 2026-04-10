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
transient `PipeDecoder`:

```python
results = pymodes.decode(
    ["8D40058B58C901375147EFD09357",
     "8D40058B58C904A87F402D3B8C59"],
    timestamps=[1446332400.0, 1446332405.0],
)
assert results[1]["latitude"] is not None  # CPR pair resolved
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
# Airport code
r = pymodes.decode("8FC8200A3AB8F5F893096B000000", surface_ref="NZCH")
print(r["latitude"], r["longitude"])  # -43.48..., 172.54...

# Explicit tuple (e.g., receiver location)
r = pymodes.decode("8FC8200A3AB8F5F893096B000000", surface_ref=(-43.48, 172.53))
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
