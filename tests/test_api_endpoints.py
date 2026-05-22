import sys
from concurrent.futures import ThreadPoolExecutor
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
    assert payload["focus_queue_items"][0]["id"] == "poor_position_play"


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
    assert "quiz_id" in payload
    assert "correct_answer" not in payload

    evaluate = client.post(
        "/api/training/quiz/evaluate",
        json={"quiz_id": payload["quiz_id"], "player": payload["player"], "user_answer": 19},
    )
    assert evaluate.status_code == 200
    assert evaluate.json()["correct"] is True
    assert "explanation" in evaluate.json()


def test_training_drill_endpoint(client):
    response = client.get("/api/training/drill?player=Guest&focus=poor_pot_odds")
    assert response.status_code == 200
    payload = response.json()
    assert payload["focus_area"] == "poor_pot_odds"
    assert "scenario" in payload
    assert "quiz" in payload
    assert "drill_id" in payload
    assert "correct_answer" not in payload["quiz"]
    assert "open-ended straight draw" in payload["quiz"]["question"]
    assert str(payload["scenario"]["pot_size"]) in payload["quiz"]["question"]
    assert str(payload["scenario"]["bet_to_call"]) in payload["quiz"]["question"]

    result = client.post(
        "/api/training/drill/evaluate",
        json={"drill_id": payload["drill_id"], "player": payload["player"], "user_answer": "fold"},
    )
    assert result.status_code == 200
    assert result.json()["correct"] is True
    assert "straight draw" in result.json()["explanation"] or "outs" in result.json()["explanation"]


def test_training_drill_payload_uses_coherent_scenario_values(client):
    response = client.get("/api/training/drill?player=ScenarioUser&focus=poor_pot_odds")

    assert response.status_code == 200
    payload = response.json()
    scenario = payload["scenario"]
    quiz = payload["quiz"]
    assert "pot" not in quiz
    assert "bet" not in quiz
    assert f"${scenario['pot_size']}" in quiz["question"]
    assert f"${scenario['bet_to_call']}" in quiz["question"]
    assert str(scenario["outs"]) in quiz["question"]


def test_concurrent_training_drill_requests_do_not_lose_json_progress(client, tmp_path, monkeypatch):
    data_file = tmp_path / "players.json"
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(data_file))
    attempts = 12

    def request_drill(index: int) -> str:
        response = client.get(
            f"/api/training/drill?player=ConcurrentUser&focus=poor_pot_odds&n={index}"
        )
        assert response.status_code == 200, response.text
        return response.json()["drill_id"]

    with ThreadPoolExecutor(max_workers=attempts) as executor:
        drill_ids = list(executor.map(request_drill, range(attempts)))

    assert len(set(drill_ids)) == attempts
    record = DataManager(data_file=str(data_file)).get_player("ConcurrentUser")
    pending = record["training_progress"]["pending_drills"]
    assert set(drill_ids).issubset(set(pending))


def test_training_progress_endpoint(client):
    response = client.get("/api/training/progress?player=Guest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["player"] == "Guest"
    assert "quiz_stats" in payload


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


def test_hand_detail_disambiguates_duplicate_hand_numbers_by_session(client, tmp_path, monkeypatch):
    data_file = tmp_path / "players.json"
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(data_file))
    manager = DataManager(data_file=str(data_file))
    manager.create_player("ReplayUser", 5000)
    manager.append_hand_history(
        "ReplayUser",
        {
            "session_id": "old-session",
            "hand_number": 1,
            "hero_hole_cards": ["Ah", "Kd"],
            "pot_total": 100,
            "winners": ["ReplayUser"],
        },
    )
    manager.append_hand_history(
        "ReplayUser",
        {
            "session_id": "new-session",
            "hand_number": 1,
            "hero_hole_cards": ["2h", "2d"],
            "pot_total": 250,
            "winners": ["Villain"],
        },
    )

    unqualified = client.get("/api/hands/ReplayUser/1")
    assert unqualified.status_code == 200
    assert unqualified.json()["session_id"] == "new-session"

    qualified = client.get("/api/hands/ReplayUser/1?session_id=old-session")
    assert qualified.status_code == 200
    assert qualified.json()["session_id"] == "old-session"


def test_summary_timeline_uses_saved_hand_history_when_recent_hands_empty(client, tmp_path, monkeypatch):
    data_file = tmp_path / "players.json"
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(data_file))
    manager = DataManager(data_file=str(data_file))
    manager.create_player("TimelineUser", 5000)
    manager.save_players()
    manager.append_hand_history(
        "TimelineUser",
        {
            "hand_number": 7,
            "started_at": "2026-05-14T18:30:00",
            "pot_total": 240,
            "winners": ["TimelineUser"],
            "meta": {"hero_won": True, "pot_total": 240},
        },
    )

    response = client.get("/api/summary?player=TimelineUser")

    assert response.status_code == 200
    payload = response.json()
    assert payload["timeline"][0]["label"] == "Hand 7"
    assert "Won pot" in payload["timeline"][0]["detail"]
