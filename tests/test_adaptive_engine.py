"""Tests for the Track 4 adaptive engine.

Pins behavior of:
  - Thompson-sampling bandit (inverted: picks lowest expected acc)
  - SM-2 spaced repetition (intervals, ease, due rollover)
  - Elo updates (zero-sum, symmetric, K-factor bounded)
  - AdaptiveState round-trip serialization
"""
from __future__ import annotations

import math
import random
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.adaptive_engine import (
    AdaptiveState,
    BanditArm,
    DEFAULT_BETA_ALPHA,
    DEFAULT_BETA_BETA,
    DEFAULT_ELO_RATING,
    DEFAULT_TOPICS,
    EloPlayer,
    SrsCard,
    bandit_update,
    cards_due_for_review,
    elo_expected,
    elo_update,
    load_state,
    progression_summary,
    save_state,
    select_scenario_near,
    sm2_update,
    thompson_select,
)


# ---------- BanditArm ----------


def test_bandit_arm_default_expected_accuracy_is_half():
    arm = BanditArm(topic="x")
    assert math.isclose(arm.expected_accuracy(), 0.5)


def test_bandit_arm_credible_interval_contains_mean():
    arm = BanditArm(topic="x", alpha=10, beta=5)
    lo, hi = arm.credible_interval()
    assert lo <= arm.expected_accuracy() <= hi


def test_bandit_arm_round_trip_dict():
    arm = BanditArm(topic="vpip", alpha=3.0, beta=7.0, pulls=12)
    restored = BanditArm.from_dict(arm.to_dict())
    assert restored.topic == "vpip"
    assert restored.alpha == 3.0
    assert restored.beta == 7.0
    assert restored.pulls == 12


def test_bandit_update_increments_alpha_on_correct():
    arm = BanditArm(topic="x")
    bandit_update(arm, correct=True)
    assert arm.alpha == DEFAULT_BETA_ALPHA + 1
    assert arm.beta == DEFAULT_BETA_BETA
    assert arm.pulls == 1


def test_bandit_update_increments_beta_on_wrong():
    arm = BanditArm(topic="x")
    bandit_update(arm, correct=False)
    assert arm.alpha == DEFAULT_BETA_ALPHA
    assert arm.beta == DEFAULT_BETA_BETA + 1


def test_thompson_select_returns_an_arm_from_the_pool():
    arms = [BanditArm(topic=t) for t in ("a", "b", "c")]
    chosen = thompson_select(arms, rng=random.Random(7))
    assert chosen.topic in {"a", "b", "c"}


def test_thompson_select_biases_to_weaker_arm_over_many_pulls():
    """Over 500 picks, the arm with the worst posterior should be
    chosen most often. (Bandit picks lowest expected accuracy.)"""
    strong = BanditArm(topic="strong", alpha=40, beta=4)
    weak = BanditArm(topic="weak", alpha=4, beta=40)
    rng = random.Random(11)
    counts = {"strong": 0, "weak": 0}
    for _ in range(500):
        a = thompson_select([strong, weak], rng=rng)
        counts[a.topic] += 1
    # Weak arm should be chosen the overwhelming majority.
    assert counts["weak"] > counts["strong"] * 3


def test_thompson_select_rejects_empty_arms():
    with pytest.raises(ValueError):
        thompson_select([])


# ---------- SM-2 SRS ----------


def test_sm2_quality_5_increases_interval():
    card = SrsCard(card_id="pot-odds-1")
    sm2_update(card, quality=5, now_ts=0)
    assert card.repetitions == 1
    assert card.interval_days == 1.0
    sm2_update(card, quality=5, now_ts=86400)
    assert card.repetitions == 2
    assert card.interval_days == 6.0
    # Third success uses ease factor (~2.5).
    sm2_update(card, quality=5, now_ts=7 * 86400)
    assert card.repetitions == 3
    assert card.interval_days > 6.0


def test_sm2_quality_below_3_resets_repetitions():
    card = SrsCard(card_id="c", repetitions=5, interval_days=30.0)
    sm2_update(card, quality=1, now_ts=0)
    assert card.repetitions == 0
    assert card.interval_days == 0.0


def test_sm2_ease_factor_floored():
    card = SrsCard(card_id="c", ease_factor=1.4)
    for _ in range(10):
        sm2_update(card, quality=0)
    assert card.ease_factor >= 1.3


def test_sm2_ease_factor_grows_on_perfect_recall():
    card = SrsCard(card_id="c")
    initial = card.ease_factor
    sm2_update(card, quality=5)
    assert card.ease_factor > initial


def test_sm2_card_is_due_when_no_history():
    card = SrsCard(card_id="c")
    assert card.is_due()


def test_sm2_card_not_due_after_recent_review():
    card = SrsCard(card_id="c")
    sm2_update(card, quality=5, now_ts=time.time())
    assert not card.is_due()


def test_cards_due_for_review_filter():
    fresh = SrsCard(card_id="fresh")
    answered = SrsCard(card_id="answered")
    sm2_update(answered, quality=5, now_ts=time.time())
    due = cards_due_for_review([fresh, answered])
    assert fresh in due
    assert answered not in due


# ---------- Elo ----------


def test_elo_expected_symmetric():
    assert math.isclose(elo_expected(1500, 1500), 0.5)


def test_elo_higher_rated_has_higher_expected():
    assert elo_expected(1700, 1500) > elo_expected(1500, 1700)


def test_elo_update_zero_sum_when_player_wins():
    new_p, new_s = elo_update(1500, 1500, player_won=True, k_factor=32)
    assert math.isclose((new_p - 1500) + (new_s - 1500), 0.0, abs_tol=1e-9)


def test_elo_player_rating_rises_after_win():
    new_p, _ = elo_update(1500, 1500, player_won=True)
    assert new_p > 1500


def test_elo_player_rating_falls_after_loss():
    new_p, _ = elo_update(1500, 1500, player_won=False)
    assert new_p < 1500


def test_elo_update_bounded_by_k_factor():
    new_p, _ = elo_update(1500, 1500, player_won=True, k_factor=32)
    assert abs(new_p - 1500) <= 32


def test_select_scenario_near_picks_closest_rating():
    scenarios = [
        {"id": "a", "elo_rating": 1300},
        {"id": "b", "elo_rating": 1500},
        {"id": "c", "elo_rating": 1700},
    ]
    chosen = select_scenario_near(scenarios, player_rating=1480, window=200)
    assert chosen["id"] == "b"


def test_select_scenario_falls_back_when_window_excludes_all():
    scenarios = [{"id": "a", "elo_rating": 2000}]
    chosen = select_scenario_near(scenarios, player_rating=1000, window=100)
    assert chosen is not None
    assert chosen["id"] == "a"


def test_select_scenario_handles_empty():
    assert select_scenario_near([], player_rating=1500) is None


# ---------- AdaptiveState round-trip + integration ----------


def test_adaptive_state_fresh_has_default_topics():
    state = AdaptiveState.fresh()
    for topic in DEFAULT_TOPICS:
        assert topic in state.bandit
    assert state.player_elo.rating == DEFAULT_ELO_RATING


def test_adaptive_state_round_trip_via_dict():
    state = AdaptiveState.fresh()
    state.record_topic_result("pot_odds", correct=True)
    state.record_scenario_outcome("turn-decision-1", player_won=False)
    state.review_card("pot-odds-card", quality=4)

    serialized = state.to_dict()
    restored = AdaptiveState.from_dict(serialized)
    assert restored.bandit["pot_odds"].alpha == state.bandit["pot_odds"].alpha
    assert "turn-decision-1" in restored.scenario_elos
    assert restored.player_elo.attempts == 1
    assert "pot-odds-card" in restored.cards


def test_progression_summary_keys():
    state = AdaptiveState.fresh()
    state.record_topic_result("pot_odds", correct=True)
    summary = progression_summary(state)
    assert "bandit" in summary
    assert "next_topic" in summary
    assert "srs" in summary
    assert "elo" in summary


def test_load_state_handles_missing_record():
    assert isinstance(load_state(None), AdaptiveState)
    assert isinstance(load_state({}), AdaptiveState)


def test_load_state_round_trips_through_player_record():
    state = AdaptiveState.fresh()
    state.record_topic_result("pot_odds", correct=True)
    progress: dict = {}
    save_state(progress, state)
    record = {"training_progress": progress}
    restored = load_state(record)
    assert restored.bandit["pot_odds"].alpha == state.bandit["pot_odds"].alpha


def test_pick_topic_returns_a_valid_topic():
    state = AdaptiveState.fresh()
    topic = state.pick_topic(rng=random.Random(1))
    assert topic in state.bandit
