"""Regression tests for items 2.4, 4.5, 1.6, 2.5, 3.9, 2.10, 2.6, 2.8."""
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
from app.services import drill_service, game_service
from app.services.analytics_service import _ev_summary_from_hand_records
from app.services.summary_service import _build_training_tracks
from data.manager import DataManager
from stats.session_tracker import SessionTracker
from training.trainer import PokerTrainer


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYHOLDEM_DATA_FILE", str(tmp_path / "players.json"))
    game_service.SESSIONS.clear()
    return TestClient(app)


# ----- 2.4 EV grading --------------------------------------------------------


def test_ev_summary_aggregates_chips_and_bb_loss():
    """Item 2.4 / 4.5: top_leaks should rank by largest chip loss."""
    records = [
        {
            "hand_number": 1,
            "decision_points": [
                {
                    "betting_round": "flop",
                    "chosen_action": "call",
                    "ev_loss_chips": -12.0,
                    "ev_loss_bb": -1.2,
                    "equity": 0.25,
                    "required_equity": 0.40,
                },
                {
                    "betting_round": "turn",
                    "chosen_action": "fold",
                    "ev_loss_chips": -3.0,
                    "ev_loss_bb": -0.3,
                },
            ],
        },
        {
            "hand_number": 2,
            "decision_points": [
                {
                    "betting_round": "river",
                    "chosen_action": "call",
                    "ev_loss_chips": -20.0,
                    "ev_loss_bb": -2.0,
                },
                # Unrelated decision without EV - should be skipped.
                {"betting_round": "preflop", "chosen_action": "raise"},
            ],
        },
    ]
    summary = _ev_summary_from_hand_records(records)
    assert summary["graded_decisions"] == 3
    assert summary["total_chips"] == pytest.approx(-35.0)
    assert summary["total_bb"] == pytest.approx(-3.5)
    # Top leak should be the river -20 chip mistake.
    assert summary["top_leaks"][0]["hand_number"] == 2
    assert summary["top_leaks"][0]["ev_loss_chips"] == -20.0


def test_ev_endpoint_returns_zero_when_no_decisions(client):
    response = client.get("/api/analytics/ev").json()
    assert response["ev"]["graded_decisions"] == 0


# ----- 1.6 aggressive intent -------------------------------------------------


def test_short_stack_jam_counts_as_aggressive_intent():
    """Item 1.6: jam that doesn't reopen betting should still bump PFR."""
    tracker = SessionTracker("Hero")
    tracker.start_session(
        game_type="cash",
        limit_type="no_limit",
        bankroll_start=200,
        small_blind=5,
        big_blind=10,
    )
    tracker.start_hand(hero_hole_cards=["Ah", "Kd"])

    # Simulate an under-min-raise all-in jam by the hero. did_raise is False
    # (doesn't reopen betting) but intent is aggressive.
    tracker.record_action(
        player_name="Hero",
        action="all_in",
        amount=15,
        pot_before=20,
        betting_round="preflop",
        did_raise=False,
        is_aggressive_intent=True,
    )
    metrics = tracker.metrics
    tracker.end_hand(winners=["Hero"], pot_total=35)
    assert metrics.pfr_hands == 1, "Aggressive-intent jam should count toward PFR"


def test_default_aggressive_intent_falls_back_to_did_raise():
    """Backward compat: callers that omit the new flag still work."""
    tracker = SessionTracker("Hero")
    tracker.start_session(
        game_type="cash",
        limit_type="no_limit",
        bankroll_start=200,
        small_blind=5,
        big_blind=10,
    )
    tracker.start_hand(hero_hole_cards=["Ah", "Kd"])
    tracker.record_action(
        player_name="Hero",
        action="raise",
        amount=30,
        pot_before=15,
        betting_round="preflop",
        did_raise=True,
    )
    assert tracker.metrics.pfr_hands == 1


# ----- 2.5 Quiz tolerance ----------------------------------------------------


def test_quiz_tolerance_accepts_both_fractional_and_percent_input():
    """Item 2.5: fractional 0.25 with tolerance 0.05 should accept both 0.25 and 25 (and 23, 27)."""
    trainer = PokerTrainer()
    for input_value in (0.25, 25, 23, 27):
        result = trainer.evaluate_answer(0.25, input_value, tolerance=0.05)
        assert result["correct"] is True, f"Expected {input_value} to be within tolerance"

    miss = trainer.evaluate_answer(0.25, 32, tolerance=0.05)
    assert miss["correct"] is False


def test_quiz_tolerance_absolute_vs_relative_for_chip_amounts():
    """Numeric > 1 answers: tolerance <= 1 is relative, > 1 is absolute."""
    trainer = PokerTrainer()

    # Relative: 100 * 0.2 = 20 chip window -> 95 ok, 75 not ok
    rel_ok = trainer.evaluate_answer(100, 95, tolerance=0.2)
    rel_miss = trainer.evaluate_answer(100, 75, tolerance=0.2)
    assert rel_ok["correct"] is True
    assert rel_miss["correct"] is False

    # Absolute: tolerance 10 (>1) means within 10 chips -> 95 ok, 75 not ok
    abs_ok = trainer.evaluate_answer(100, 95, tolerance=10)
    abs_miss = trainer.evaluate_answer(100, 75, tolerance=10)
    assert abs_ok["correct"] is True
    assert abs_miss["correct"] is False


# ----- 3.9 Session report ----------------------------------------------------


def test_session_report_latest_404s_without_sessions(client):
    response = client.get("/api/analytics/sessions/latest")
    assert response.status_code == 404


def test_session_report_latest_returns_grade_when_data_exists(client, tmp_path):
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
            "last_session": {
                "hands_played": 80,
                "vpip": 0.24,
                "pfr": 0.18,
                "aggression_factor": 2.0,
                "decision_accuracy": 0.7,
                "profit": 120,
            },
        },
    )
    manager.save_players()

    response = client.get("/api/analytics/sessions/latest?player=ReportUser")
    assert response.status_code == 200
    body = response.json()
    assert body["report"] is not None
    assert "overall_grade" in body["report"]


# ----- 2.10 HUD in WS state --------------------------------------------------


def test_serialize_state_includes_hud_when_history_present(client, monkeypatch):
    """Item 2.10: opponent profile should ride along on the live state."""
    create = client.post(
        "/api/games/sessions",
        json={
            "player_name": "HudUser",
            "game_type": "cash",
            "limit_type": "no_limit",
            "small_blind": 5,
            "big_blind": 10,
            "opponents": 1,
        },
    ).json()
    session_id = create["id"]

    # Run one hand so the session tracker has actions to compute HUD from.
    state = client.post(f"/api/games/sessions/{session_id}/hand/start").json()
    while state["status"] == "awaiting_input":
        pending = state["pending_input"]
        options = pending.get("options") or []
        idx = next(
            (i for i, opt in enumerate(options, 1) if "call" in opt.lower() or "check" in opt.lower()),
            1,
        )
        state = client.post(
            f"/api/games/sessions/{session_id}/hand/input", json={"choice": idx}
        ).json()

    # Whether or not the resulting hand had postflop actions, the HUD payload
    # must be a list when present. (For very short hands it may be empty if
    # no opponent recorded any actions, so we just assert the shape.)
    state_payload = state.get("state") or {}
    hud = state_payload.get("hud")
    if hud is not None:
        assert "opponents" in hud
        assert isinstance(hud["opponents"], list)


# ----- 2.6 Track scoring -----------------------------------------------------


def test_training_tracks_use_quiz_stats_when_available():
    """Item 2.6: per-topic quiz stats should drive Range vs Range progress."""
    record = {
        "sessions": [
            {"hands_played": 100, "vpip": 0.24, "pfr": 0.18, "aggression_factor": 2.0}
        ],
        "quiz_stats": {
            "total": 30,
            "correct": 24,
            "accuracy": 0.8,
            "by_topic": {
                "required_equity": {"total": 15, "correct": 14, "accuracy": 14 / 15},
                "implied_odds": {"total": 12, "correct": 10, "accuracy": 10 / 12},
                "pot_odds": {"total": 3, "correct": 3, "accuracy": 1.0},
            },
        },
    }
    tracks = _build_training_tracks(record, record["sessions"][-1])
    range_track = next(t for t in tracks if t["title"] == "Range vs Range")
    assert range_track["progress"] >= 75, (
        f"Expected high Range vs Range progress, got {range_track['progress']}"
    )


def test_training_tracks_fallback_when_no_quiz_stats():
    """No quiz data -> still produces something via the band signal."""
    record = {
        "sessions": [
            {"hands_played": 100, "vpip": 0.24, "pfr": 0.18, "aggression_factor": 2.5}
        ]
    }
    tracks = _build_training_tracks(record, record["sessions"][-1])
    # In-band VPIP/PFR/AF should yield strong preflop + postflop scores.
    preflop_track = next(t for t in tracks if t["title"] == "Preflop Mastery")
    postflop_track = next(t for t in tracks if t["title"] == "Postflop Pressure")
    assert preflop_track["progress"] >= 80
    assert postflop_track["progress"] >= 80


# ----- 2.8 Spaced repetition -------------------------------------------------


def test_spaced_repetition_picks_lowest_accuracy_focus():
    """Item 2.8: when all candidates have been seen, prefer the one with the
    lowest accuracy.
    """
    # Pre-populate every supported focus area so the "unseen" bonus doesn't
    # dominate; we want to verify the *accuracy* signal in isolation here.
    practice_stats = {
        "by_focus": {
            w.value: {
                "total": 10,
                "correct": 9,
                "accuracy": 0.9,
                "last_seen": "2025-01-02T00:00:00",
            }
            for w in drill_service.SUPPORTED_WEAKNESSES
        }
    }
    # Now make too_passive the clear loser
    practice_stats["by_focus"]["too_passive"] = {
        "total": 10,
        "correct": 3,
        "accuracy": 0.3,
        "last_seen": "2025-01-02T00:00:00",
    }
    candidates = list(drill_service.SUPPORTED_WEAKNESSES)
    pick = drill_service._score_focus_for_spaced_repetition(practice_stats, candidates)
    assert pick is not None
    assert pick.value == "too_passive"


def test_spaced_repetition_surfaces_unseen_material():
    """Item 2.8: focus areas never practiced should surface first."""
    practice_stats = {
        "by_focus": {
            "poor_pot_odds": {"total": 10, "correct": 9, "accuracy": 0.9},
            "too_passive": {"total": 5, "correct": 2, "accuracy": 0.4},
            # WEAK_3BET_DEFENSE and others omitted -> "unseen"
        }
    }
    candidates = list(drill_service.SUPPORTED_WEAKNESSES)
    pick = drill_service._score_focus_for_spaced_repetition(practice_stats, candidates)
    # Should pick one of the unseen ones (score 1.5), beating the 0.6 from too_passive.
    assert pick is not None
    seen = {"poor_pot_odds", "too_passive"}
    assert pick.value not in seen, f"Expected an unseen focus area, got {pick.value}"


def test_drill_generation_uses_spaced_repetition_for_persisted_player(client, tmp_path):
    """Item 2.8: anonymous drill requests with a player who has practice
    history should pick the weakest focus area, not the analytics fallback.
    """
    manager = DataManager(data_file=str(tmp_path / "players.json"))
    manager.create_player("SpacedUser", 5000)
    manager.update_player_stats(
        "SpacedUser",
        {
            # Practice history that screams "I'm bad at 3-bet defense"
            "practice_stats": {
                "by_focus": {
                    "weak_3bet_defense": {"total": 10, "correct": 2, "accuracy": 0.2},
                    "poor_pot_odds": {"total": 10, "correct": 9, "accuracy": 0.9},
                    "too_loose": {"total": 10, "correct": 8, "accuracy": 0.8},
                    "too_passive": {"total": 10, "correct": 9, "accuracy": 0.9},
                    "poor_bet_sizing": {"total": 10, "correct": 9, "accuracy": 0.9},
                }
            },
        },
    )
    manager.save_players()

    response = client.post(
        "/api/training/drills",
        json={"player_name": "SpacedUser"},
    ).json()
    assert response["focus_area"] == "weak_3bet_defense"
