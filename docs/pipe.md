# PipeDecoder

`PipeDecoder` is pyModeS' stateful streaming decoder. It processes one
message at a time and maintains per-ICAO state across calls, so:

- **CPR pair resolution** — an even/odd pair of airborne-position
  frames produced ≤ `pair_window` seconds apart is resolved to absolute
  lat/lon without needing an external reference.
- **BDS 5,0 / 6,0 disambiguation** — when a Comm-B message plausibly
  matches both registers, prior observations of groundspeed, track,
  and heading score the candidates and pick the better fit.
- **DF20/21 ICAO verification** — CRC-valid DF17/18 frames populate a
  trusted-ICAO set; a later DF20/21 whose CRC-derived ICAO matches one
  in the set is flagged with `icao_verified=True`.
- **Phantom rejection** — CRC alone doesn't catch every FRUIT frame
  that happens to land with a plausible ICAO. Several cross-checks
  layered on top of CRC use per-ICAO anchors to drop phantoms before
  they pollute state (see [Validation](#validation) below).

## Basic usage

```python
from pyModeS import PipeDecoder

pipe = PipeDecoder(surface_ref="EHAM", pair_window=10.0, eviction_ttl=300.0)

for raw_msg, timestamp in stream:
    result = pipe.decode(raw_msg, timestamp=timestamp)
    print(result)
    ...

print(pipe.stats)  # counters
pipe.reset()       # clear all state
```

## Constructor options

- `surface_ref` — airport code or `(lat, lon)` for surface CPR
  resolution (single-message path). Required for surface positions to
  return lat/lon. Not needed for airborne.
- `full_dict` — if `True`, every decoded result is populated with every
  key from the canonical schema (missing fields = `None`).
- `pair_window` — maximum age gap (seconds) between an even and odd
  CPR frame for them to count as a pair. Default `10.0`.
- `eviction_ttl` — per-ICAO state and pending CPR frames older than
  this are dropped lazily at the start of the next `decode()` call
  with a timestamp. Default `300.0` (5 minutes).
- `max_speed_kt` — ceiling for the per-ICAO motion check (see
  [Validation](#validation)). Default `1500` — ~2× typical airliner
  cruise; loose enough to accept fast business jets and wind-boosted
  ground speeds, tight enough that a phantom hundreds of km away can't
  masquerade as a continuation of the real track.
- `motion_margin_km` — slack added to the motion envelope to absorb
  CPR quantisation + clock jitter. Default `2.0` km.

## State lifecycle

Per-ICAO state is built incrementally from tracked fields in decoded
results:

- BDS 0,9 velocity → `groundspeed`, `track`, `heading`
- BDS 0,9 sub 3/4 → `airspeed` + `airspeed_type` routes to `ias` or `tas`
- BDS 5,0 → `groundspeed`, `track`, `tas`
- BDS 6,0 → `heading`, `ias`, `mach`

These values are then passed as `known=` to subsequent decodes of the
same ICAO, enabling BDS 5,0 / 6,0 disambiguation. When `groundspeed`
and `altitude` are known but `ias`, `mach`, or `tas` aren't yet
observed, they're derived via the ISA atmosphere model so BDS 6,0
scoring still has a reference field.

State entries carry a `_last_seen` timestamp. On each `decode()` call
with a timestamp, entries older than `eviction_ttl` are dropped.

## Validation

On top of CRC, `PipeDecoder` runs four plausibility cross-checks
against per-ICAO anchors updated only from CRC-valid frames that
passed their own check. A frame that fails is kept (header fields
intact) so the caller can see it, but its position / velocity fields
are scrubbed, the anchor is not updated, and state is not mutated.

| Check | Frames | Against | Stats counter |
|-------|--------|---------|---------------|
| Altitude | DF20 (header AC-code) | ADS-B altitude anchor | `altitude_mismatch` |
| Altitude | DF17/18 BDS 0,5 | ADS-B altitude anchor | `altitude_mismatch` |
| Velocity | DF17/18 TC=19 | ADS-B velocity anchor; abs VR > 10 000 fpm | `velocity_mismatch` |
| Velocity | DF20/21 BDS 5,0 | ADS-B velocity anchor | `velocity_mismatch` |
| Heading | DF20/21 BDS 6,0 | ADS-B track anchor (wider tol.) | `velocity_mismatch` |

### Position bootstrap

The first few resolved positions for a new ICAO don't yet have an
anchor to cross-check against — so they're held back. The decoder
collects up to 5 candidate positions into `_bootstrap`, runs a cluster
analysis to pick a consistent seed, and only then promotes them into
the rolling position history used for the motion check. While held,
`latitude` / `longitude` are suppressed in the returned result; once
the cluster locks, **both halves** of each resolved CPR pair are
retro-filled, so batch callers who keep their result list around see
the positions on their early samples.

If no consistent cluster forms, the bootstrap buffer resets and
candidates start over — counted as `bootstrap_reset`.

### Motion check

Post-bootstrap, each candidate position is compared against the most
recent accepted anchor. The allowed distance is
`max_speed_kt * dt + motion_margin_km`. Positions that exceed it are
rejected (`position_rejected`) — the anchor still rotates through the
history regardless of accept/reject, so real tracks eventually
out-vote lingering phantoms.

### BDS coverage

What happens per register when it's offered to `PipeDecoder`:

| BDS | Dedicated check | Disambiguation scoring | Indirect scrub on DF20 altitude mismatch |
|-----|-----------------|------------------------|------------------------------------------|
| 0,5 airborne position | altitude | — | — |
| 0,9 velocity (TC=19) | gs / track / abs VR | — | — |
| 1,0, 1,7 data-link capability | — | — | yes (`supported_bds`) |
| 2,0 aircraft identification | — | — | yes (`callsign`) |
| 4,0 selected vertical intention | — | — | yes (MCP/FMS alt, VNAV, etc.) |
| 4,4, 4,5 meteorological | — | — | yes (wind, temperature, turbulence, …) |
| 5,0 track & turn | gs / true_track | yes | yes |
| 6,0 heading & speed | magnetic_heading | yes | yes |

- **Dedicated check** — a per-ICAO cross-check runs on this register;
  failing frames are scrubbed and counted in
  `altitude_mismatch` / `velocity_mismatch`.
- **Disambiguation scoring** — when the raw payload plausibly matches
  multiple registers, prior state scores candidates via
  `_SCORE_FIELDS_BDS50` / `_BDS60` (implemented only for 5,0 and 6,0).
- **Indirect scrub** — when a DF20 fails the altitude check, any
  inferred fields from the listed registers are wiped regardless of
  whether *this* register would have caught it.

A phantom DF20 whose inferred payload lands in 1,0 / 2,0 / 4,0 / 4,4 /
4,5 with a plausible AC-code altitude and no prior anchor passes
silently — the dedicated checks don't cover those registers.

## Thread safety

`PipeDecoder` is **not thread-safe** by default. Every `decode()` call
mutates internal state without locking. Wrap the instance with a lock
if multiple threads feed it concurrently:

```python
import threading
from pyModeS import PipeDecoder

pipe = PipeDecoder()
lock = threading.Lock()

def decode_one(msg: str, ts: float):
    with lock:
        return pipe.decode(msg, timestamp=ts)
```

For single-producer pipelines (one reader thread draining a socket) no
locking is needed — just don't share the decoder across threads.

## Stats

`pipe.stats` returns a snapshot dict:

- `total` — messages offered to `decode()` (including corrupt inputs)
- `decoded` — messages that parsed successfully
- `crc_fail` — messages whose decoded `crc_valid` was `False`
- `pending_pairs` — CPR frames currently held waiting for their pair
- `altitude_mismatch` — frames rejected by the altitude cross-check
- `velocity_mismatch` — frames rejected by a velocity / heading check
- `position_rejected` — post-bootstrap positions rejected by the
  motion check
- `bootstrap_held` — candidate positions added to the bootstrap buffer
  (some may end up promoted, others discarded on reset)
- `bootstrap_reset` — bootstrap buffers that failed to cluster and
  restarted

The trusted ICAO set, per-ICAO state, pending CPR frames, anchors,
bootstrap buffers, and position history are all cleared by `reset()`.
