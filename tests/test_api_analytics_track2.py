"""Integration tests for Track 2 Bayesian analytics endpoints.

These tests hit the FastAPI app via TestClient and verify the
end-to-end shape of /api/analytics/variance, /api/analytics/icm,
/api/analytics/icm/spot, and the extended /api/charts/{metric}.

Backend-only - the frontend wires them in Analytics.tsx and the
component tests in src/pages/Analytics.test.tsx cover that side.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    return TestClient(app)


# ---------- /api/analytics/variance ----------


def test_variance_endpoint_returns_empty_for_no_player(client):
    response = client.get("/api/analytics/variance")
    assert response.status_code == 200
    payload = response.json()
    assert "winrate" in payload
    assert "rolling_bb100" in payload
    assert "ev_adjusted_lines" in payload
    assert "all_in_luck" in payload
    assert payload["session_count"] == 0


def test_variance_endpoint_accepts_bankroll_param(client):
    response = client.get("/api/analytics/variance?bankroll_bbs=2000")
    assert response.status_code == 200
    # Even with no sessions the field must exist with bankroll provided.
    assert "winrate" in response.json()


def test_variance_endpoint_rejects_negative_bankroll(client):
    response = client.get("/api/analytics/variance?bankroll_bbs=-50")
    assert response.status_code == 422


# ---------- /api/analytics/icm/spot ----------


def test_icm_spot_returns_equities_summing_to_prize(client):
    response = client.post(
        "/api/analytics/icm/spot",
        json={
            "stacks": [5000, 3000, 2000],
            "payouts": [600, 300, 100],
            "hero_index": 0,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["icm"] is not None
    equities = payload["icm"]["equities"]
    assert len(equities) == 3
    assert abs(sum(equities) - 1000.0) < 1e-6


def test_icm_spot_chip_leader_underpaid(client):
    response = client.post(
        "/api/analytics/icm/spot",
        json={
            "stacks": [5000, 2500, 2500],
            "payouts": [500, 300, 200],
        },
    )
    payload = response.json()
    icm = payload["icm"]
    # Chip leader (seat 0) ICM equity < chip share (classic result).
    assert icm["equities"][0] < icm["chip_shares"][0]


def test_icm_spot_validates_stacks_length(client):
    response = client.post(
        "/api/analytics/icm/spot",
        json={"stacks": [5000], "payouts": [500]},
    )
    # Pydantic rejects single-stack arrays (min_length=2).
    assert response.status_code == 422


def test_icm_spot_validates_hero_index(client):
    response = client.post(
        "/api/analytics/icm/spot",
        json={
            "stacks": [5000, 3000],
            "payouts": [500],
            "hero_index": 5,
        },
    )
    assert response.status_code == 400


def test_icm_spot_validates_payouts_dont_exceed_stacks(client):
    """The malmuth_harville helper rejects more payouts than players;
    the service wraps that into an error response with note."""
    response = client.post(
        "/api/analytics/icm/spot",
        json={
            "stacks": [5000, 3000],
            "payouts": [500, 300, 200],
        },
    )
    # The endpoint hits the icm_calculator's ValueError, which the
    # service swallows into a payload with error field.
    payload = response.json()
    assert payload.get("error") or payload.get("icm") is None


# ---------- /api/analytics/icm (player mode) ----------


def test_icm_player_mode_returns_placeholder_for_unknown_player(client):
    response = client.get("/api/analytics/icm?player=Nobody")
    assert response.status_code == 200
    payload = response.json()
    assert payload["icm"] is None
    assert "note" in payload


# ---------- /api/charts extended ----------


def test_charts_supports_window_param(client):
    response = client.get("/api/charts/vpip?player=Nobody&window=5")
    assert response.status_code == 200
    # No sessions -> empty list. The schema must still parse the params.
    assert response.json() == []


def test_charts_supports_include_adjusted_param(client):
    response = client.get(
        "/api/charts/profit?player=Nobody&include_adjusted=true"
    )
    assert response.status_code == 200
    assert response.json() == []


def test_charts_rejects_invalid_window(client):
    response = client.get("/api/charts/vpip?player=Nobody&window=0")
    assert response.status_code == 422


def test_charts_endpoint_under_analytics_route_also_works(client):
    response = client.get(
        "/api/analytics/chart?player=Nobody&metric=vpip&window=3"
    )
    assert response.status_code == 200
    assert response.json() == []


# ---------- /api/summary/report includes Bayesian CI fields ----------


def test_summary_report_returns_ci_fields_when_player_present(client):
    """Create a player via summary's implicit fallback path, then
    request the analytics report. Bayesian CI fields must be in the
    playing_style block."""
    # Hit summary first to ensure the data file is set up; the route
    # returns Guest defaults when no players exist, which is fine for
    # this assertion.
    response = client.get("/api/summary/report?player=Guest")
    assert response.status_code == 200
    payload = response.json()
    style = payload.get("playing_style") or {}
    # The Bayesian fields should always be present on the response,
    # even with zero data (they degrade to {value: 0.5, ci: [0,1], ...}).
    assert "vpip_ci" in style
    assert "pfr_ci" in style
    assert "aggression_factor_ci" in style
    # CI shape integrity.
    assert {"value", "ci_lower", "ci_upper", "sample_size", "small_sample"} <= set(
        style["vpip_ci"].keys()
    )
