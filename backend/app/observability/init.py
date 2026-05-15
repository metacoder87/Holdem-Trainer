"""One-call initializer wiring middleware + /metrics route + gauge sync.

Why a function call instead of module-side effects: the test suite
creates the FastAPI app multiple times (different env vars). Calling
``init_observability`` explicitly per app keeps metric state clean.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.observability.metrics import REGISTRY, sessions_active, ws_connections_active
from app.observability.middleware import GoldenSignalsMiddleware

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import FastAPI


def _is_enabled() -> bool:
    """Allow env-driven opt-out, in case ops want to disable in prod."""
    flag = os.getenv("PYHOLDEM_METRICS_ENABLED", "1").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def _refresh_saturation_gauges() -> None:
    """Pull current saturation state from the live game-service store.

    Called from inside the /metrics handler so each scrape sees a
    fresh value instead of stale-since-last-state-change.
    """
    try:
        from app.services import game_service  # local import: avoids cycle

        with game_service.SESSIONS_LOCK:
            sessions_active.set(len(game_service.SESSIONS))
    except Exception:
        # Don't let metrics break /metrics. Gauges just stay at last value.
        pass


def init_observability(app: "FastAPI") -> None:
    """Attach the middleware and the /metrics endpoint to ``app``."""
    if not _is_enabled():
        return

    app.add_middleware(GoldenSignalsMiddleware)

    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint() -> Response:
        _refresh_saturation_gauges()
        payload = generate_latest(REGISTRY)
        return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
