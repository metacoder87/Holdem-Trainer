"""Regression tests for the training+analytics Sprint A fixes.

Each test corresponds to a numbered item from docs/training-analytics-plan.md.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
BACKEND_PATH = ROOT / "backend"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from fastapi.testclient import TestClient

from data.manager import DataManager
from training.progression_analyzer import ProgressionAnalyzer, WeaknessType
from training.trainer import PokerTrainer, QuizType


# ----------------------------- 1.4 + 1.8 -----------------------------------


def test_identify_weaknesses_dedupes_too_passive():
    """Item 1.4 - low PFR and low AF used to emit TOO_PASSIVE twice."""
    analyzer = ProgressionAnalyzer()
    metrics = {
        "vpip": 0.24,
        "pfr": 0.02,  # low -> TOO_PASSIVE
        "aggression_factor": 0.5,  # also low -> TOO_PASSIVE
    }
    result = analyzer.identify_weaknesses(metrics)
    assert result.count(WeaknessType.TOO_PASSIVE) == 1


def test_identify_weaknesses_requires_pot_odds_sample():
    """Item 1.8 - new players (zero quizzes) should not be flagged."""
    analyzer = ProgressionAnalyzer()
    no_sample = {"vpip": 0.24, "pfr": 0.18, "aggression_factor": 2.0,
                 "pot_odds_accuracy": 0.0, "pot_odds_samples": 0}
    assert WeaknessType.POOR_POT_ODDS not in analyzer.identify_weaknesses(no_sample)

    enough_sample = {**no_sample, "pot_odds_accuracy": 0.30, "pot_odds_samples": 25}
    assert WeaknessType.POOR_POT_ODDS in analyzer.identify_weaknesses(enough_sample)


# ----------------------------- 1.9 -----------------------------------------


def test_aggression_factor_caps_at_finite_sentinel():
    """Item 1.9 - postflop_raises > 0 with postflop_calls == 0 must not
    serialize as float('inf') (invalid in strict JSON parsers).
    """
    from stats.session_tracker import SessionMetrics

    metrics = SessionMetrics(
        player_name="Test",
        game_type="cash",
        limit_type="no_limit",
        bankroll_start=1000,
        bankroll_end=1000,
        small_blind=5,
        big_blind=10,
        postflop_raises=3,
        postflop_calls=0,
        hands_played=10,
    )
    out = metrics.to_dict()
    af = out["aggression_factor"]
    import math

    assert math.isfinite(af)
    assert af == SessionMetrics.AF_INFINITE_SENTINEL


# ----------------------------- 1.1 -----------------------------------------


def test_required_equity_quiz_distinct_from_pot_odds():
    """Item 1.1 - the two quiz types now train different formulas."""
    trainer = PokerTrainer()
    pot_odds = trainer.generate_quiz(QuizType.POT_ODDS, pot_size=100, bet_to_call=25)

    # Sample 5 required-equity quizzes; with fold_equity randomized in
    # [0.10, 0.50] the answers should differ from raw pot odds.
    different = 0
    for _ in range(5):
        req_eq = trainer.generate_quiz(QuizType.REQUIRED_EQUITY, pot_size=100, bet_to_call=25)
        if req_eq["correct_answer"] != pot_odds["correct_answer"]:
            different += 1
    assert different >= 4, "Required-equity should generally diverge from pot odds"


# ----------------------------- 1.5 -----------------------------------------


def test_quiz_type_weighting_biases_toward_unmastered():
    """Item 1.5 - per-topic mastery should up-weight under-trained topics."""
    trainer = PokerTrainer()
    trainer.enable_training()

    # Simulate the user being perfect at POT_ODDS and terrible at BET_SIZING.
    for _ in range(20):
        trainer.record_topic_result(QuizType.POT_ODDS, correct=True)
        trainer.record_topic_result(QuizType.BET_SIZING, correct=False)

    counts = {q: 0 for q in trainer.quiz_types}
    import random as _random
    _random.seed(42)
    for _ in range(500):
        counts[trainer.get_random_quiz_type()] += 1

    # BET_SIZING is at 0% mastery, POT_ODDS at 100%. Mastered topics get the
    # 0.2 floor weight; un-mastered get weight 1.0. Expect bet sizing to be
    # picked materially more often.
    assert counts[QuizType.BET_SIZING] > counts[QuizType.POT_ODDS] * 2


# ----------------------------- 1.8 + 1.10 (API surface) -----------------------


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    from app.main import app
    from app.services import game_service

    game_service.SESSIONS.clear()
    return TestClient(app)


def test_analytics_leaks_silent_on_small_sample(client, tmp_path):
    """Item 1.8 - small samples should suppress leak flags entirely."""
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("Rookie", 5000)
    # 5 hands total: below MIN_HANDS_FOR_LEAK_DETECTION (50).
    manager.update_player_stats(
        "Rookie",
        {"sessions": [{"hands_played": 5, "vpip": 0.0, "pfr": 0.0, "aggression_factor": 0.0}]},
    )
    manager.save_players()

    response = client.get("/api/analytics/leaks?player=Rookie")
    assert response.status_code == 200
    payload = response.json()
    assert payload["leaks"] == []
    assert "note" in payload  # tells the user why


def test_analytics_summary_surfaces_sample_counts(client, tmp_path):
    """Frontend uses these counts to gate "high severity" labels client-side."""
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("Sampled", 5000)
    manager.update_player_stats(
        "Sampled",
        {"sessions": [
            {"hands_played": 80, "vpip": 0.24, "pfr": 0.18, "aggression_factor": 2.0,
             "pot_odds_quizzes": 5, "decisions_total": 60}
        ]},
    )
    manager.save_players()

    response = client.get("/api/analytics/summary?player=Sampled").json()
    assert "samples" in response
    assert response["samples"]["hands"] == 80
    assert response["samples"]["pot_odds_quizzes"] == 5
    assert response["samples"]["decisions"] == 60


# ----------------------------- 3.7 -----------------------------------------


def test_summary_focus_queue_items_carry_focus_area_id(client, tmp_path):
    """Item 3.7 - the frontend needs `id` to deep-link into the drill engine."""
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("Leaky", 5000)
    manager.update_player_stats(
        "Leaky",
        {
            "sessions": [{"hands_played": 100, "vpip": 0.55, "pfr": 0.04, "aggression_factor": 0.5}],
            "weaknesses": ["too_loose", "too_passive"],
        },
    )
    manager.save_players()

    response = client.get("/api/summary?player=Leaky").json()
    items = response["focus_queue_items"]
    assert len(items) >= 2
    ids = {item["id"] for item in items if item.get("id")}
    assert "too_loose" in ids
    assert "too_passive" in ids


# ----------------------------- 3.8 -----------------------------------------


def test_quiz_evaluation_persists_per_player(client, tmp_path):
    """Item 3.8 - quiz attempts persist into quiz_history + quiz_stats."""
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("QuizUser", 5000)
    manager.save_players()

    response = client.post(
        "/api/training/quiz/evaluate",
        json={
            "correct_answer": 0.25,
            "user_answer": 0.25,
            "tolerance": 0.05,
            "player_name": "QuizUser",
            "quiz_type": "pot_odds",
        },
    ).json()
    assert response["correct"] is True
    assert response["persisted"] is True

    fresh = DataManager(data_file=str(tmp_path / "players.json"))
    record = fresh.get_player("QuizUser")
    assert len(record["quiz_history"]) == 1
    assert record["quiz_stats"]["total"] == 1
    assert record["quiz_stats"]["correct"] == 1
    assert record["quiz_stats"]["by_topic"]["pot_odds"]["correct"] == 1


def test_quiz_evaluation_without_player_name_is_not_persisted(client):
    """Anonymous evaluations should still grade but not persist."""
    response = client.post(
        "/api/training/quiz/evaluate",
        json={"correct_answer": 0.25, "user_answer": 0.25, "tolerance": 0.05},
    ).json()
    assert response["correct"] is True
    assert response["persisted"] is False
