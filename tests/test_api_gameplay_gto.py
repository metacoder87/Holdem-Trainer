"""End-to-end GTO wiring smoke tests via the FastAPI test client.

These tests exercise the full path:

  1. POST /api/games/sessions creates a session with a chosen
     villain_style.
  2. The engine spins up the right villain class.
  3. A hand is played to completion.
  4. The final response carries decision_points annotated with the
     GTO advisor payload (or null on cache miss), plus a
     coach_notes.gto_summary if any decision had cache coverage.

We don't assert on the *content* of GTO advice since that depends on
the precomputed cache contents and the random villain hand bucket.
We assert on the *shape*: that the field exists on every hand and
that the optional villain_style param doesn't break unrelated flows.
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
from app.services import game_service  # noqa: E402


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
        return {"value": min_value if min_value is not None else 1}
    if kind == "yes_no":
        return {"value": False}
    return {"value": 1}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    game_service.SESSIONS.clear()
    return TestClient(app)


def _play_one_hand(client, session_id: str, max_steps: int = 30) -> dict:
    """Drive a hand to completion and return the terminal state."""
    state = client.post(f"/api/games/sessions/{session_id}/hand/start").json()
    steps = 0
    while state.get("status") != "hand_complete" and steps < max_steps:
        pending = state.get("pending_input")
        if pending:
            state = client.post(
                f"/api/games/sessions/{session_id}/hand/input",
                json=_payload_for_pending(pending),
            ).json()
        else:
            state = client.get(f"/api/games/sessions/{session_id}/hand").json()
        steps += 1
    return state


def test_create_session_accepts_villain_style_gto(client):
    response = client.post(
        "/api/games/sessions",
        json={
            "player_name": "GTOTester",
            "game_type": "cash",
            "limit_type": "no_limit",
            "small_blind": 5,
            "big_blind": 10,
            "opponents": 1,
            "villain_style": "gto",
        },
    )
    assert response.status_code == 200
    session = response.json()
    assert session["id"]
    # The villain_style should be persisted in the session config.
    config = session.get("config") or {}
    assert config.get("villain_style") == "gto"


def test_create_session_rejects_unknown_villain_style_gracefully(client):
    """Unknown values fall back to balanced rather than erroring."""
    response = client.post(
        "/api/games/sessions",
        json={
            "player_name": "Fallback",
            "game_type": "cash",
            "limit_type": "no_limit",
            "opponents": 1,
            "villain_style": "expert-mode-9000",
        },
    )
    assert response.status_code == 200


def test_gto_session_full_hand_has_gto_field_on_decisions(client):
    """The last_hand response should carry decision_points with a
    'gto' field (value may be null when not cached)."""
    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "GTOFullHand",
            "game_type": "cash",
            "limit_type": "no_limit",
            "small_blind": 5,
            "big_blind": 10,
            "opponents": 1,
            "villain_style": "gto",
        },
    )
    assert create.status_code == 200
    session_id = create.json()["id"]

    state = _play_one_hand(client, session_id)
    assert state["status"] == "hand_complete"
    last_hand = state.get("last_hand")
    assert last_hand is not None

    coach = last_hand.get("coach_notes") or {}
    # gto_summary is optional but the key must exist on the payload.
    assert "gto_summary" in coach

    # Every decision_point must carry a 'gto' field (None or dict).
    decisions = last_hand.get("decision_points") or []
    for d in decisions:
        assert "gto" in d
        gto = d["gto"]
        assert gto is None or isinstance(gto, dict)
        if isinstance(gto, dict):
            assert "gto_action" in gto
            assert "source" in gto
            assert gto["source"] == "cache"


def test_balanced_session_still_works(client):
    """villain_style default ('balanced') doesn't break the existing flow."""
    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "Balanced",
            "game_type": "cash",
            "limit_type": "no_limit",
            "small_blind": 5,
            "big_blind": 10,
            "opponents": 1,
        },
    )
    assert create.status_code == 200
    session_id = create.json()["id"]
    state = _play_one_hand(client, session_id)
    assert state["status"] == "hand_complete"
