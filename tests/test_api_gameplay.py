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
from game.card import Card, Rank, Suit  # noqa: E402
from game.game_engine import BettingRound, GameState  # noqa: E402
from game.pot import Pot  # noqa: E402


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
            "hud": True,
        },
    )
    assert create.status_code == 200
    session_id = create.json()["id"]

    start = client.post(f"/api/games/sessions/{session_id}/hand/start")
    assert start.status_code == 200
    state = start.json()
    assert state["state"]["hud"]["opponents"]

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
    assert state["last_hand"]["coach_notes"]["headline"]
    assert state["state"]["hero_cards"]


def test_live_coach_only_appears_for_pending_decision(client):
    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "CoachUser",
            "game_type": "cash",
            "limit_type": "no_limit",
            "small_blind": 5,
            "big_blind": 10,
            "opponents": 1,
            "hud": True,
        },
    )
    assert create.status_code == 200
    session_id = create.json()["id"]

    idle = client.get(f"/api/games/sessions/{session_id}/hand").json()
    assert idle["pending_input"] is None
    assert idle["live_coach"] is None

    state = client.post(f"/api/games/sessions/{session_id}/hand/start").json()
    steps = 0
    while not state.get("pending_input") and state["status"] != "hand_complete" and steps < 10:
        state = client.get(f"/api/games/sessions/{session_id}/hand").json()
        steps += 1

    assert state["pending_input"] is not None
    coach = state["live_coach"]
    assert coach is not None
    assert coach["recommended_action"]
    assert "required_equity" in coach["math"]
    assert "estimated_equity" in coach["math"]
    assert "opponent" in coach


def test_live_coach_response_is_cached_until_relevant_state_changes(client, monkeypatch):
    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "CoachCacheUser",
            "game_type": "cash",
            "limit_type": "no_limit",
            "small_blind": 5,
            "big_blind": 10,
            "opponents": 1,
            "hud": True,
        },
    )
    assert create.status_code == 200
    session_id = create.json()["id"]

    state = client.post(f"/api/games/sessions/{session_id}/hand/start").json()
    steps = 0
    while not state.get("pending_input") and state["status"] != "hand_complete" and steps < 20:
        state = client.get(f"/api/games/sessions/{session_id}/hand").json()
        steps += 1
    assert state["pending_input"] is not None

    session = game_service.SESSIONS[session_id]
    calls = []

    def fake_live_coach(session_arg, pending_arg):
        calls.append((session_arg.id, pending_arg.get("kind")))
        return {
            "recommended_action": "check",
            "confidence": 0.5,
            "summary": f"cached response {len(calls)}",
            "math": {},
            "opponent": {},
            "rationale": [],
            "warnings": [],
            "history_signals": [],
            "training_link": None,
        }

    monkeypatch.setattr(game_service, "_build_live_coach", fake_live_coach)
    session._coach_cache_key = None
    session._coach_cache_val = None

    first = game_service._build_hand_response(session)
    second = game_service._build_hand_response(session)
    assert first["live_coach"]["summary"] == "cached response 1"
    assert second["live_coach"]["summary"] == "cached response 1"
    assert len(calls) == 1

    with session.lock:
        session.engine.human_player.bankroll += 1

    third = game_service._build_hand_response(session)
    assert third["live_coach"]["summary"] == "cached response 2"
    assert len(calls) == 2


def test_gameplay_persists_session_and_single_hand_history(client, tmp_path, monkeypatch):
    data_file = tmp_path / "players.json"
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(data_file))
    game_service.SESSIONS.clear()

    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "PersistUser",
            "game_type": "cash",
            "limit_type": "no_limit",
            "small_blind": 5,
            "big_blind": 10,
            "opponents": 1,
            "hud": True,
        },
    )
    session_id = create.json()["id"]
    state = client.post(f"/api/games/sessions/{session_id}/hand/start").json()

    steps = 0
    while state["status"] != "hand_complete" and steps < 30:
        pending = state.get("pending_input")
        if pending:
            state = client.post(
                f"/api/games/sessions/{session_id}/hand/input",
                json=_payload_for_pending(pending),
            ).json()
        else:
            state = client.get(f"/api/games/sessions/{session_id}/hand").json()
        steps += 1

    assert state["status"] == "hand_complete"

    manager = DataManager(data_file=str(data_file))
    sessions = manager.get_sessions("PersistUser")
    assert len(sessions) == 1
    assert sessions[0]["id"] == session_id
    assert sessions[0]["status"] == "hand_complete"
    assert sessions[0]["hands_played"] >= 1

    history = manager.load_hand_history("PersistUser", limit=10)
    assert len(history) == 1
    assert history[0]["session_id"] == session_id

    api_sessions = client.get("/api/stats/sessions?player=PersistUser")
    assert api_sessions.status_code == 200
    assert api_sessions.json()[0]["id"] == session_id


def test_websocket_returns_session_state(client):
    create = client.post(
        "/api/games/sessions",
        json={"player_name": "SocketUser", "game_type": "cash", "limit_type": "no_limit", "opponents": 1},
    )
    session_id = create.json()["id"]

    # Route is /ws/sessions/{id}, not /ws/{id} (was a README/test typo)
    with client.websocket_connect(f"/ws/sessions/{session_id}") as websocket:
        payload = websocket.receive_json()

    assert payload["session_id"] == session_id
    assert "state" in payload


def test_cleanup_sessions_removes_idle_sessions(client):
    create = client.post(
        "/api/games/sessions",
        json={"player_name": "CleanupUser", "game_type": "cash", "limit_type": "no_limit", "opponents": 1},
    )
    session_id = create.json()["id"]
    session = game_service._get_live_session(session_id)
    assert session is not None

    removed = game_service.cleanup_sessions(now=session.updated_at + 999999)

    assert removed == 1
    assert game_service._get_live_session(session_id) is None


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


def test_cash_session_returns_game_over_when_hero_is_busted(client):
    create = client.post(
        "/api/games/sessions",
        json={"player_name": "BustedHero", "game_type": "cash", "limit_type": "no_limit", "opponents": 1},
    )
    session_id = create.json()["id"]
    session = game_service._get_live_session(session_id)
    assert session is not None
    session.engine.human_player.bankroll = 0

    response = client.post(f"/api/games/sessions/{session_id}/hand/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "game_over"
    assert payload["terminal_reason"] == "hero_busted"
    assert payload["pending_input"] is None


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


def _seed_mid_river_snapshot(client, player_name="RiverRestore"):
    create = client.post(
        "/api/games/sessions",
        json={"player_name": player_name, "game_type": "cash", "limit_type": "no_limit", "opponents": 1},
    )
    assert create.status_code == 200
    session_id = create.json()["id"]
    session = game_service._get_live_session(session_id)
    assert session is not None

    engine = session.engine
    players = engine.table.get_players_in_order()
    hero = engine.human_player
    villain = next(player for player in players if player is not hero)

    hero.bankroll = 900
    hero.current_bet = 100
    hero.total_bet = 100
    hero.hole_cards = [Card(Suit.SPADES, Rank.ACE), Card(Suit.HEARTS, Rank.KING)]
    villain.bankroll = 850
    villain.current_bet = 150
    villain.total_bet = 150
    villain.hole_cards = [Card(Suit.CLUBS, Rank.QUEEN), Card(Suit.DIAMONDS, Rank.QUEEN)]

    engine.game_state = GameState.RIVER
    engine.current_betting_round = BettingRound.RIVER
    engine.community_cards = [
        Card(Suit.CLUBS, Rank.TWO),
        Card(Suit.DIAMONDS, Rank.SEVEN),
        Card(Suit.SPADES, Rank.TEN),
        Card(Suit.HEARTS, Rank.FOUR),
        Card(Suit.CLUBS, Rank.NINE),
    ]
    engine.deck.cards = [
        Card(Suit.SPADES, Rank.TWO),
        Card(Suit.HEARTS, Rank.THREE),
        Card(Suit.DIAMONDS, Rank.FIVE),
    ]
    engine.pot = Pot()
    engine.pot.add_bet(hero, 100)
    engine.pot.add_bet(villain, 150)
    engine._current_hand_players = [hero, villain]
    engine._min_raise_increment = 50
    engine._set_betting_loop_state(
        betting_round=BettingRound.RIVER,
        players_in_round=[hero, villain],
        players_acted={hero: False, villain: True},
        highest_bet=150,
        player_index=0,
    )
    engine.session_tracker.start_hand(
        hero_hole_cards=[str(card) for card in hero.hole_cards],
        hand_meta={"session_id": session_id},
    )
    engine.session_tracker.set_board([str(card) for card in engine.community_cards])
    with session.input_handler._lock:
        session.input_handler._pending = game_service.InputRequest(
            kind="menu",
            prompt="What would you like to do",
            options=["Call $50", "Raise (min $200)", "Fold", "All-In"],
            min_value=1,
            max_value=4,
            integer_only=True,
        )
    session.status = "awaiting_input"
    session.flush_snapshot("test_mid_river")
    return session_id


def test_mid_river_snapshot_restores_pot_bets_next_to_act_and_deck(client):
    session_id = _seed_mid_river_snapshot(client)
    game_service.SESSIONS.clear()

    response = client.get(f"/api/games/sessions/{session_id}/hand")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["status"] == "awaiting_input"
    assert payload["state"]["game_state"] == "river"
    assert payload["state"]["pot_size"] == 250
    assert payload["state"]["next_to_act"] == "RiverRestore"
    assert payload["pending_input"]["options"][0] == "Call $50"
    players = {player["name"]: player for player in payload["state"]["players"]}
    assert players["RiverRestore"]["current_bet"] == 100
    assert next(player for name, player in players.items() if name != "RiverRestore")["current_bet"] == 150

    restored = game_service._get_live_session(session_id)
    assert restored is not None
    assert [str(card) for card in restored.engine.deck.cards] == ["2♠", "3♥", "5♦"]


def test_websocket_rehydrates_missing_memory_session_and_reconnects_same_prompt(client):
    session_id = _seed_mid_river_snapshot(client, player_name="SocketRestore")
    game_service.SESSIONS.clear()

    with client.websocket_connect(f"/ws/sessions/{session_id}") as websocket:
        first = websocket.receive_json()
    assert first["session_id"] == session_id
    assert first["state"]["next_to_act"] == "SocketRestore"
    assert first["pending_input"]["prompt"] == "What would you like to do"

    game_service.SESSIONS.clear()
    with client.websocket_connect(f"/ws/sessions/{session_id}") as websocket:
        second = websocket.receive_json()
    assert second["state"]["next_to_act"] == first["state"]["next_to_act"]
    assert second["pending_input"] == first["pending_input"]


def test_tournament_opponent_elimination_snapshot_restores_remaining_players(client):
    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "ElimRestore",
            "game_type": "tournament",
            "limit_type": "no_limit",
            "opponents": 3,
            "buy_in": 1000,
            "starting_chips": 1000,
        },
    )
    assert create.status_code == 200
    session_id = create.json()["id"]
    session = game_service._get_live_session(session_id)
    assert session is not None
    victim = next(player for player in session.engine.table.get_players_in_order() if player.name == "AI_1")
    victim.bankroll = 0
    session.engine._handle_eliminations()
    session.flush_snapshot("test_elimination")
    game_service.SESSIONS.clear()

    response = client.get(f"/api/games/sessions/{session_id}/hand")

    assert response.status_code == 200
    players = response.json()["state"]["players"]
    assert len(players) == 3
    assert "AI_1" not in {player["name"] for player in players}


def test_hero_elimination_terminal_snapshot_is_idempotent(client):
    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "HeroGone",
            "game_type": "tournament",
            "limit_type": "no_limit",
            "opponents": 2,
            "buy_in": 1000,
            "starting_chips": 1000,
        },
    )
    assert create.status_code == 200
    session_id = create.json()["id"]
    session = game_service._get_live_session(session_id)
    assert session is not None
    session.engine.human_player.bankroll = 0
    session.engine._handle_eliminations()

    first = client.post(f"/api/games/sessions/{session_id}/hand/start")
    second = client.post(f"/api/games/sessions/{session_id}/hand/start")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "game_over"
    assert second.json()["status"] == "game_over"
    assert first.json()["terminal_reason"] == "hero_eliminated"
    assert second.json()["terminal_reason"] == "hero_eliminated"
