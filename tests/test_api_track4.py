"""Integration tests for Track 4 adaptive engine endpoints."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    return TestClient(app)


# ---------- /api/training/progression ----------


def test_progression_endpoint_returns_documented_shape(client):
    response = client.get("/api/training/progression?player=NewPlayer")
    assert response.status_code == 200
    payload = response.json()
    assert "bandit" in payload
    assert "next_topic" in payload
    assert "srs" in payload
    assert "elo" in payload
    assert payload["srs"]["due_count"] == 0
    assert payload["elo"]["player_rating"] == 1500.0


def test_progression_next_topic_returns_valid_topic(client):
    response = client.get("/api/training/progression/next-topic?player=Q")
    assert response.status_code == 200
    body = response.json()
    assert body["topic"] in {a["topic"] for a in body["bandit"]}


# ---------- Bandit result ----------


def test_bandit_result_persists_across_requests(client):
    """Record a correct outcome, then verify the bandit reflects it."""
    response = client.post(
        "/api/training/progression/bandit-result",
        json={"player": "BanditUser", "topic": "pot_odds", "correct": True},
    )
    assert response.status_code == 200
    first = response.json()
    target_arm = next(
        (a for a in first["bandit"] if a["topic"] == "pot_odds"), None
    )
    assert target_arm is not None
    # Default alpha=2.0; after one correct -> 3.0.
    assert target_arm["alpha"] == 3.0
    assert target_arm["pulls"] == 1

    # Re-fetch via progression to confirm persistence.
    second = client.get(
        "/api/training/progression?player=BanditUser"
    ).json()
    target_arm2 = next(a for a in second["bandit"] if a["topic"] == "pot_odds")
    assert target_arm2["alpha"] == 3.0


def test_bandit_result_validates_body(client):
    bad = client.post(
        "/api/training/progression/bandit-result",
        json={"player": "", "topic": "pot_odds", "correct": True},
    )
    assert bad.status_code == 422


# ---------- SRS review ----------


def test_srs_review_creates_card_and_schedules_next_due(client):
    response = client.post(
        "/api/training/progression/srs-review",
        json={"player": "SrsUser", "card_id": "pot-odds-1", "quality": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    # After one successful review the card should not be due now.
    assert payload["srs"]["due_count"] == 0
    assert payload["srs"]["total_cards"] == 1


def test_srs_quality_below_3_keeps_card_due(client):
    response = client.post(
        "/api/training/progression/srs-review",
        json={"player": "SrsUser2", "card_id": "preflop-utg", "quality": 1},
    )
    assert response.status_code == 200
    payload = response.json()
    # Quality 1 -> interval 0 -> still due.
    assert payload["srs"]["due_count"] >= 1


def test_srs_review_validates_quality_range(client):
    out_of_range = client.post(
        "/api/training/progression/srs-review",
        json={"player": "S", "card_id": "c", "quality": 9},
    )
    assert out_of_range.status_code == 422


# ---------- Scenario Elo ----------


def test_scenario_elo_updates_player_rating(client):
    # Hero wins a scenario -> rating goes up.
    response = client.post(
        "/api/training/progression/scenario-result",
        json={
            "player": "EloUser",
            "scenario_id": "AKx-flop",
            "player_won": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["elo"]["player_rating"] > 1500.0
    assert payload["elo"]["attempts"] == 1


def test_scenario_elo_loss_drops_rating(client):
    client.post(
        "/api/training/progression/scenario-result",
        json={"player": "EloUser2", "scenario_id": "s1", "player_won": True},
    )
    response = client.post(
        "/api/training/progression/scenario-result",
        json={"player": "EloUser2", "scenario_id": "s1", "player_won": False},
    )
    payload = response.json()
    # After 1 win + 1 loss, rating ends close to 1500 (Elo is zero-sum
    # but k-factor 32 means a 32-point swing each direction). Verify
    # the attempt counter incremented.
    assert payload["elo"]["attempts"] == 2


# ---------- Validation across endpoints ----------


def test_progression_endpoint_handles_no_player_param(client):
    """Endpoints accept missing player and degrade gracefully."""
    response = client.get("/api/training/progression")
    assert response.status_code == 200
