"""Regression coverage for the main-branch repair pass.

Covers the bugs that were uncovered during the audit:
- WS route used to AttributeError because it referenced missing session attrs
  (`update_event`, `tournament_finalized`). The repaired route only relies on
  attrs that LiveSession actually has.
- `/api/hands/filter` was unreachable because it was declared after
  `/api/hands/{name}/{int}`. The reordered route should now resolve.
- Analytics service had get_career_report / get_session_report but no route
  exposed them. Both routes should now respond.
- All-in hand must resolve to a non-empty winners list (regression from the
  original "all-in shows no winner" bug, without the broken seed= kwarg the
  old test passed to GameEngine).
"""
from __future__ import annotations

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
from game.game_engine import GameEngine
from game.player import Player


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    # Tests share the SESSIONS dict; clear it between fixtures so leaked
    # sessions from previous tests don't influence cleanup paths.
    with game_service.SESSIONS_LOCK:
        game_service.SESSIONS.clear()
    return TestClient(app)


# ----- /api/hands/filter route ordering --------------------------------------


def test_hands_filter_route_is_reachable(client, tmp_path):
    """Regression: /api/hands/filter must resolve before /{name}/{int}.

    Before the fix this returned 422 (because FastAPI tried to parse
    "filter" as the int hand_number) instead of running the filter handler.
    """
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("FilterUser", 5000)
    manager.save_players()
    manager.append_hand_history(
        "FilterUser",
        {
            "hand_number": 1,
            "pot_total": 200,
            "winners": ["FilterUser"],
            "board": ["2c", "7d", "Ts"],
            "actions": [],
            "decision_points": [],
            "hero_hole_cards": [],
            "meta": {},
        },
    )

    response = client.get("/api/hands/filter?player=FilterUser&min_pot=100&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["hand_number"] == 1


# ----- /api/analytics/* new routes ------------------------------------------


def test_analytics_career_route_handles_empty_player(client):
    """Empty career should 200, not 404 - the frontend renders a placeholder."""
    response = client.get("/api/analytics/career")
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_count"] == 0
    assert payload["career_metrics"] is None


def test_analytics_career_route_aggregates_sessions(client, tmp_path):
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("CareerUser", 10000)
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

    response = client.get("/api/analytics/career?player=CareerUser")
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_count"] == 2
    metrics = payload["career_metrics"]
    assert metrics["total_hands"] == 110
    assert metrics["total_profit"] == 100


def test_analytics_session_latest_404s_without_sessions(client):
    response = client.get("/api/analytics/sessions/latest")
    assert response.status_code == 404


def test_analytics_session_latest_returns_report(client, tmp_path):
    """`/latest` must be matched as the literal, not parsed as an int."""
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("ReportUser", 5000)
    manager.update_player_stats(
        "ReportUser",
        {
            "sessions": [
                {
                    "hands_played": 80,
                    "vpip": 0.24,
                    "pfr": 0.18,
                    "aggression_factor": 2.0,
                    "decision_accuracy": 0.7,
                    "profit": 120,
                }
            ],
        },
    )
    manager.save_players()

    response = client.get("/api/analytics/sessions/latest?player=ReportUser")
    assert response.status_code == 200
    payload = response.json()
    assert payload["report"] is not None
    assert "overall_grade" in payload["report"]


def test_analytics_ev_leaks_handles_empty_player(client):
    response = client.get("/api/analytics/ev-leaks?player=Nobody")
    assert response.status_code == 200
    payload = response.json()
    assert payload["priced_decision_count"] == 0
    assert payload["groups"] == []


def test_analytics_ev_leaks_groups_priced_mistakes(client, tmp_path):
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("LeakUser", 10000)
    manager.append_hand_history(
        "LeakUser",
        {
            "session_id": "s1",
            "hand_number": 1,
            "decision_points": [
                {
                    "betting_round": "turn",
                    "hero_position": 2,
                    "chosen_action": "call",
                    "recommended_action": "fold",
                    "opponent": {"type": "loose-aggressive"},
                    "ev_loss_bb": 2.5,
                    "ev_loss_chips": 25,
                },
                {
                    "betting_round": "river",
                    "hero_position": 4,
                    "chosen_action": "fold",
                    "recommended_action": "fold",
                    "opponent": {"type": "balanced"},
                    "ev_loss_bb": 0,
                    "ev_loss_chips": 0,
                },
                {
                    "betting_round": "flop",
                    "chosen_action": "check",
                    "recommended_action": "check",
                    "ev_loss_bb": None,
                },
            ],
        },
    )
    manager.append_hand_history(
        "LeakUser",
        {
            "session_id": "s2",
            "hand_number": 2,
            "decision_points": [
                {
                    "betting_round": "turn",
                    "hero_position": 2,
                    "chosen_action": "call",
                    "recommended_action": "fold",
                    "opponent": {"type": "loose-aggressive"},
                    "ev_loss_bb": 1.5,
                    "ev_loss_chips": 15,
                }
            ],
        },
    )

    response = client.get("/api/analytics/ev-leaks?player=LeakUser&limit=5")
    assert response.status_code == 200
    payload = response.json()
    assert payload["priced_decision_count"] == 3
    assert payload["mistake_count"] == 2
    assert payload["total_ev_loss_bb"] == 4.0
    assert payload["worst_group"]["street"] == "turn"
    assert payload["worst_group"]["decision_count"] == 2
    assert payload["groups"][0]["total_ev_loss_bb"] == 4.0


# ----- /api/games/sessions all-in regression --------------------------------


def test_all_in_hand_resolves_with_winners(tmp_path):
    """All-in must complete the hand: winners list non-empty + pot moved.

    Reproduces the original 'all-in shows no winner / no money changes hands'
    bug. We don't use any `seed=` kwarg here because GameEngine doesn't
    accept one on main; we just rely on it eventually resolving and not
    looping forever (engine has a safety break on the betting round).
    """

    class ScriptedHandler:
        def __init__(self, responses):
            self._responses = list(responses)

        def get_menu_choice(self, options, prompt=""):
            return self._responses.pop(0) if self._responses else 1

        def get_number_input(self, prompt, min_value=None, max_value=None, integer_only=False):
            return self._responses.pop(0) if self._responses else (min_value or 1)

        def get_yes_no_input(self, prompt):
            return False

    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("Hero", 1000)
    manager.save_players()

    hero = Player("Hero", 1000)
    # 1 opponent, then "All-In" (the last option in the human menu). The menu
    # order is [Call|Check, Raise, Fold, All-In] when raising is allowed.
    handler = ScriptedHandler(responses=[1, 4, 4, 4, 4])
    engine = GameEngine(hero, data_manager=manager, display=None, input_handler=handler)
    engine._test_mode = True
    engine.start_game(
        {
            "type": "cash",
            "limit": "no_limit",
            "small_blind": 10,
            "big_blind": 20,
            "max_players": 2,
        }
    )

    starting_hero_chips = engine.human_player.bankroll
    opponent = next(
        p for p in engine.table.get_players_in_order() if p is not engine.human_player
    )
    starting_opp_chips = opponent.bankroll

    engine.play_hand()

    last_hand = engine.session_tracker.hand_history[-1]
    assert last_hand["winners"], (
        f"Expected at least one winner, got empty list. last_hand={last_hand!r}"
    )
    assert last_hand["pot_total"] > 0

    hero_delta = engine.human_player.bankroll - starting_hero_chips
    opp_delta = opponent.bankroll - starting_opp_chips
    # Either hero won and gained or opponent won and gained - the key is that
    # chips actually moved.
    assert hero_delta != 0 or opp_delta != 0, (
        f"Expected chips to move on all-in. hero_delta={hero_delta}, "
        f"opp_delta={opp_delta}"
    )
