"""Tests for the Four Golden Signals middleware + /metrics endpoint."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = ROOT / "backend"
SRC_PATH = ROOT / "src"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    monkeypatch.setenv("PYHOLDEM_METRICS_ENABLED", "1")
    return TestClient(app)


def test_metrics_endpoint_exposes_prometheus_format(client):
    """Plain hit to /metrics returns the Prometheus exposition format."""
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    # Prometheus format starts with "# HELP" comments for each series.
    assert "# HELP" in body
    # The Four Golden Signals are pre-declared, so they show up even
    # before any traffic has been seen.
    assert "pyholdem_api_requests_total" in body
    assert "pyholdem_api_request_duration_seconds" in body
    assert "pyholdem_api_errors_total" in body
    assert "pyholdem_sessions_active" in body


def test_traffic_counter_increments_on_request(client):
    """Hitting an instrumented route should bump the requests counter."""
    # /metrics + /health are excluded from instrumentation (so the
    # counters aren't polluted by scrapes), so use /api/bankroll/players.
    client.get("/api/bankroll/players")
    client.get("/api/bankroll/players")

    metrics = client.get("/metrics").text
    # The counter is exported per (method, route, status). Look for any
    # 200-status row matching the route template (FastAPI template
    # form is /api/bankroll/players).
    assert "pyholdem_api_requests_total" in metrics
    assert '/api/bankroll/players' in metrics


def test_latency_histogram_records_durations(client):
    """The latency histogram should have at least one observation."""
    client.get("/api/bankroll/players")
    metrics = client.get("/metrics").text
    # Histograms expose `_bucket`, `_sum`, `_count` series.
    assert "pyholdem_api_request_duration_seconds_count" in metrics
    assert "pyholdem_api_request_duration_seconds_bucket" in metrics


def test_errors_counter_increments_on_404(client):
    """404 routes (4xx) should bump the errors{kind=4xx} counter."""
    client.get("/api/players/nonexistent-user-id")  # known 404 path

    metrics = client.get("/metrics").text
    assert 'kind="4xx"' in metrics
    assert "pyholdem_api_errors_total" in metrics


def test_metrics_route_excluded_from_instrumentation(client):
    """Scraping /metrics shouldn't add itself to the counters."""
    # Hit /metrics a few times.
    before = client.get("/metrics").text
    client.get("/metrics")
    client.get("/metrics")
    after = client.get("/metrics").text
    # The /metrics URL must NOT appear as a label value in the
    # requests counter (would be infinite recursion of self-instrumented).
    assert 'route="/metrics"' not in after
    # Histogram total count for /metrics route should also be absent.
    assert '"/metrics"' not in after.split("pyholdem_api_requests_total")[1].split(
        "\n#"
    )[0] if "pyholdem_api_requests_total" in after else True


def test_metrics_disabled_via_env(monkeypatch, tmp_path):
    """PYHOLDEM_METRICS_ENABLED=0 should turn the system off."""
    monkeypatch.setenv("PYHOLDEM_METRICS_ENABLED", "0")
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    # Build a fresh app so init_observability sees the env var.
    from fastapi import FastAPI

    from app.observability.init import init_observability

    test_app = FastAPI()
    init_observability(test_app)
    test_client = TestClient(test_app)
    # /metrics shouldn't exist when disabled.
    resp = test_client.get("/metrics")
    assert resp.status_code == 404
