# PyHoldem Pro - k6 load testing suite

These scripts demonstrate the API's ability to handle institutional-grade
concurrency. They live in `scripts/load/` so they ship with the repo
and run identically in dev, CI, and against staging.

## Quick start

Local dev (k6 against `localhost:8000`):

```bash
# Smoke test (30s, 1 VU, used by CI)
k6 run -e BASE_URL=http://localhost:8000 scripts/load/smoke.js

# Full read-heavy load (1000 RPS, 1 minute)
k6 run -e BASE_URL=http://localhost:8000 scripts/load/read_heavy.js

# Game session lifecycle (100 concurrent users, 2 min)
k6 run -e BASE_URL=http://localhost:8000 scripts/load/game_session_lifecycle.js

# WebSocket live (50 concurrent WS connections)
k6 run -e BASE_URL=http://localhost:8000 -e WS_URL=ws://localhost:8000 \
    scripts/load/websocket_live.js

# Analytics aggregation
k6 run -e BASE_URL=http://localhost:8000 scripts/load/analytics.js

# Spike test (10x burst + recovery)
k6 run -e BASE_URL=http://localhost:8000 scripts/load/spike.js
```

Inside docker compose (k6 + backend share the same docker network):

```bash
docker compose -f docker-compose.yml -f docker-compose.load.yml \
    run --rm k6 run /scripts/smoke.js
```

Or with the Makefile shortcuts:

```bash
make load-smoke      # smoke test against running stack
make load-read       # sustained 1000 RPS read load
make load-sessions   # full session lifecycle
make load-ws         # WebSocket scenario
make load-spike      # spike + recovery
make load-all        # runs every scenario in sequence (~10 min)
```

## SLO targets (defined in `common/config.js`)

| Endpoint class            | p50    | p95    | p99    |
|---------------------------|--------|--------|--------|
| Read API                  | 100 ms | 200 ms | 400 ms |
| Write API                 | 250 ms | 500 ms | 1000 ms |
| WS connect handshake      | -      | 100 ms | -      |
| Demo hand                 | -      | 1500 ms| 3000 ms |
| Max error rate (global)   | -      | -      | 0.1 %  |

Each scenario imports `SLO` from `common/config.js` and converts the
relevant slice into `options.thresholds` so a regression fails the
test rather than just printing a warning.

## How to interpret a failed run

k6 exits non-zero when any threshold is missed. The summary at the
end calls out which series tripped:

```
checks_succeeded.................: 99.85% [1297 of 1299]
http_req_duration{name:summary}..: avg=42.13ms  p(95)=187ms p(99)=412ms
       ✓ p(95)<200
       ✗ p(99)<400
```

When a threshold fails:

1. Open Grafana (`docker-compose.observability.yml`) and look at
   the "Four Golden Signals" dashboard for the same time window.
   The histogram + traffic + error rows correlate the failed
   threshold to a *cause*.
2. Check `pyholdem_engine_*` histograms - if the API regression
   was driven by engine internals (equity calc, hand duration),
   the engine histograms will show it first.
3. Re-run the failing scenario at lower load to confirm it's
   load-driven and not a permanent regression.

## Wiring into CI

`scripts/load/smoke.js` is the CI gate (see
`.github/workflows/ci.yml`). It runs the smoke scenario against an
ephemeral compose stack on every PR and blocks merges if the smoke
fails. The heavier scenarios are too expensive for per-PR CI; they
should run nightly or on demand via `workflow_dispatch`.

## Adding a new scenario

1. Create `scripts/load/<name>.js`.
2. Import `BASE_URL`, `REQUEST_NAMES`, and the `SLO` slice you need
   from `common/config.js`.
3. Define `options.scenarios` with an explicit executor.
4. Define `options.thresholds` so the scenario can fail.
5. Use `tagged()` / `get()` / `post()` from `common/helpers.js` so
   the route name shows up cleanly in the latency histogram.
6. Add a `make load-<name>` target if you want it in the Makefile.
