"""Observability subsystem.

Implements the Four Golden Signals (SRE book, chapter 6) for the
FastAPI service:

  1. Latency  - histogram of request duration, by route + status
  2. Traffic  - counter of requests received, by route
  3. Errors   - counter of failed requests (>= 500 or unhandled exc), by route
  4. Saturation - gauges on engine internals (active_sessions,
                  ws_connections, session_thread_pool_depth)

Distributed tracing (spans) is deliberately deferred - we can layer
OpenTelemetry on top later without touching metrics code.

Quick-start::

    from app.observability import init_observability
    init_observability(app)  # in main.py, after CORS

That call:
  * registers a Starlette middleware that increments the 4 metrics
  * exposes ``/metrics`` in Prometheus exposition format
  * does *not* add latency to non-instrumented paths
"""

from app.observability.init import init_observability  # noqa: F401
from app.observability.metrics import (  # noqa: F401
    api_requests_total,
    api_request_duration_seconds,
    api_requests_in_flight,
    api_errors_total,
    sessions_active,
    ws_connections_active,
    engine_hand_duration_seconds,
    engine_equity_compute_duration_seconds,
)

__all__ = [
    "init_observability",
    "api_requests_total",
    "api_request_duration_seconds",
    "api_requests_in_flight",
    "api_errors_total",
    "sessions_active",
    "ws_connections_active",
    "engine_hand_duration_seconds",
    "engine_equity_compute_duration_seconds",
]
