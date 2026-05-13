"""Tests for coach notes (3.4/4.4) and career analytics (1.7/3.3)."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
BACKEND_PATH = ROOT / "backend"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.main import app
from app.services import game_service
from data.manager import DataManager


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    game_service.SESSIONS.clear()
    return TestClient(app)


# -------- Coach notes (3.4 / 4.4) --------------------------------------------


def test_coach_notes_present_after_hand_completes(client):
    """A completed hand should ship a coach_notes payload on last_hand."""
    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "CoachUser",
            "game_type": "cash",
            "limit_type": "no_limit",
            "small_blind": 5,
            "big_blind": 10,
            "opponents": 1,
        },
    )
    session_id = create.json()["id"]
    state = client.post(f"/api/games/sessions/{session_id}/hand/start").json()

    # Always pick "All-In" so the hand resolves in one step.
    while state["status"] == "awaiting_input":
        pending = state["pending_input"]
        options = pending.get("options") or []
        idx = next(
            (i for i, opt in enumerate(options, 1) if "all-in" in opt.lower()),
            1,
        )
        state = client.post(
            f"/api/games/sessions/{session_id}/hand/input", json={"choice": idx}
        ).json()

    assert state["status"] == "hand_complete"
    last_hand = state.get("last_hand") or {}
    coach = last_hand.get("coach_notes")
    assert coach is not None, "Coach notes should be present after any completed hand"
    assert "headline" in coach
    assert "hand_grade" in coach
    assert "hero_won" in coach


# -------- Career analytics (1.7 / 3.3) ---------------------------------------


def test_career_endpoint_empty_when_no_player(client):
    response = client.get("/api/analytics/career").json()
    assert response["session_count"] == 0
    assert response["career_metrics"] is None


def test_career_endpoint_aggregates_sessions_and_milestones(client, tmp_path):
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("CareerUser", 10000)
    # Two sessions, one positive, one negative, > 100 hands total -> hits the
    # `100_hands` milestone.
    manager.update_player_stats(
        "CareerUser",
        {
            "sessions": [
                {
                    "hands_played": 60,
                    "vpip": 0.24,
                    "pfr": 0.18,
                    "aggression_factor": 2.0,
                    "profit": 250,
                    "winrate": 0.4,
                },
                {
                    "hands_played": 50,
                    "vpip": 0.22,
                    "pfr": 0.17,
                    "aggression_factor": 2.5,
                    "profit": -150,
                    "winrate": 0.3,
                },
            ]
        },
    )
    manager.save_players()

    response = client.get("/api/analytics/career?player=CareerUser").json()
    assert response["session_count"] == 2
    metrics = response["career_metrics"]
    assert metrics["total_hands"] == 110
    assert metrics["total_profit"] == 100
    assert metrics["best_session_profit"] == 250
    assert metrics["worst_session_profit"] == -150
    milestone_types = {m["type"] for m in response["milestones"]}
    assert "100_hands" in milestone_types
