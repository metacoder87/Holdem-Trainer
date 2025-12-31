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


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    game_service.SESSIONS.clear()
    return TestClient(app)


def _choose_menu_option(options):
    for index, option in enumerate(options, start=1):
        label = option.lower()
        if "check" in label or "call" in label:
            return index
    return 1


def _payload_for_pending(pending):
    kind = pending.get("kind")
    if kind == "menu":
        options = pending.get("options") or []
        return {"choice": _choose_menu_option(options)}
    if kind == "number":
        min_value = pending.get("min_value")
        value = min_value if min_value is not None else 1
        return {"value": value}
    if kind == "yes_no":
        return {"value": False}
    return {"value": 1}


def test_gameplay_flow_cash_session(client):
    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "TestUser",
            "game_type": "cash",
            "limit_type": "no_limit",
            "small_blind": 5,
            "big_blind": 10,
            "opponents": 1,
        },
    )
    assert create.status_code == 200
    session_id = create.json()["id"]

    start = client.post(f"/api/games/sessions/{session_id}/hand/start")
    assert start.status_code == 200
    state = start.json()

    steps = 0
    while state["status"] != "hand_complete" and steps < 30:
        pending = state.get("pending_input")
        if not pending:
            state = client.get(f"/api/games/sessions/{session_id}/hand").json()
            steps += 1
            continue
        payload = _payload_for_pending(pending)
        response = client.post(f"/api/games/sessions/{session_id}/hand/input", json=payload)
        assert response.status_code == 200
        state = response.json()
        steps += 1

    assert state["status"] == "hand_complete"
    assert state["last_hand"] is not None
    assert state["state"]["hero_cards"]


def test_hand_state_requires_session(client):
    response = client.get("/api/games/sessions/does-not-exist/hand")
    assert response.status_code == 404


def test_submit_requires_pending_input(client):
    create = client.post(
        "/api/games/sessions",
        json={"player_name": "InputWait", "game_type": "cash", "limit_type": "no_limit", "opponents": 1},
    )
    session_id = create.json()["id"]

    response = client.post(f"/api/games/sessions/{session_id}/hand/input", json={"choice": 1})
    assert response.status_code == 409


def test_invalid_menu_choice_rejected(client):
    create = client.post(
        "/api/games/sessions",
        json={"player_name": "BadChoice", "game_type": "cash", "limit_type": "no_limit", "opponents": 1},
    )
    session_id = create.json()["id"]

    state = client.post(f"/api/games/sessions/{session_id}/hand/start").json()
    if not state.get("pending_input"):
        state = client.get(f"/api/games/sessions/{session_id}/hand").json()

    pending = state.get("pending_input")
    assert pending is not None

    max_value = int(pending.get("max_value") or 1)
    response = client.post(
        f"/api/games/sessions/{session_id}/hand/input",
        json={"choice": max_value + 5},
    )
    assert response.status_code == 400


def test_tournament_buy_in_validation(client):
    response = client.post(
        "/api/games/sessions",
        json={
            "player_name": "ShortStack",
            "game_type": "tournament",
            "limit_type": "no_limit",
            "buy_in": 20000,
            "starting_chips": 20000,
            "opponents": 2,
        },
    )
    assert response.status_code == 400
