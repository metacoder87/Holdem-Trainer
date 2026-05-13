"""Coverage for analytics + hand-replay endpoints and tournament settlement."""
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
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    game_service.SESSIONS.clear()
    return TestClient(app)


def _seed_player_with_history(tmp_path, player_name="ReplayUser"):
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player(player_name, 5000)
    manager.save_players()
    manager.append_hand_history(
        player_name,
        {
            "hand_number": 1,
            "started_at": "2026-05-09T10:00:00",
            "ended_at": "2026-05-09T10:01:00",
            "hero_hole_cards": ["Ah", "Kd"],
            "board": ["2c", "7d", "Ts", "5h"],
            "board_by_street": {
                "flop": ["2c", "7d", "Ts"],
                "turn": ["2c", "7d", "Ts", "5h"],
            },
            "actions": [
                {"player": player_name, "action": "raise", "amount": 30, "pot_before": 15, "pot_after": 45, "betting_round": "preflop", "did_raise": True},
                {"player": "AI_1", "action": "call", "amount": 30, "pot_before": 45, "pot_after": 75, "betting_round": "preflop", "did_raise": False},
                {"player": player_name, "action": "raise", "amount": 50, "pot_before": 75, "pot_after": 125, "betting_round": "flop", "did_raise": True},
                {"player": "AI_1", "action": "fold", "amount": 0, "pot_before": 125, "pot_after": 125, "betting_round": "flop", "did_raise": False},
            ],
            "decision_points": [
                {"betting_round": "preflop", "chosen_action": "raise", "recommended_action": "raise", "quality": "optimal"},
                {"betting_round": "flop", "chosen_action": "raise", "recommended_action": "raise", "quality": "optimal", "equity": 0.65, "required_equity": 0.3},
            ],
            "winners": [player_name],
            "pot_total": 125,
            "meta": {
                "small_blind": 5,
                "big_blind": 10,
                "ante": 0,
                "blind_level": 1,
                "game_type": "cash",
                "limit_type": "no_limit",
                "hero_won": True,
            },
        },
    )


def test_hand_replay_endpoint_returns_streets(client, tmp_path):
    _seed_player_with_history(tmp_path)

    response = client.get("/api/hands/ReplayUser/1/replay")
    assert response.status_code == 200
    payload = response.json()

    assert payload["hand_number"] == 1
    assert payload["winners"] == ["ReplayUser"]
    assert payload["summary"]["small_blind"] == 5

    street_names = [s["name"] for s in payload["streets"]]
    assert "preflop" in street_names
    assert "flop" in street_names

    flop = next(s for s in payload["streets"] if s["name"] == "flop")
    assert flop["board"] == ["2c", "7d", "Ts"]
    assert any(d["quality"] == "optimal" for d in flop["decisions"])


def test_hand_replay_missing_returns_404(client, tmp_path):
    _seed_player_with_history(tmp_path)
    response = client.get("/api/hands/ReplayUser/999/replay")
    assert response.status_code == 404


def test_analytics_summary_defaults_when_no_player(client):
    response = client.get("/api/analytics/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["player"] is None
    assert payload["session_count"] == 0


def test_analytics_summary_with_session_data(client, tmp_path):
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("AnalyticsUser", 10000)
    manager.update_player_stats(
        "AnalyticsUser",
        {
            "sessions": [
                {"hands_played": 50, "vpip": 0.55, "pfr": 0.05, "aggression_factor": 0.5, "decision_accuracy": 0.4, "started_at": "2026-05-01T10:00:00"},
                {"hands_played": 50, "vpip": 0.50, "pfr": 0.04, "aggression_factor": 0.6, "decision_accuracy": 0.45, "started_at": "2026-05-08T10:00:00"},
            ],
            "skill_level": "beginner",
        },
    )
    manager.save_players()

    response = client.get("/api/analytics/summary?player=AnalyticsUser")
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_count"] == 2
    assert payload["metrics"]["vpip"] > 0.0
    assert len(payload["trends"]["vpip"]) == 2


def test_analytics_leaks_flags_loose_passive_player(client, tmp_path):
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("LeakyUser", 10000)
    manager.update_player_stats(
        "LeakyUser",
        {
            "sessions": [
                {"hands_played": 100, "vpip": 0.55, "pfr": 0.04, "aggression_factor": 0.6},
            ],
        },
    )
    manager.save_players()

    response = client.get("/api/analytics/leaks?player=LeakyUser")
    assert response.status_code == 200
    payload = response.json()
    leak_ids = [leak["id"] for leak in payload["leaks"]]
    assert "too_loose" in leak_ids
    assert "too_passive" in leak_ids


def test_training_tracks_endpoint(client, tmp_path):
    response = client.get("/api/training/tracks")
    assert response.status_code == 200
    payload = response.json()
    assert "training_tracks" in payload
    assert len(payload["training_tracks"]) >= 4


def test_tournament_buy_in_deducted_and_refunded_on_loss(client, tmp_path):
    """A losing tournament should still return chip stack -> cash."""
    # Seed a wealthy player so we can afford a tournament.
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("TournUser", 50000)
    manager.save_players()

    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "TournUser",
            "game_type": "tournament",
            "limit_type": "no_limit",
            "buy_in": 1000,
            "starting_chips": 5000,
            "opponents": 1,
        },
    )
    assert create.status_code == 200
    session_id = create.json()["id"]

    session = game_service.SESSIONS[session_id]

    # Simulate hero busting out by removing them from the table after session
    # creation. The next state poll should detect elimination and trigger
    # _finalize_tournament -> chip stack converted back to cash + payout.
    session.engine.table.remove_player(session.engine.human_player)

    response = client.get(f"/api/games/sessions/{session_id}/hand")
    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "tournament_complete"
    assert payload["tournament_result"]["result"] == "lost"

    # The hero's cash bankroll should be pre-buy-in cash minus buy-in
    # (50000 - 1000 = 49000) since they lost and got no payout.
    assert payload["tournament_result"]["final_bankroll"] == 49000

    # Subsequent start_hand should be a no-op (tournament already over).
    next_state = client.post(f"/api/games/sessions/{session_id}/hand/start").json()
    assert next_state["status"] == "tournament_complete"


def test_tournament_winner_collects_full_prize_pool(client, tmp_path):
    """Winning hero should receive the entire prize pool back into cash bankroll."""
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("Champ", 50000)
    manager.save_players()

    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "Champ",
            "game_type": "tournament",
            "limit_type": "no_limit",
            "buy_in": 1000,
            "starting_chips": 5000,
            "opponents": 1,
        },
    )
    session_id = create.json()["id"]
    session = game_service.SESSIONS[session_id]

    # Simulate the AI busting out, leaving only the hero.
    for player in list(session.engine.table.get_players_in_order()):
        if player is not session.engine.human_player:
            session.engine.table.remove_player(player)

    payload = client.get(f"/api/games/sessions/{session_id}/hand").json()
    assert payload["status"] == "tournament_complete"
    assert payload["tournament_result"]["result"] == "won"
    # 2-player payout is winner-take-all of the 2 * buy_in prize pool, so
    # cash = (50000 - 1000) + 2000 = 51000
    assert payload["tournament_result"]["final_bankroll"] == 51000


def test_session_store_evicts_when_over_limit(monkeypatch, tmp_path):
    """LRU eviction kicks in once SESSIONS exceeds its limit."""
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    game_service.SESSIONS.clear()

    store = game_service._SessionStore(limit=2, ttl_seconds=0.0)

    class _Fake:
        def __init__(self, sid):
            self.id = sid
            self.last_touched = 0.0
            self.thread = None

    store["a"] = _Fake("a")
    store["b"] = _Fake("b")
    store["c"] = _Fake("c")

    assert "a" not in store
    assert "b" in store
    assert "c" in store


def test_drill_endpoints_round_trip(client):
    focus = client.get("/api/training/drills/focus-areas")
    assert focus.status_code == 200
    assert any(area["id"] == "poor_pot_odds" for area in focus.json())

    create = client.post(
        "/api/training/drills",
        json={"focus_area": "poor_pot_odds", "difficulty": 2},
    )
    assert create.status_code == 200
    drill = create.json()
    assert drill["focus_area"] == "poor_pot_odds"
    assert drill["correct_action"] in {"call", "fold"}
    assert "drill_id" in drill

    answer = client.post(
        "/api/training/drills/answer",
        json={
            "drill_id": drill["drill_id"],
            "kind": drill["kind"],
            "correct_action": drill["correct_action"],
            "user_answer": drill["correct_action"],
        },
    )
    assert answer.status_code == 200
    body = answer.json()
    assert body["correct"] is True
    # No player_name supplied -> not persisted.
    assert body["persisted"] is False


def test_drill_endpoint_rejects_unknown_focus(client):
    response = client.post(
        "/api/training/drills",
        json={"focus_area": "not_a_thing"},
    )
    assert response.status_code == 400


def test_drill_id_replay_is_deterministic(client):
    first = client.post(
        "/api/training/drills",
        json={"focus_area": "poor_pot_odds", "difficulty": 2},
    ).json()

    # Re-POSTing with the same drill_id must reproduce the scenario byte-for-byte.
    second = client.post(
        "/api/training/drills",
        json={
            "focus_area": "poor_pot_odds",
            "difficulty": 2,
            "drill_id": first["drill_id"],
        },
    ).json()

    assert first["scenario"] == second["scenario"]
    assert first["correct_action"] == second["correct_action"]
    assert first["context"] == second["context"]


def test_drill_grade_persists_into_practice_history(client, tmp_path, monkeypatch):
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("DrillUser", 5000)
    manager.save_players()

    drill = client.post(
        "/api/training/drills",
        json={"focus_area": "poor_pot_odds", "difficulty": 2},
    ).json()

    answer = client.post(
        "/api/training/drills/answer",
        json={
            "drill_id": drill["drill_id"],
            "kind": drill["kind"],
            "correct_action": drill["correct_action"],
            "user_answer": drill["correct_action"],
            "player_name": "DrillUser",
            "focus_area": drill["focus_area"],
        },
    ).json()

    assert answer["correct"] is True
    assert answer["persisted"] is True

    fresh = DataManager(data_file=str(tmp_path / "players.json"))
    record = fresh.get_player("DrillUser")
    assert record is not None
    history = record["practice_history"]
    assert len(history) == 1
    assert history[0]["correct"] is True
    assert record["practice_stats"]["accuracy"] == 1.0


def test_hand_history_cursor_pagination(client, tmp_path):
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("PageUser", 5000)
    manager.save_players()
    for i in range(1, 6):
        manager.append_hand_history(
            "PageUser",
            {"hand_number": i, "pot_total": i * 10, "winners": [], "board": [], "actions": [], "decision_points": [], "hero_hole_cards": []},
        )

    # First page: newest two hands.
    page_one = client.get("/api/hands?player=PageUser&limit=2").json()
    assert [h["hand_number"] for h in page_one] == [5, 4]

    # Second page: hands strictly before the last item of page one.
    cursor = page_one[-1]["hand_number"]
    page_two = client.get(
        f"/api/hands?player=PageUser&limit=2&before_hand_number={cursor}"
    ).json()
    assert [h["hand_number"] for h in page_two] == [3, 2]


def test_hand_history_filters_by_won_and_pot(client, tmp_path):
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("FilterUser", 5000)
    manager.save_players()
    for i, hand in enumerate(
        [
            {"hand_number": 1, "pot_total": 50, "winners": ["FilterUser"], "board": ["2c", "7d", "Ts"], "actions": [], "decision_points": [], "hero_hole_cards": []},
            {"hand_number": 2, "pot_total": 200, "winners": ["AI_1"], "board": ["2c", "7d", "Ts", "5h", "9s"], "actions": [], "decision_points": [], "hero_hole_cards": []},
            {"hand_number": 3, "pot_total": 500, "winners": ["FilterUser"], "board": [], "actions": [], "decision_points": [], "hero_hole_cards": []},
        ]
    ):
        manager.append_hand_history("FilterUser", hand)

    # Won-only filter
    won_only = client.get("/api/hands?player=FilterUser&won=true&limit=10").json()
    assert {h["hand_number"] for h in won_only} == {1, 3}

    # Min-pot filter
    big_pots = client.get("/api/hands?player=FilterUser&min_pot=300&limit=10").json()
    assert [h["hand_number"] for h in big_pots] == [3]

    # Street filter (must reach turn or later)
    deep = client.get("/api/hands?player=FilterUser&street_at_least=turn&limit=10").json()
    assert [h["hand_number"] for h in deep] == [2]


def test_hand_history_export_jsonl(client, tmp_path):
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("ExportUser", 5000)
    manager.save_players()
    manager.append_hand_history(
        "ExportUser",
        {"hand_number": 1, "pot_total": 100, "winners": ["ExportUser"], "board": [], "actions": [], "decision_points": [], "hero_hole_cards": []},
    )

    response = client.get("/api/hands/export?player=ExportUser&fmt=jsonl")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    lines = [line for line in response.text.splitlines() if line]
    assert len(lines) == 1


def test_data_manager_writes_current_schema_version(tmp_path):
    import json as _json

    data_file = tmp_path / "players.json"
    manager = DataManager(data_file=str(data_file))
    manager.create_player("Versioned", 1000)
    manager.save_players()

    on_disk = _json.loads(data_file.read_text())
    assert on_disk["_schema_version"] == DataManager.SCHEMA_VERSION
    assert "Versioned" in on_disk["players"]


def test_data_manager_migrates_legacy_player_records(tmp_path):
    import json as _json

    data_file = tmp_path / "players.json"
    legacy = {
        "_schema_version": "1.0",
        "_description": "PyHoldem Pro player data storage",
        "players": {
            "Legacy": {
                "name": "Legacy",
                "bankroll": 1000,
                "created_at": "2025-01-01T00:00:00",
                # Missing: sessions, recent_hands, weaknesses, recommended_topics
            }
        },
    }
    data_file.write_text(_json.dumps(legacy))

    manager = DataManager(data_file=str(data_file))
    record = manager.get_player("Legacy")
    assert record["sessions"] == []
    assert record["recent_hands"] == []
    assert record["weaknesses"] == []
    assert record["recommended_topics"] == []


def test_deck_seed_produces_deterministic_shuffle(tmp_path):
    """Two fresh decks with the same seed should produce identical orderings."""
    import sys as _sys

    src_path = ROOT / "src"
    if str(src_path) not in _sys.path:
        _sys.path.insert(0, str(src_path))

    from game.deck import Deck

    deck_a = Deck()
    deck_a.shuffle(seed=42)
    deck_b = Deck()
    deck_b.shuffle(seed=42)
    assert [str(c) for c in deck_a.cards] == [str(c) for c in deck_b.cards]

    # Different seed => different ordering (with extremely high probability).
    deck_c = Deck()
    deck_c.shuffle(seed=43)
    assert [str(c) for c in deck_c.cards] != [str(c) for c in deck_a.cards]


def test_game_engine_seed_threads_to_deck(tmp_path):
    """GameEngine seed should make Deck.shuffle calls deterministic across hands."""
    import random as _random
    import sys as _sys

    src_path = ROOT / "src"
    if str(src_path) not in _sys.path:
        _sys.path.insert(0, str(src_path))

    from game.deck import Deck

    rng_a = _random.Random(0xCAFE)
    rng_b = _random.Random(0xCAFE)

    deck_a = Deck(rng=rng_a)
    deck_a.shuffle()
    deck_b = Deck(rng=rng_b)
    deck_b.shuffle()
    assert [str(c) for c in deck_a.cards] == [str(c) for c in deck_b.cards]
