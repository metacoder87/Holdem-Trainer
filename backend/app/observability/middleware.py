"""Starlette middleware that records the Four Golden Signals.

Labels use the matched route template (e.g. ``/api/games/sessions/{session_id}``)
rather than the raw path so cardinality is bounded.
"""
from __future__ import annotations

import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match
from starlette.types import ASGIApp

from app.observability.metrics import (
    api_errors_total,
    api_request_duration_seconds,
    api_requests_in_flight,
    api_requests_total,
)


def _match_route(request: Request) -> str:
    """Resolve the matched route template, or fall back to the raw path."""
    for route in request.app.routes:
        match, _scope = route.matches(request.scope)
        if match == Match.FULL:
            path = getattr(route, "path", None)
            if path:
                return path
    # Unknown route (404 from a path that didn't match anything).
    return request.url.path


def _status_class(status_code: int) -> str:
    return f"{status_code // 100}xx"


class GoldenSignalsMiddleware(BaseHTTPMiddleware):
    """Records latency, traffic, errors, and in-flight requests."""

    async def dispatch(self, request: Request, call_next):
        # Skip the metrics endpoint itself to avoid weird recursion in
        # the histogram (every scrape would add to traffic counters).
        if request.url.path in ("/metrics", "/health"):
            return await call_next(request)

        method = request.method
        route = _match_route(request)
        api_requests_in_flight.labels(route=route).inc()
        start = time.perf_counter()
        status_code: Optional[int] = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            api_errors_total.labels(
                method=method, route=route, kind="exception"
            ).inc()
            raise
        finally:
            duration = time.perf_counter() - start
            sc = status_code or 500
            api_requests_total.labels(
                method=method, route=route, status=str(sc)
            ).inc()
            api_request_duration_seconds.labels(
                method=method, route=route, status_class=_status_class(sc)
            ).observe(duration)
            if sc >= 500:
                api_errors_total.labels(
                    method=method, route=route, kind="5xx"
                ).inc()
            elif sc >= 400:
                api_errors_total.labels(
                    method=method, route=route, kind="4xx"
                ).inc()
            api_requests_in_flight.labels(route=route).dec()
