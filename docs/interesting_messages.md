# Interesting messages

A growing catalogue of real-world Mode-S / ADS-B messages that exhibit
instructive edge cases — CRC-lucky phantoms, 1090 MHz FRUIT, BDS
ambiguity, malformed payloads, etc. Each entry keeps the raw hex plus a
few neighbouring messages so you can replay them through the decoder
and reason about what went wrong.

Use this as a reference when:

- debugging a surprising decode output;
- writing a new plausibility check for `PipeDecoder`;
- building a test case from a real-world pathology instead of a
  synthetic one.

Message annotations use the format `DF=<n> TC=<n> [BDS=<a,b>]` so the
frame class is obvious at a glance.

---

## DF17 TC=19 velocity — CRC-valid FRUIT phantom

**Case:** isolated velocity sample in an otherwise clean cruise track
disagrees violently with the surrounding messages.

- **Flight:** KLM90J, EDDB → EHAM, B738, 2025-04-13
- **Aircraft:** `icao24 = 484556`
- **Source:** OpenSky Trino `velocity_data4`
- **Symptom:** a single CRC-valid DF17 TC=19 frame decodes to
  `gs = 558 kt, track = 340.9°` sandwiched between samples reporting
  `gs ≈ 445 kt, track ≈ 272°`, at a gap of only 1.6 s from the prior
  real sample.

### Raw messages (5 before, phantom, 5 after)

```text
04:36:52.352  DF=17 TC=19   8D484556990DBE023008844B0DE0   gs=445 trk=272.1 vr=+64
04:36:53.894  DF=17 TC=19   8D484556990DBE02100484462BC9   gs=445 trk=271.9 vr=  0
04:36:54.954  DF=17 TC=19   8D484556990DBE021804842889C1   gs=445 trk=271.9 vr=  0
04:36:56.395  DF=17 TC=19   8D484556990DBE0218088460D3C1   gs=445 trk=271.9 vr=-64
04:37:21.123  DF=17 TC=19   8D484556990DBE021008840E71C9   gs=445 trk=271.9 vr=+64
04:37:22.758  DF=17 TC=19   8D484556990CB8423008844B2DE1   gs=558 trk=340.9 vr=+64   <-- phantom
04:38:00.883  DF=17 TC=19   8D484556990DBE01F80484710EE2   gs=445 trk=271.8 vr=  0
04:38:05.347  DF=17 TC=19   8D484556990DBE01F004841FACEA   gs=445 trk=271.8 vr=  0
04:38:06.953  DF=17 TC=19   8D484556990DBD01F004841AB3B8   gs=444 trk=271.8 vr=  0
04:38:08.003  DF=17 TC=19   8D484556990DBD01F804847411B0   gs=444 trk=271.8 vr=  0
04:38:11.633  DF=17 TC=19   8D484556990DBD01D80484316D99   gs=444 trk=271.7 vr=  0
```

All eleven frames pass CRC. All decode as `DF=17, TC=19, ICAO=484556`.
Only the phantom disagrees with the aircraft's physical state: +113 kt
groundspeed and +69° track in 1.6 seconds is dynamically impossible for
a commercial jet (max realistic rates ≈ 5 kt/s accel, 9°/s rate-3 turn).

### Byte-by-byte diff

Fixing the frame layout `DF|ICAO24|ME56|CRC24`:

```text
              DF | ICAO     | ME (bytes 5-11)          | CRC
real          8D | 48 45 56 | 99 0D BE 02 10 08 84     | 0E 71 C9
phantom       8D | 48 45 56 | 99 0C B8 42 30 08 84     | 4B 2D E1
xor           00 | 00 00 00 | 00 01 06 40 20 00 00     | 45 5C 28
```

Five of the 14 bytes in the payload differ, scattered across multiple
fields — this isn't a single short burst. Both the DF/CA byte and the
plain-text ICAO24 field come through intact, which is why OpenSky
attributes the phantom to this aircraft.

### Why it passes CRC

Mode-S uses a 24-bit CRC. For DF17/18 the CRC is computed over the
88-bit payload (no XOR with ICAO like DF20/21). Guarantees:

- detects **all** 1- and 2-bit errors;
- detects **all** burst errors ≤ 24 bits;
- for arbitrary multi-bit errors, the residual false-accept rate is
  ~2⁻²⁴ ≈ 6 × 10⁻⁸ per corrupted message.

That's small per-message, but 1090 MHz is busy: OpenSky's network
ingests billions of Mode-S transmissions per day, so occasional CRC-lucky
corruptions are expected.

At 1090 MHz the dominant mechanism is **FRUIT** (False Replies
Unsynchronised with Interrogator Transmission). Two aircraft's squitters
overlap at a receiver; bits from one transmission smear onto the other.
The merged frame occasionally satisfies all three conditions at once:

1. the DF nibble still looks like a valid type (DF17),
2. bits 9-32 still read as a plausible ICAO24,
3. the 24-bit CRC over the mangled payload happens to equal the trailing
   24 bits (or, equivalently, the error pattern is a multiple of the CRC
   polynomial).

Sample-timing slips in a single receiver's demodulator are a lesser
contributor but can produce the same signature.

### How PipeDecoder handles it

Since 3.3.0, `PipeDecoder._reject_velocity_mismatch` cross-checks each
CRC-valid DF17/18 TC=19 frame against the per-ICAO velocity anchor
(`_adsb_velocity[icao] = (timestamp, groundspeed, track)`) populated
from previously-accepted TC=19 frames. Tolerances scale with the gap
since the anchor:

```text
gs  tolerance = max(20 kt,  min(Δt · 5 kt/s,  200 kt))
trk tolerance = max(20°,    min(Δt · 10°/s,  180°))
```

The phantom above has Δt = 1.6 s → tol ≈ (20 kt, 20°), measured diff
(113 kt, 69°) → rejected. The result gets `velocity_mismatch=True` and
its velocity fields are scrubbed. The anchor is **not** updated on a
rejected frame, so a phantom cannot poison the next check.

### Reproduce

```python
from pyModeS import PipeDecoder

pipe = PipeDecoder()
pipe.decode("8D484556990DBE021008840E71C9", timestamp=1.0)     # real
r = pipe.decode("8D484556990CB8423008844B2DE1", timestamp=2.6)  # phantom
assert r["velocity_mismatch"] is True
assert r.get("groundspeed") is None
```

---

## Cold-start position bootstrap — cluster over first K candidates

**Case:** at the very start of a stream, the motion-consistency check
cannot run — there is no ring buffer to compare against. If the first
CPR pair that resolves happens to be a phantom, it would lock the
anchor at the wrong location and every real subsequent position would
get rejected as "inconsistent".

- **Flight:** KLM47U, EHAM → LFBO, B738, 2025-05-05
- **Aircraft:** `icao24 = 485A33`
- **Takeoff:** 12:44:20 UTC from EHAM 18L (around 52.32 °N, 4.74 °E)

### First 12 airborne position messages

Annotated with the CPR parity flag `F` (even = 0, odd = 1). Pairs form
when an even and odd from the same ICAO land within `pair_window = 10 s`
of each other:

```text
12:44:20.471  DF=17 TC=11  F=0   8D485A33580572E136F2A2037D58   alt= -25
12:44:20.982  DF=17 TC=11  F=1   8D485A335805864C74EBE5B0CC6B   alt=   0   <-- 1st pair resolves
12:44:21.555  DF=17 TC=11  F=0   8D485A33580592E156F2A215806A   alt=  25
12:44:21.950  DF=17 TC=11  F=0   8D485A33580592E162F2A2BAE957   alt=  25
12:44:22.913  DF=17 TC=11  F=1   8D485A335805B64CAAEBE6E13238   alt=  75   <-- 2nd pair resolves
12:44:23.385  DF=17 TC=11  F=0   8D485A335805B2E18AF2A490B664   alt=  75
12:44:24.009  DF=17 TC=11  F=1   8D485A335805C64CC8EBE6A65861   alt= 100   <-- 3rd pair resolves
12:44:24.457  DF=17 TC=11  F=0   8D485A335805D2E1ACF2A45AD98B   alt= 125
12:44:24.849  DF=17 TC=11  F=1   8D485A335805E64CE4EBE7247A8D   alt= 150   <-- 4th pair resolves
12:44:25.323  DF=17 TC=11  F=1   8D485A335805F64CF2EBE81ACBB3   alt= 175
12:44:25.778  DF=17 TC=11  F=1   8D485A335805F64CFEEBE84338BF   alt= 175
12:44:26.322  DF=17 TC=11  F=0   8D485A33580702E1E4F2A623AB8E   alt= 200   <-- 5th pair resolves, lock fires
```

Each of the first five resolved pairs produces a bootstrap candidate:

```text
candidate #1  12:44:20.982   (52.3200, 4.7390)
candidate #2  12:44:22.913   (52.3212, 4.7390)
candidate #3  12:44:24.009   (52.3219, 4.7390)
candidate #4  12:44:24.849   (52.3226, 4.7391)
candidate #5  12:44:26.322   (52.3236, 4.7392)
```

All five lie within ~400 m of each other along runway 18L — a
motion-consistent cluster. On the fifth arrival `_bootstrap_try_lock`
promotes the whole cluster into `_position_history`, retro-fills
`latitude`/`longitude` on every held result dict — typically two per
candidate, one for each half of the CPR pair — and subsequent positions
go through the standard motion check.

### What would break without the bootstrap step

If the decoder simply took the first resolved pair as the anchor:

1. A single CRC-collision position frame at stream start (common with
   noisy ground receivers during taxi/lineup) would lock the anchor
   hundreds of km away.
2. Every real follow-up position would fail motion-consistency against
   that phantom anchor — the stream would look "broken" for this ICAO.
3. The motion-consistency buffer would never recover: every real
   position gets rejected, so the ring buffer stays seeded with
   phantoms.

The cluster step breaks the chicken-and-egg problem by requiring
corroboration before committing to an anchor.

### Handling

`_bootstrap_accumulate`:

- each bootstrap entry holds a **list** of result dicts — when the
  caller comes from the pair-resolution path in `_handle_cpr_pair` it
  passes both halves of the resolved pair `[later, earlier]` so both
  get retro-filled together;
- sets `latitude`/`longitude` to `None` on every held dict so
  unverified positions are never emitted to the caller;
- increments `_stats["bootstrap_held"]`;
- on reaching `_BOOTSTRAP_K = 5`, calls `_bootstrap_try_lock`.

`_bootstrap_try_lock`:

- runs an O(K²) neighbour scan: for each candidate count how many
  others are reachable under `_pair_consistent` (same helper as the
  steady-state motion check);
- picks the candidate with the most neighbours;
- if it has **zero** neighbours, returns `False` → caller clears the
  buffer and increments `_stats["bootstrap_reset"]` (all K were
  scattered phantoms; start fresh);
- otherwise, promotes that candidate plus its neighbours, retro-fills
  `latitude`/`longitude` on every held result dict for each cluster
  member, seeds the last `_POSITION_HISTORY_SIZE` members into
  `_position_history`, and clears the bootstrap buffer.

`flush()` runs the same cluster analysis at end-of-stream for any
ICAO still in bootstrap — useful for batch consumers that finish with
fewer than K candidates.

### Reproduce

```python
from pyModeS import PipeDecoder

# Six CPR pairs (five consistent along EHAM 18L + one phantom far away);
# each pair contributes two result dicts — even and odd — so 12 mock
# dicts total. The list-of-dicts per candidate is how the real decoder
# wires both halves of a pair through _bootstrap_accumulate.
pipe = PipeDecoder()
results = [{} for _ in range(12)]  # 6 pairs × 2 halves
pipe._bootstrap["485A33"] = [
    (52.3200, 4.7390, 1000.982, [results[0],  results[1]]),
    (52.3212, 4.7390, 1002.913, [results[2],  results[3]]),
    (52.3219, 4.7390, 1004.009, [results[4],  results[5]]),
    (60.0000, 10.0000, 1004.500, [results[6],  results[7]]),   # phantom
    (52.3226, 4.7391, 1004.849, [results[8],  results[9]]),
    (52.3236, 4.7392, 1006.322, [results[10], results[11]]),
]
assert pipe._bootstrap_try_lock("485A33", min_candidates=5) is True

# The five Schiphol pairs (10 dicts) were retro-filled; the phantom
# pair's two dicts were not.
retrofilled = [r for r in results if "latitude" in r]
assert len(retrofilled) == 10
assert "latitude" not in results[6]
assert "latitude" not in results[7]

# History is seeded with (up to) the 5 most-recent cluster members.
assert len(pipe._position_history["485A33"]) == 5
```

---

## DF17 TC=11 airborne position — CRC-valid altitude ghost

**Case:** a single CRC-valid DF17 airborne-position frame decodes to
an altitude thousands of feet away from the aircraft's stable cruise
altitude. Same FRUIT / CRC-luck mechanism as the DF17 TC=19 velocity
phantom at the top of this page, different typecode.

- **Flight:** KLM90J, EDDB → EHAM, B738, 2025-04-13
- **Aircraft:** `icao24 = 484556`, stable at FL340 cruise
- **Symptom:** one TC=11 decodes to `altitude = 27 900 ft` between 180
  neighbours at 34 000 ft.

### Raw messages (5 before, phantom, 5 after; all sources)

```text
04:33:26.559  DF=17 TC=11 BDS=0,5   8D48455658AF86664DF2CD7CC4E9   alt=34000
04:33:27.091  DF=17 TC=11 BDS=0,5   8D48455658AF86664FF2B565BE0F   alt=34000
04:33:27.539  DF=17 TC=11 BDS=0,5   8D48455658AF82FB9200E0A1E0EF   alt=34000
04:33:28.049  DF=17 TC=11 BDS=0,5   8D48455658AF866653F28A1F8833   alt=34000
04:33:28.346  DF=20 BDS=6,0         A00015B8DD2A13302014003C75ED   alt=34000
04:33:28.500  DF=17 TC=11 BDS=0,5   8D48455658AF82FB9600B56A1E6C   alt=34000
04:33:28.565  DF=20                 A00015B858AF82FB9600B10A99D2   alt=34000
04:33:28.993  DF=17 TC=11 BDS=0,5   8D48455658AF866657F2602DF150   alt=34000
04:33:29.221  DF=17 TC=11 BDS=0,5   8D4845565C6AAA206D6E6095C950   alt=27900   <-- phantom
04:33:29.358  DF=20 BDS=6,0         A00015B8DD2A1530202400E8D740   alt=34000
04:33:29.559  DF=17 TC=11 BDS=0,5   8D48455658AF82FB9A0084CD3801   alt=34000
04:33:30.141  DF=17 TC=11 BDS=0,5   8D48455658AF82FB9C00691B39C4   alt=34000
04:33:30.661  DF=17 TC=11 BDS=0,5   8D48455658AF82FB9E0052FE2850   alt=34000
04:33:31.230  DF=17 TC=11 BDS=0,5   8D48455658AF86665FF1FDA91F93   alt=34000
```

The DF20 Comm-B frames interleaved above all report 34 000 ft from
their independent 13-bit AC-code field — independent corroboration that
the aircraft really is at FL340 at 04:33:29.

### Byte-by-byte diff

```text
               DF | ICAO     | ME (TC + altitude + cpr)      | CRC
real           8D | 48 45 56 | 58 AF 82 FB 92 00 E0 A1      | E0 EF
phantom        8D | 48 45 56 | 5C 6A AA 20 6D 6E 60 95      | C9 50
xor            00 | 00 00 00 | 04 C5 28 DB FF 6E 80 34      | 29 BF
```

Seven of the 11 payload bytes differ — a typical multi-bit FRUIT smear.
DF and ICAO come through intact, TC still decodes to 11 (the TC field
sits in the top 5 bits of byte 5 — `01011` is preserved in both), but
the altitude-code bits and CPR bits are completely rewritten.

### Handling

Since this change, `PipeDecoder._reject_df17_altitude_mismatch` runs
the same altitude cross-check used for DF20 (see the DF20 entry below),
but for CRC-valid DF17/18 BDS 0,5 frames:

```text
tol = max(500 ft, min(Δt · 100 ft/s, 5000 ft))
```

Here Δt ≈ 0.2 s → tol = 500 ft, |27 900 − 34 000| = 6 100 ft → reject.
On rejection, `altitude_mismatch=True` is set, the 13-bit AC-code
altitude stays on the result (for diagnostics) while `cpr_lat`,
`cpr_lon`, `cpr_format` are nulled so the phantom cannot pair with
real neighbours and produce a far-off lat/lon that the motion check
would have to clean up later. The anchor is **not** updated from a
rejected frame.

### Reproduce

```python
from pyModeS import PipeDecoder

pipe = PipeDecoder()
# A CRC-valid DF17 TC=11 at 04:33:27 established the anchor at FL340.
pipe._adsb_altitude["484556"] = (1000.0, 34000.0)

r = pipe.decode("8D4845565C6AAA206D6E6095C950", timestamp=1001.0)
assert r["altitude_mismatch"] is True
assert r["altitude"] == 27900     # preserved for diagnostics
assert r.get("cpr_lat") is None   # cleared so phantom won't pair
```

---

## DF20 Comm-B — CRC-collision altcode ghost

**Case:** an isolated DF20 reply arrives with a 13-bit AC-code altitude
30 000 ft below the surrounding traffic and a Comm-B payload that
doesn't pattern-match any known BDS register.

- **Flight:** KLM38Y, LSZH → EHAM, B738, 2025-04-13
- **Aircraft:** `icao24 = 484163` (CRC-derived ICAO of the phantom
  happens to match the real aircraft)
- **Source:** OpenSky Trino `rollcall_replies_data4`
- **Symptom:** a lone DF20 at 05:37:29.913 decodes to `altitude =
  2350 ft` with no identifiable BDS, surrounded by DF20/DF21 traffic
  reporting FL341 (34 075–34 100 ft). The decoded `magnetic_heading
  = 314°` on the real BDS 6,0 replies brackets the phantom on both
  sides — the aircraft is cruising, not descending.

### Raw messages (5 before, phantom, 5 after)

```text
05:37:28.174  DF=21 BDS=4,0   A8000800CA380030A800005F235B
05:37:28.187  DF=20 BDS=6,0   A00015BBEF8A233160D41AF07E22   alt=34075 hdg=314
05:37:28.413  DF=20 BDS=6,0   A00015BBEF8A233160CC1A60CA22   alt=34075 hdg=314
05:37:29.676  DF=20 BDS=6,0   A00015BCEF8A233160F41A49C8CC   alt=34100 hdg=314
05:37:29.688  DF=21 BDS=4,0   A8000800CA380030A800005F235B
05:37:29.913  DF=20           A3A142168C14F64881711E2DB71A   alt= 2350   <-- phantom
05:37:30.003  DF=20 BDS=6,0   A00015BCEF8A233160E41AA910CC   alt=34100 hdg=314
05:37:30.069  DF=20 BDS=6,0   A00015BCEF8A233160DC1A07E0C5   alt=34100 hdg=314
05:37:30.155  DF=20 BDS=5,0   A00015BC803E27382004E2CFC9EA   alt=34100 gs=448
05:37:30.177  DF=20 BDS=4,0   A00015BCCA380030A80000C404F6   alt=34100
05:37:30.546  DF=20 BDS=6,0   A00015BCEF8A233160CC1AE738C5   alt=34100 hdg=314
```

Nearest CRC-valid ADS-B position (the anchor source):

```text
05:37:29.401  DF=17 TC=11   8D48416358AFB049A5733842BB0E   alt=34075
05:37:29.982  DF=17 TC=11   8D48416358AFC049CB7327A362CB   alt=34100
```

### Mechanism

DF20's address/parity field XORs the 24-bit CRC with the ICAO24, so a
corrupted DF20 reply can XOR-decode back to the same ICAO as a real
neighbouring aircraft (or worse, our own). The 13-bit AC-code altitude
sits in DF20's header (bits 20-32), completely independent of the MB
payload — and of the CRC-derived ICAO. That makes it an ideal
cross-check: the header's altitude and a recent CRC-valid ADS-B altitude
come from different message classes, so a genuine reply from the same
aircraft has them within a few hundred feet (plus whatever the aircraft
has climbed/descended since the anchor).

Note that the phantom above doesn't get a BDS classification at all —
its MB bits don't match any register signature cleanly, so the inferer
punts. That's common for these frames: CRC-lucky multi-bit corruption
rarely produces a cleanly-structured 56-bit MB payload.

### Handling

`PipeDecoder._reject_on_altitude_mismatch` fires when
`|ac_code − adsb_anchor| > _altitude_tolerance(Δt)`:

```text
tol = max(500 ft, min(Δt · 100 ft/s, 5000 ft))
```

100 ft/s is an emergency-descent envelope (~6000 fpm); the 500-ft floor
absorbs 25-ft-LSB quantisation + sample jitter; the 5000-ft cap keeps
stale anchors from rubber-stamping any altitude. On rejection,
`altitude_mismatch=True` is set and every BDS-payload field listed in
`_BDS_FIELDS_TO_CLEAR` is nulled so a downstream Phase-3 disambiguator
can't be poisoned by the phantom's bits. The header AC-code altitude
is deliberately left in place — callers can see why the frame was
flagged.

Here: Δt ≈ 0.5 s → tol = 500 ft, |2350 − 34075| = 31 725 ft. Clear reject.

### Reproduce

```python
from pyModeS import PipeDecoder

pipe = PipeDecoder()
# Pretend we just saw a DF17 position putting this aircraft at FL341.
pipe._adsb_altitude["484163"] = (1000.0, 34075.0)

r = pipe.decode("A3A142168C14F64881711E2DB71A", timestamp=1000.5)
assert r["altitude_mismatch"] is True
assert r.get("bds") is None
assert r["altitude"] == 2350   # preserved for diagnostics
```

---

## DF17 CPR pair resolving to impossible latitude

**Case:** an even/odd DF17 position pair passes the `cprNL` consistency
check yet decodes to a latitude outside [−90°, 90°].

- **Flight:** climbing out of EHAM, 2025-04-13 19:34 UTC
- **Aircraft:** `icao24 = 485A33`
- **Pair:**

```text
even: 8F485A33397C737A27D1B18072CD   cpr_lat=113939  cpr_lon=119217   DF=17 TC=7 (surface)
odd:  8D485A33581D663872E86A3BBFFF   cpr_lat= 72761  cpr_lon= 59498   DF=17 TC=11 (airborne)
```

### Surrounding position stream

```text
19:34:54.292  DF=17 TC=11   8D485A33581D063920E87D008CD0   alt=4600
19:34:54.834  DF=17 TC=11   8D485A33581D12CD84EF1FE2BB2B   alt=4625
19:34:55.401  DF=17 TC=11   8D485A33581D2638EEE87768E345   alt=4650
19:34:55.862  DF=17 TC=11   8D485A33581D22CD56EF19157A4B   alt=4650
19:34:56.433  DF=17 TC=11   8D485A33581D32CD38EF1657A916   alt=4675
19:34:57.005  DF=17 TC=11   8D485A33581D4638A2E86F1892EF   alt=4700
19:34:57.232  DF=17 TC=11   8D485A33581D4638A2E86F1892EF   alt=4700
19:34:57.473  DF=17 TC=11   8D485A33581D56388AE86D03FC35   alt=4725
19:34:57.551  DF=17 TC=11   8D485A33581D4638A2E86F1892EF   alt=4700
19:34:57.789  DF=17 TC= 7   8F485A33397C837A41D1B6750ABD   gs= 7.0 trk=202.5   <-- nearby TC=7
19:34:57.913  DF=17 TC= 7   8F485A33397C737A27D1B18072CD   gs= 7.0 trk=199.7   <-- phantom even
```

The aircraft is climbing normally at ~25 ft/s — lots of clean TC=11
airborne positions. Then two TC=7 **surface-position** frames appear
while the aircraft is at 4700 ft. Surface position encoding uses a
different CPR lat/lon scaling from airborne, so pairing a TC=7 even
frame with a nearby TC=11 odd frame sends the math off a cliff: the
resulting `Rlat` ends up outside [−90°, 90°].

### What happens without the guard

The global airborne CPR equations compute `Rlat_even` and `Rlat_odd`
and pick one based on an "is even newer" flag. With these cross-class
cpr values, the arithmetic yields `lat ≈ 113.22°`, `lon ≈ −169°` —
geometrically a point north of the North Pole. The `cprNL` zone-crossing
check doesn't catch it because the latitudes land in the same NL zone
after modular wraparound; the bug only shows in the final number.

### Handling

`airborne_position_pair` ends with a final sanity guard:

```python
if abs(lat) > 90 or abs(lon) > 180:
    return None
```

A pair that fails the guard is discarded entirely — neither frame
becomes an anchor, and the enclosing `PipeDecoder._handle_cpr_pair`
leaves the result's `latitude`/`longitude` keys unset.

### Reproduce

```python
from pyModeS.position._cpr import airborne_position_pair

result = airborne_position_pair(
    113939, 119217, 72761, 59498, even_is_newer=False,
)
assert result is None
```

---

## Position jump rejected by motion-consistency

**Case:** a valid CPR pair resolves to a geometrically sensible lat/lon
that's hundreds of kilometres from the aircraft's known recent track —
the signature of two phantom frames co-operating.

- **Flight:** KLM30A, EHAM → LSZH, B738, 2025-04-13
- **Aircraft:** `icao24 = 484164`, on descent into LSZH
- **Rejection timestamp:** 09:01:03.961 UTC

### Surrounding position stream

```text
09:01:03.575  DF=17 TC=12   8D484164602B33D825DF33A49786   alt=7475
09:01:03.670  DF=17 TC=12   8D484164602B275037D32FB795B8   alt=7450
09:01:03.766  DF=17 TC=12   8D484164602B275029D328D75A02   alt=7450
09:01:03.855  DF=17 TC=12   8D484164602B23D7F9DF1AFDD978   alt=7450
09:01:03.946  DF=17 TC=12   8D4841646019B736C5D12199D7CA   alt=4075   <-- altitude ghost #1
09:01:03.961  DF=17 TC=12   8D484164602B13D7E9DF118EF036   alt=7475   <-- motion reject triggered here
09:01:04.017  DF=17 TC=12   8D4841646019B736C5D12199D7CA   alt=4075
09:01:04.115  DF=17 TC=12   8D484164602B074FFBD30EDDD331   alt=7400
09:01:04.184  DF=17 TC=12   8D484164602B03D7CBDF001F9CAC   alt=7400
09:01:04.289  DF=17 TC=12   8D4841646029F3D7BBDEF705482F   alt=7375
09:01:04.388  DF=17 TC=12   8D4841646029F3D7ABDEEFD89C8B   alt=7375
```

At the reject, the per-ICAO ring buffer looked like:

```text
history buffer (lat, lon):
  (47.619, 8.384)  # Switzerland
  (47.617, 8.385)  # Switzerland
  (47.616, 8.385)  # Switzerland
  (47.615, 8.386)  # Switzerland
  (53.765, 9.624)  # Hamburg ← phantom, ~700 km away
```

The reject fires when the *next* CPR pair resolves to another
Hamburg-like position — the motion-consistency check walks the ring
buffer and fails to find any entry within
`max_speed_kmps · Δt + motion_margin_km` of the candidate.

The stream also shows an **altitude ghost** (TC=12 frames decoding to
4075 ft while the aircraft is at 7400–7475 ft) interleaved with the
real positions — same CRC-collision mechanism, different manifestation.
Those don't trip the motion check because the raw stream sample is
spatially close; the altitude mismatch stays in the position's BDS 0,5
payload and passes through today.

### Handling

`PipeDecoder._motion_consistent(icao, lat, lon, timestamp)` checks the
new candidate against every entry in `_position_history[icao]` (a ring
buffer of up to 5 recent `(lat, lon, t)` tuples). A candidate is
accepted iff at least one history entry lies within
`max_speed_kmps · Δt + motion_margin_km` — defaults 1500 kt and 2 km.

On rejection:

1. `_handle_cpr_pair` drops the resolved `latitude`/`longitude` from
   the result dict.
2. `_stats["position_rejected"]` is incremented.
3. The rejected position **is** appended to the ring buffer anyway —
   so a sustained burst of consistent phantoms (a real-world stream,
   not a single CRC fluke) can eventually out-vote a stale anchor and
   rotate the history toward reality rather than locking the decoder
   out forever.

For the first few samples of a new ICAO (before the ring buffer is
locked), candidates live in `_bootstrap[icao]` instead and go through
the cluster-analysis step in `_bootstrap_try_lock`.

### Reproduce

```python
from pyModeS import PipeDecoder

pipe = PipeDecoder()
# Seed history with Swiss-airspace positions (the aircraft's real track).
pipe._position_history["484164"] = [
    (47.619, 8.384, 990.0),
    (47.617, 8.385, 992.0),
    (47.616, 8.385, 995.0),
    (47.615, 8.386, 998.0),
]
# A candidate in Hamburg is unreachable in the elapsed seconds.
assert pipe._motion_consistent("484164", 53.765, 9.624, 1000.0) is False
```

---

# Open cases

Pathologies without a robust handler today. Documented here so future
work has a starting point — if you find a clean example please append
the raw hex to the relevant section.

## DF21 Comm-B BDS 6,0 from a co-altitude neighbour

**Case:** an isolated DF21 reply whose decoded BDS 6,0 payload
(magnetic heading, IAS, Mach, vertical rates) looks *dynamically*
consistent with the aircraft's own flight envelope but differs by
enough that the sample shows up as a clear outlier against the
surrounding BDS 6,0 stream.

- **Witnessed on:** KLM24F, LFBO → EHAM, 2025-04-30 around 16:30 UTC.
- **Witness conditions:** our aircraft at ~FL216, Mach 0.65, IAS 289 kt;
  a neighbour on the same STAR at ~FL270 broadcasting Mach 0.78, IAS
  316 kt, with matching heading and vertical-rate profile. The
  neighbour's DF20 frames (which carry the 13-bit AC-code altitude)
  are caught by `_reject_on_altitude_mismatch`. Its DF21 frames have
  no altitude header and slip through.

### Why it's hard

Three checks were tried and rejected:

1. **Mach smoothness against per-ICAO state.** Real Mach changes by up
   to 0.13 over ~30 s during cruise-to-IAS-transition descent; a
   tolerance tight enough to catch the phantom (Δ ≈ 0.13 per sample)
   false-positived thousands of real samples on the same flight.
2. **Expected Mach derived from groundspeed + anchor altitude.**
   Phantom Mach-IAS pair differed from the gs-derived expectation by
   only 0.092 — well inside the 0.20 tolerance needed to accommodate
   ±100 kt of real-world wind.
3. **Mach-IAS internal consistency at the anchor altitude.** The
   phantom's `(Mach 0.78, IAS 316)` evaluated at the anchor's 2400 ft
   produces a TAS-from-Mach of ~338 kt vs TAS-from-IAS of ~295 kt —
   a 43 kt disagreement, just above the 40 kt threshold used for
   cruise-phase checks. But lowering the altitude floor that enables
   this check (currently `> 500 ft`) any further starts rejecting
   real late-descent traffic, and tightening the 40 kt bound
   false-positives in the presence of large wind changes.

The signal that would reliably catch this pathology is *interrogator
timing*: a DF20/DF21 reply is a response to a ground-station Mode-S
interrogation, and a phantom would typically arrive outside the
expected response window for this ICAO. OpenSky's archived streams
don't preserve that timing, so catching this class of phantom offline
would need either a stricter-but-noisier Mach/IAS envelope or
acceptance of a higher false-positive rate.

### How to contribute

If you catch a clean example in the wild, append the raw 14-byte DF21
frame plus ~5 neighbours before/after, the aircraft's own anchor
altitude/Mach/IAS at the time, and the suspected source (neighbour
ICAO if known).

---

## Adding a new case

When you find another interesting message, append an `##` section with
the same structure:

1. **Case** — one-line summary of the symptom.
2. **Context** — flight/aircraft/source so the case can be reproduced
   or re-pulled from the upstream data.
3. **Raw messages** — the interesting frame plus ~5 neighbours
   before and ~5 after. Every line must show timestamp, `DF=<n>
   TC=<n> [BDS=<a,b>]`, raw hex, and the few decoded fields that make
   the pathology legible.
4. **Mechanism** — a plausible physical / protocol reason.
5. **Handling** — what (if anything) `PipeDecoder` does with it.
6. **Reproduce** — a minimal snippet that runs against stock pyModeS,
   using `from pyModeS import ...` (not `import pyModeS as pms`).
