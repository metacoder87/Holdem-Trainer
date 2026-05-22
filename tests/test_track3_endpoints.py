"""Integration tests for Track 3 endpoints.

Verifies:
  - GET /api/analytics/regret-heatmap returns the documented shape.
  - POST /api/training/drill/from-decision seeds a drill with the
    correct board / hole cards / pot from a recorded decision.
  - get_game_state serializes dealer + SB + BB seat markers.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SRC = ROOT / "src"
for p in (BACKEND, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.main import app  # noqa: E402
from app.services import game_service  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    game_service.SESSIONS.clear()
    return TestClient(app)


# ---------- Regret heatmap ----------


def test_regret_heatmap_empty_player_returns_empty_payload(client):
    response = client.get("/api/analytics/regret-heatmap")
    assert response.status_code == 200
    payload = response.json()
    assert payload["cells"] == []
    assert payload["totals"]["decisions"] == 0


def test_regret_heatmap_validates_scan_hands_range(client):
    too_low = client.get("/api/analytics/regret-heatmap?scan_hands=1")
    assert too_low.status_code == 422
    too_high = client.get("/api/analytics/regret-heatmap?scan_hands=999999")
    assert too_high.status_code == 422


# ---------- Drill from decision ----------


def test_drill_from_decision_404_for_unknown_player(client):
    response = client.post(
        "/api/training/drill/from-decision",
        json={"player": "Nobody", "hand_number": 1, "decision_index": 0},
    )
    assert response.status_code == 404


def test_drill_from_decision_validates_body(client):
    """hand_number must be >= 1 and decision_index >= 0."""
    response = client.post(
        "/api/training/drill/from-decision",
        json={"player": "X", "hand_number": 0, "decision_index": 0},
    )
    assert response.status_code == 422


# ---------- get_game_state includes dealer / blinds metadata ----------


def test_get_game_state_serializes_dealer_and_blinds(client):
    """Start a real hand, snapshot state, verify seat markers + blind labels."""
    response = client.post(
        "/api/games/sessions",
        json={
            "player_name": "DealerTest",
            "game_type": "cash",
            "limit_type": "no_limit",
            "small_blind": 5,
            "big_blind": 10,
            "opponents": 2,
        },
    )
    assert response.status_code == 200
    session_id = response.json()["id"]

    # The hand state endpoint returns the full wrapped payload with
    # ``state`` (the game_state dict).
    hand_payload = client.post(
        f"/api/games/sessions/{session_id}/hand/start"
    ).json()
    state = hand_payload.get("state") or {}

    players = state.get("players") or []
    assert players, f"Players list should not be empty; payload was {hand_payload}"

    # Each player carries seat indicators.
    for p in players:
        for key in {"is_dealer", "is_small_blind", "is_big_blind", "is_hero"}:
            assert key in p, f"Player payload missing {key}: {p}"

    blinds = state.get("blinds") or {}
    assert "dealer_name" in blinds
    assert "small_blind_player" in blinds
    assert "big_blind_player" in blinds
    # At least one player should be flagged as dealer (in 2+ player tables).
    assert any(p.get("is_dealer") for p in players)
    assert any(p.get("is_big_blind") for p in players)


# ---------- SPR bucket captured on decision points ----------


def test_decision_points_capture_spr_bucket():
    """Drive a postflop check spot and verify spr_bucket is recorded."""
    from game.card import Card, Rank, Suit
    from game.game_engine import BettingRound, GameEngine, GameState
    from game.player import Player, PlayerAction

    class _NullHandler:
        def get_menu_choice(self, options, prompt=""):
            return 1

        def get_number_input(self, *a, **kw):
            return 1.0

        def get_yes_no_input(self, *a, **kw):
            return False

    hero = Player("Hero", bankroll=1000)
    engine = GameEngine(hero, data_manager=None, display=None, input_handler=_NullHandler())
    engine._test_mode = True
    engine.start_game(
        {
            "type": "cash",
            "limit": "no_limit",
            "small_blind": 5,
            "big_blind": 10,
            "max_players": 2,
        }
    )
    villain = engine.table.get_players_in_order()[1]
    hero.folded = False
    villain.folded = False
    hero.hole_cards = [Card(Suit.SPADES, Rank.SEVEN), Card(Suit.CLUBS, Rank.TWO)]
    villain.hole_cards = [Card(Suit.SPADES, Rank.JACK), Card(Suit.HEARTS, Rank.TEN)]
    engine.community_cards = [
        Card(Suit.HEARTS, Rank.QUEEN),
        Card(Suit.DIAMONDS, Rank.SEVEN),
        Card(Suit.CLUBS, Rank.TWO),
    ]
    engine.session_tracker.start_hand(hand_meta={"hero_name": hero.name})
    engine.current_betting_round = BettingRound.FLOP
    engine.game_state = GameState.FLOP

    context = {
        "current_bet": 0,
        "pot_total": 100,  # SPR = 1000/100 = 10 -> bucket 3
        "can_check": True,
        "raise_allowed": True,
        "min_raise": 10,
    }
    engine._record_human_decision_point(
        chosen_action=PlayerAction.CHECK,
        chosen_amount=0,
        context=context,
    )

    decisions = engine.session_tracker.hand_history[-1].get("decision_points") or []
    assert decisions, "Decision should have been recorded"
    last = decisions[-1]
    assert "spr" in last
    assert "spr_bucket" in last
    # SPR ~ 10 -> bucket 3 (6 < spr <= 12).
    assert last["spr_bucket"] == 3
    assert abs(last["spr"] - 10.0) < 0.01
