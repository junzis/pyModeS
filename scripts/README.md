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
    --network airsquitter.lr.tudelft.nl:10006 > decoded.jsonl
  ```

## Benchmarks

- `benchmark_mixed_traffic.py` — isolated v2, released-v3, updated-v3, and
  prefiltered-v3 comparison on mixed captured traffic. Writes
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

The CLI smoke test requires network access. The wheel smoke test uses the most
recent `dist/pymodes-*.whl` when no path is supplied.
