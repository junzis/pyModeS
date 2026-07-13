# Benchmark capture data

## `airsquitter_2026-07-13_120s.csv.gz`

Two-minute capture from the public TU Delft AirSquitter Mode-S Beast feed:

- Source: `airsquitter.lr.tudelft.nl:10006` (TCP, Beast binary)
- Capture date: 2026-07-13
- Frames: 176,612
- Uncompressed format: `timestamp,hex_message`, one frame per line
- Compressed size: approximately 2 MiB
- SHA-256: `fa433eb8dc2ec9cf6ebd40c1bf0a095ae753960d5e8c42ae6da15cc28eb3baea`

The timestamps are reconstructed by `pyModeS.cli._source.NetworkSource`
from the Beast MLAT counter, anchored to wall-clock time when the TCP data
is received. Mode A/C and Beast status frames are omitted because
`NetworkSource` yields only Mode-S short and long frames.

Capture and compact conversion:

```bash
timeout --signal=INT 120 \
  modes live \
  --network airsquitter.lr.tudelft.nl:10006 \
  --quiet \
  --dump-to /tmp/pymodes-live-mixed.jsonl

jq -r '"\(.timestamp),\(.raw_msg)"' \
  /tmp/pymodes-live-mixed.jsonl \
  | gzip -9 > scripts/data/airsquitter_2026-07-13_120s.csv.gz
```

Run the associated isolated three-version benchmark with:

```bash
python scripts/benchmark_mixed_traffic.py
```
