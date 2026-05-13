"""Reproduce the 'all-in shows no winner / no money changes hands' bug."""
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from data.manager import DataManager
from game.game_engine import GameEngine
from game.player import Player, PlayerAction


class ScriptedInputHandler:
    """Replays a queue of menu/number/yes_no responses, recording prompts."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.prompts = []

    def get_menu_choice(self, options, prompt=""):
        self.prompts.append(("menu", prompt, list(options)))
        if not self._responses:
            return 1
        return self._responses.pop(0)

    def get_number_input(self, prompt, min_value=None, max_value=None, integer_only=False):
        self.prompts.append(("number", prompt, min_value, max_value))
        if not self._responses:
            return min_value or 1
        return self._responses.pop(0)

    def get_yes_no_input(self, prompt):
        self.prompts.append(("yes_no", prompt, None))
        if not self._responses:
            return False
        return self._responses.pop(0)


def _setup_engine(tmp_path, *, responses):
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("Hero", 1000)
    manager.save_players()

    hero = Player("Hero", 1000)
    handler = ScriptedInputHandler(responses)
    engine = GameEngine(hero, data_manager=manager, display=None, input_handler=handler, seed=12345)
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
    return engine, handler


def test_all_in_hand_completes_with_winners_and_pot_distributed(tmp_path):
    """Hero shoves preflop, AI calls, hand should resolve to a known winner."""
    # Setup: 1 opponent, hero responds to opponent count, then goes All-In.
    # Menu order in _get_human_player_action: [Call|Check, Raise (if allowed), Fold, All-In]
    # We pick the All-In option whenever the hero is asked to act.
    responses = [
        1,  # number of opponents = 1 (SetupInputHandler-style)
        4,  # all-in preflop (4th menu option)
        4,  # if asked again on flop, all-in (defensive; hero will be all_in so won't be asked)
    ]

    engine, handler = _setup_engine(tmp_path, responses=responses)

    starting_hero_bankroll = engine.human_player.bankroll
    opponent = next(p for p in engine.table.get_players_in_order() if p is not engine.human_player)
    starting_opp_bankroll = opponent.bankroll

    engine.play_hand()

    last_hand = engine.session_tracker.hand_history[-1]

    assert last_hand["winners"], (
        f"Expected at least one winner, got empty list. last_hand={last_hand!r}"
    )

    assert last_hand["pot_total"] > 0, (
        f"Expected pot_total > 0, got {last_hand['pot_total']!r}"
    )

    # Money must change hands: either hero gained chips or lost them all.
    hero_delta = engine.human_player.bankroll - starting_hero_bankroll
    opp_delta = opponent.bankroll - starting_opp_bankroll

    if "Hero" in last_hand["winners"]:
        assert hero_delta > 0, f"Hero won but bankroll didn't grow ({hero_delta})"
        assert opp_delta < 0, f"Hero won but opponent didn't lose ({opp_delta})"
    else:
        assert hero_delta < 0, f"Hero lost but bankroll didn't shrink ({hero_delta})"
        assert opp_delta > 0, f"Hero lost but opponent didn't gain ({opp_delta})"


def test_hand_completes_when_stdout_cannot_encode_emojis(tmp_path, monkeypatch):
    """Regression: engine must not crash a hand when stdout is cp1252.

    On Windows, the FastAPI server's stdout defaults to cp1252 which can't
    encode the emoji characters in the engine's status prints. That used to
    raise UnicodeEncodeError out of play_hand and leave the UI stuck on
    'betting stops, no winner shown, no money changes hands'.
    """
    # Simulate a Windows-console-style stdout: strict cp1252 encoding.
    raw = io.BytesIO()
    fake_stdout = io.TextIOWrapper(raw, encoding="cp1252", errors="strict", newline="\n")
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    responses = [1, 4]  # 1 opponent, all-in preflop
    engine, _ = _setup_engine(tmp_path, responses=responses)
    engine.play_hand()

    last_hand = engine.session_tracker.hand_history[-1]
    assert last_hand["winners"], (
        "Engine choked on emoji encoding instead of completing the hand. "
        f"last_hand={last_hand!r}"
    )
    assert last_hand["pot_total"] > 0


def test_all_in_against_multiple_opponents(tmp_path):
    """Hero shoves preflop against 3 opponents - the hand must still resolve."""
    responses = [
        3,  # 3 opponents
        4,  # all-in preflop
    ]

    engine, handler = _setup_engine(tmp_path, responses=responses)
    engine.play_hand()
    last_hand = engine.session_tracker.hand_history[-1]
    assert last_hand["winners"], (
        f"Expected at least one winner with 3 opponents; got {last_hand!r}"
    )
    assert last_hand["pot_total"] > 0


def test_submit_input_returns_completed_state_no_polling(tmp_path, monkeypatch):
    """Like the frontend: submit all-in and trust the response - no follow-up polling.

    The frontend's HTTP fallback path does not re-fetch state automatically after
    a submit_input call. So the response from submit_input MUST already reflect
    the hand having either reached the next pending_input or finished.
    """
    BACKEND_PATH = ROOT / "backend"
    if str(BACKEND_PATH) not in sys.path:
        sys.path.insert(0, str(BACKEND_PATH))

    from fastapi.testclient import TestClient

    from app.main import app
    from app.services import game_service

    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    game_service.SESSIONS.clear()
    client = TestClient(app)

    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "ShoveHero",
            "game_type": "cash",
            "limit_type": "no_limit",
            "small_blind": 5,
            "big_blind": 10,
            "opponents": 1,
        },
    )
    session_id = create.json()["id"]

    # Kick off the hand and get to the first pending_input.
    state = client.post(f"/api/games/sessions/{session_id}/hand/start").json()

    # The first prompt should be the action menu.
    pending = state["pending_input"]
    assert pending is not None
    assert pending["kind"] == "menu"
    options = pending["options"]
    all_in_idx = next(
        i for i, opt in enumerate(options, start=1) if "all-in" in opt.lower()
    )

    # Submit all-in. WITHOUT a follow-up GET, this single response must already
    # reflect the settled state - because that's what the WS-less frontend sees.
    response = client.post(
        f"/api/games/sessions/{session_id}/hand/input", json={"choice": all_in_idx}
    ).json()

    # If the bug is present, status will be "in_hand" and last_hand will be None
    # because the engine is still working through flop/turn/river when we return.
    assert response["status"] in {"hand_complete", "awaiting_input"}, (
        f"submit_input returned mid-hand state: {response!r}"
    )
    if response["status"] == "hand_complete":
        assert response["last_hand"] is not None
        assert response["last_hand"]["winners"], (
            f"hand_complete but no winners: {response['last_hand']!r}"
        )


def test_submit_input_returns_completed_state_with_many_opponents(tmp_path, monkeypatch):
    """With more opponents the post-all-in flop/turn/river takes longer.

    Make sure submit_input still returns settled state even when the engine
    has to chew through more AI decisions before reaching showdown.
    """
    BACKEND_PATH = ROOT / "backend"
    if str(BACKEND_PATH) not in sys.path:
        sys.path.insert(0, str(BACKEND_PATH))

    from fastapi.testclient import TestClient

    from app.main import app
    from app.services import game_service

    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    game_service.SESSIONS.clear()
    client = TestClient(app)

    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "TableShove",
            "game_type": "cash",
            "limit_type": "no_limit",
            "small_blind": 5,
            "big_blind": 10,
            "opponents": 5,
        },
    )
    session_id = create.json()["id"]
    state = client.post(f"/api/games/sessions/{session_id}/hand/start").json()

    # Walk through any pre-action prompts (e.g. earlier seats acting before hero)
    while state["status"] == "awaiting_input":
        pending = state["pending_input"]
        options = pending["options"]
        all_in_idx = next(
            (i for i, opt in enumerate(options, start=1) if "all-in" in opt.lower()),
            None,
        )
        if all_in_idx is None:
            # No all-in option (e.g. early position with low bet). Just call/check
            # until it's our turn with a sensible all-in.
            idx = next(
                (i for i, opt in enumerate(options, start=1)
                 if "call" in opt.lower() or "check" in opt.lower()),
                1,
            )
            state = client.post(
                f"/api/games/sessions/{session_id}/hand/input", json={"choice": idx}
            ).json()
            continue

        # Shove.
        state = client.post(
            f"/api/games/sessions/{session_id}/hand/input", json={"choice": all_in_idx}
        ).json()

    assert state["status"] == "hand_complete", (
        f"After shoving and getting no more prompts, state should be hand_complete. "
        f"Got: status={state['status']}, last_hand={state.get('last_hand')!r}"
    )
    assert state["last_hand"]["winners"]


def test_all_in_through_api_completes_and_shows_winners(tmp_path, monkeypatch):
    """End-to-end via the API: shove all-in, verify winners + pot are surfaced."""
    BACKEND_PATH = ROOT / "backend"
    if str(BACKEND_PATH) not in sys.path:
        sys.path.insert(0, str(BACKEND_PATH))

    from fastapi.testclient import TestClient

    from app.main import app
    from app.services import game_service

    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    game_service.SESSIONS.clear()
    client = TestClient(app)

    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "AllInHero",
            "game_type": "cash",
            "limit_type": "no_limit",
            "small_blind": 5,
            "big_blind": 10,
            "opponents": 1,
        },
    )
    assert create.status_code == 200, create.text
    session_id = create.json()["id"]

    state = client.post(f"/api/games/sessions/{session_id}/hand/start").json()

    steps = 0
    while state.get("status") not in {"hand_complete", "tournament_complete", "error"} and steps < 40:
        pending = state.get("pending_input")
        if not pending:
            state = client.get(f"/api/games/sessions/{session_id}/hand").json()
            steps += 1
            continue

        kind = pending.get("kind")
        if kind == "menu":
            options = pending.get("options") or []
            # Find the "All-In" option index (1-based for choice param).
            all_in_idx = next(
                (i for i, opt in enumerate(options, start=1) if "all-in" in opt.lower()),
                None,
            )
            if all_in_idx is None:
                # Fall back to Check/Call so the hand keeps progressing.
                all_in_idx = next(
                    (i for i, opt in enumerate(options, start=1)
                     if "check" in opt.lower() or "call" in opt.lower()),
                    1,
                )
            payload = {"choice": all_in_idx}
        elif kind == "number":
            payload = {"value": pending.get("min_value") or 1}
        else:
            payload = {"value": False}

        response = client.post(f"/api/games/sessions/{session_id}/hand/input", json=payload)
        assert response.status_code == 200, response.text
        state = response.json()
        steps += 1

    assert state["status"] == "hand_complete", f"Status was {state['status']}: {state!r}"
    last_hand = state.get("last_hand") or {}
    assert last_hand.get("winners"), (
        f"All-in finished but no winners reported. last_hand={last_hand!r}"
    )
    assert int(last_hand.get("pot_total", 0)) > 0, (
        f"All-in pot_total is 0 - distribution may have failed. last_hand={last_hand!r}"
    )
