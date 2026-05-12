import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.main import app  # noqa: E402
from app.services import game_service  # noqa: E402
from data.manager import DataManager  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    data_file = tmp_path / "players.json"
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(data_file))
    game_service.SESSIONS.clear()
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_summary_defaults_without_players(client):
    response = client.get("/api/summary")
    assert response.status_code == 200
    payload = response.json()
    assert "player" in payload
    assert "live_metrics" in payload


def test_bankroll_create_list_update_flow(client):
    create = client.post("/api/bankroll/players", json={"name": "BankrollUser", "bankroll": 15000})
    assert create.status_code == 200
    assert create.json()["bankroll"] == 15000

    listing = client.get("/api/bankroll/players")
    assert listing.status_code == 200
    assert any(player["name"] == "BankrollUser" for player in listing.json())

    update = client.patch("/api/bankroll/players/BankrollUser", json={"bankroll": 12000})
    assert update.status_code == 200
    assert update.json()["bankroll"] == 12000

    summary = client.get("/api/bankroll/summary")
    assert summary.status_code == 200
    assert summary.json()["total_players"] == 1


def test_training_quiz_and_evaluation(client):
    quiz = client.get("/api/training/quiz?quiz_type=pot_odds")
    assert quiz.status_code == 200
    payload = quiz.json()
    assert "question" in payload
    assert "correct_answer" in payload

    evaluate = client.post(
        "/api/training/quiz/evaluate",
        json={"correct_answer": payload["correct_answer"], "user_answer": payload["correct_answer"]},
    )
    assert evaluate.status_code == 200
    assert evaluate.json()["correct"] is True


def test_training_drill_endpoint(client):
    response = client.get("/api/training/drill?player=Guest&focus=poor_pot_odds")
    assert response.status_code == 200
    payload = response.json()
    assert payload["focus_area"] == "poor_pot_odds"
    assert "scenario" in payload
    assert "quiz" in payload


def test_chart_data_uses_recorded_sessions_only(client):
    response = client.get("/api/charts/vpip?player=UnknownUser")
    assert response.status_code == 200
    assert response.json() == []


def test_players_endpoints(client):
    missing = client.get("/api/players/UnknownUser")
    assert missing.status_code == 404

    client.post("/api/bankroll/players", json={"name": "RosterUser", "bankroll": 8000})
    roster = client.get("/api/players")
    assert roster.status_code == 200
    assert any(player["name"] == "RosterUser" for player in roster.json())

    detail = client.get("/api/players/RosterUser")
    assert detail.status_code == 200
    assert detail.json()["name"] == "RosterUser"


def test_hand_history_endpoints(client, tmp_path, monkeypatch):
    data_file = tmp_path / "players.json"
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(data_file))
    manager = DataManager(data_file=str(data_file))
    manager.create_player("HistoryUser", 5000)
    manager.save_players()
    manager.append_hand_history(
        "HistoryUser",
        {
            "hand_number": 1,
            "hero_hole_cards": ["Ah", "Kd"],
            "board": ["2c", "7d", "Ts"],
            "pot_total": 120,
            "winners": ["HistoryUser"],
        },
    )
    manager.append_hand_history(
        "HistoryUser",
        {
            "hand_number": 2,
            "hero_hole_cards": ["2h", "2d"],
            "board": ["2c", "7d", "Ts"],
            "pot_total": 40,
            "winners": ["Villain"],
        },
    )

    listing = client.get("/api/hands?player=HistoryUser&limit=5")
    assert listing.status_code == 200
    assert len(listing.json()) == 2

    detail = client.get("/api/hands/HistoryUser/1")
    assert detail.status_code == 200
    assert detail.json()["hand_number"] == 1

    filtered = client.get("/api/hands/filter?player=HistoryUser&winner=hero&min_pot=100")
    assert filtered.status_code == 200
    assert [hand["hand_number"] for hand in filtered.json()] == [1]
