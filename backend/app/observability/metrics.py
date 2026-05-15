"""Prometheus metric singletons (Four Golden Signals + saturation).

We pre-declare everything in a single module so:

  1. Metric names + labels + histogram buckets are reviewable in one place.
  2. There's a single ``REGISTRY`` we can pass to the /metrics handler.
  3. Cardinality is bounded - we never label by user-controlled strings
     (no `player_name`, no raw paths with IDs). Routes use the matched
     route template (``/api/games/sessions/{session_id}``) so IDs don't
     blow up cardinality.

Histogram buckets are tuned for a Python+SQLAlchemy stack with
realistic targets:

  - API: 5 ms .. 5 s (covers cache-hit reads through worst-case writes)
  - Hand: 10 ms .. 60 s (an interactive hand can pause for a human input)
  - Equity: 1 ms .. 5 s (Monte Carlo equity at 1000 trials)
"""
from __future__ import annotations

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
)

# Single, app-scoped registry. Using the default global REGISTRY plays
# poorly with tests (re-import causes "Duplicated timeseries" errors).
REGISTRY = CollectorRegistry()

# Common buckets per metric kind.
API_LATENCY_BUCKETS = (
    0.005, 0.01, 0.025, 0.05, 0.075,
    0.1, 0.25, 0.5, 0.75,
    1.0, 2.5, 5.0,
)

HAND_DURATION_BUCKETS = (
    0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0,
)

EQUITY_BUCKETS = (
    0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0,
)


# ---------------------------------------------------------------------
# 1. Latency  - per-route request duration histogram
# ---------------------------------------------------------------------

api_request_duration_seconds = Histogram(
    "pyholdem_api_request_duration_seconds",
    "HTTP request duration by route + method + status class.",
    ["method", "route", "status_class"],
    buckets=API_LATENCY_BUCKETS,
    registry=REGISTRY,
)


# ---------------------------------------------------------------------
# 2. Traffic  - request rate (counter; rate() in PromQL)
# ---------------------------------------------------------------------

api_requests_total = Counter(
    "pyholdem_api_requests_total",
    "Total HTTP requests by route + method + status code.",
    ["method", "route", "status"],
    registry=REGISTRY,
)


# ---------------------------------------------------------------------
# 3. Errors  - failed-request counter
# ---------------------------------------------------------------------

api_errors_total = Counter(
    "pyholdem_api_errors_total",
    "HTTP requests that returned >= 500 or raised an unhandled exception.",
    ["method", "route", "kind"],  # kind: 5xx, 4xx, exception
    registry=REGISTRY,
)


# ---------------------------------------------------------------------
# 4. Saturation  - gauges + in-flight counter
# ---------------------------------------------------------------------

api_requests_in_flight = Gauge(
    "pyholdem_api_requests_in_flight",
    "HTTP requests currently being processed.",
    ["route"],
    registry=REGISTRY,
)

sessions_active = Gauge(
    "pyholdem_sessions_active",
    "Number of LiveSessions currently held in memory.",
    registry=REGISTRY,
)

ws_connections_active = Gauge(
    "pyholdem_ws_connections_active",
    "Open WebSocket connections to /ws/sessions/{id}.",
    registry=REGISTRY,
)


# ---------------------------------------------------------------------
# Engine-internal histograms (custom-instrumented hot paths)
# ---------------------------------------------------------------------

engine_hand_duration_seconds = Histogram(
    "pyholdem_engine_hand_duration_seconds",
    "Wall-clock duration of GameEngine.play_hand().",
    ["game_type"],  # cash, tournament
    buckets=HAND_DURATION_BUCKETS,
    registry=REGISTRY,
)

engine_equity_compute_duration_seconds = Histogram(
    "pyholdem_engine_equity_compute_duration_seconds",
    "Wall-clock duration of one EquityCalculator.calculate_*_equity call.",
    ["mode"],  # heads_up, multiway
    buckets=EQUITY_BUCKETS,
    registry=REGISTRY,
)


# ---------------------------------------------------------------------
# Optional counters useful for product analytics
# ---------------------------------------------------------------------

hands_played_total = Counter(
    "pyholdem_hands_played_total",
    "Hands played to completion.",
    ["game_type"],
    registry=REGISTRY,
)

training_attempts_total = Counter(
    "pyholdem_training_attempts_total",
    "Quiz / drill attempts evaluated.",
    ["kind", "correct"],  # kind in {quiz, drill}, correct in {true, false}
    registry=REGISTRY,
)
