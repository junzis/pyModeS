# PipeDecoder

`PipeDecoder` is pymodes' stateful streaming decoder. It processes
one message at a time and maintains per-ICAO state across calls, so:

- **CPR pairs** — an even/odd pair of airborne position frames
  produced ≤10 seconds apart is resolved to absolute lat/lon without
  needing an external reference.
- **BDS 5,0/6,0 disambiguation** — when a Comm-B message plausibly
  matches both registers, prior observations of groundspeed / track /
  heading are used to pick the better candidate (Phase 3 scoring).
- **DF20/21 ICAO verification** — DF17/18 messages populate a
  trusted-ICAO set; subsequent DF20/21 messages whose CRC-derived
  ICAO matches a trusted one are flagged with `icao_verified=True`.

## Basic usage

```python
from pymodes import PipeDecoder

pipe = PipeDecoder(surface_ref="EHAM", pair_window=10.0, eviction_ttl=300.0)

for raw_msg, timestamp in stream:
    result = pipe.decode(raw_msg, timestamp=timestamp)
    if "error" in result:
        continue
    ...

print(pipe.stats)  # counters
pipe.reset()       # clear all state
```

## Constructor options

- `surface_ref` — airport code or `(lat, lon)` for surface CPR
  resolution (single-message path). Required for surface positions
  to return lat/lon. Not needed for airborne.
- `full_dict` — if `True`, every decoded result is populated with
  every key from the canonical schema (missing fields = `None`).
- `pair_window` — maximum age gap (seconds) between an even and odd
  CPR frame for them to count as a pair. Default 10 seconds.
- `eviction_ttl` — per-ICAO state and pending CPR frames older than
  this are dropped lazily at the start of the next `decode()` call
  with a timestamp. Default 300 seconds (5 minutes).

## State lifecycle

Per-ICAO state is built incrementally from tracked fields in
decoded results:

- BDS 0,9 velocity → `groundspeed`, `track`, `heading`
- BDS 0,9 sub 3/4 → `airspeed` + `airspeed_type` routes to `ias` or `tas`
- BDS 5,0 → `groundspeed`, `track`, `tas`
- BDS 6,0 → `heading`, `ias`, `mach`

These values are then passed as `known=` to subsequent decodes of
the same ICAO, enabling Phase 3 disambiguation.

State entries carry a `_last_seen` timestamp. On each `decode()`
call with a timestamp, entries older than `eviction_ttl` are dropped.

## Thread safety

`PipeDecoder` is **not thread-safe**. Every `decode()` call mutates
internal state without locking. Wrap the instance with a lock if
multiple threads feed it concurrently:

```python
import threading
from pymodes import PipeDecoder

pipe = PipeDecoder()
lock = threading.Lock()

def decode_one(msg: str, ts: float):
    with lock:
        return pipe.decode(msg, timestamp=ts)
```

For single-producer pipelines (one reader thread draining a socket)
no locking is needed — just don't share the decoder across threads.

## Stats

`pipe.stats` returns a snapshot dict:

- `total` — messages offered to `decode()` (including corrupt inputs)
- `decoded` — messages that parsed successfully
- `crc_fail` — messages whose decoded `crc_valid` was `False`
- `pending_pairs` — CPR frames currently held waiting for their pair

The trusted ICAO set, per-ICAO state, and pending CPR frames are all
cleared by `reset()`.
