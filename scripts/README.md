# Maintainer scripts

Run these commands from the repository root. Scripts are grouped by purpose
through their names; generated benchmark reports live in
`scripts/benchmark_results/`, and committed input data lives in
`scripts/data/`.

## Streaming example

- `stream_filtered.py` — configurable high-throughput example using a live
  Mode-S Beast feed or the committed replay capture. Defaults to DF17/20/21
  while excluding ADS-B typecodes 28/29/31.

  ```bash
  uv run python scripts/stream_filtered.py \
    --network airsquitter.lr.tudelft.nl:10006 \
    --include-meteo > decoded.jsonl
  ```

  `--include-meteo` is optional and enables heuristic Comm-B BDS 4,4/4,5
  reports when the feed is expected to contain meteorological data.

## Benchmarks

- `benchmark_mixed_traffic.py` — isolated v2.21.1, released v3.5.0, v3.5.1,
  and prefiltered v3.5.1 comparison on mixed captured traffic. It measures
  throughput, immediate streaming position yield, and coordinate agreement.
  By default it fails below 80% of v2 position yield, below 99% agreement
  within 100 m, or when v3.5.1 yields fewer positions than v3.5.0. The two
  percentage floors are configurable through command-line options. Writes
  `benchmark_results/mixed_traffic.md` by default.
- `benchmark_pipe.py` — synthetic high-cardinality PipeDecoder comparison.
  Writes `benchmark_results/pipe.md` by default.
- `benchmark_cpr.py` — focused CPR primitive comparison against the v2 NumPy
  implementation.

  ```bash
  uv run python scripts/benchmark_mixed_traffic.py
  uv run python scripts/benchmark_pipe.py
  uv run --with numpy python scripts/benchmark_cpr.py
  ```

The version-comparison benchmarks build the working tree and resolve released
versions from PyPI in isolated temporary environments. They require network
access unless those packages are already cached.

## Generated data

- `generate_airport_db.py` — refreshes `src/pyModeS/data/airports.py` from
  OurAirports.
- `generate_v2_fixture.py` — regenerates the committed v2.21.1 golden oracle.

  ```bash
  uv run python scripts/generate_airport_db.py
  uv run --no-project --with pyModeS==2.21.1 \
    python scripts/generate_v2_fixture.py
  ```

## Release smoke tests

- `smoke_test_wheel.sh [wheel]` — installs a built wheel in a clean virtual
  environment and checks the public API.
- `smoke_test_cli.sh` — checks CLI decoding and a short live Beast connection.

The CLI smoke test requires network access. The wheel smoke test accepts an
explicit wheel path; without one, it builds a fresh working-tree wheel in a
temporary directory so stale files under `dist/` cannot be selected.
