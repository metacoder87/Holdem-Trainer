"""Tests for variance, all-in adjustment, RoR, Kelly."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.services.variance_analytics import (
    AllInAdjustment,
    WinrateStats,
    adjust_for_luck,
    adjust_session_profits,
    cumulative_lines,
    rolling_bb100,
    winrate_stats,
)


# ---------- adjust_for_luck ----------


def test_adjust_for_luck_empty_input():
    adj = adjust_for_luck([])
    assert adj.realized_chips == 0.0
    assert adj.ev_chips == 0.0
    assert adj.luck_chips == 0.0
    assert adj.decision_count == 0
    assert adj.sample_adequate is False


def test_adjust_for_luck_zero_luck_when_realized_equals_ev():
    decisions = [
        {"chosen_ev_chips": 100, "realized_chips": 100},
        {"chosen_ev_chips": -50, "realized_chips": -50},
    ]
    adj = adjust_for_luck(decisions, big_blind=10)
    assert adj.luck_chips == 0.0
    assert adj.luck_bb == 0.0
    assert adj.decision_count == 2


def test_adjust_for_luck_positive_luck():
    """Realized > EV -> hero got lucky."""
    decisions = [
        {"chosen_ev_chips": 100, "realized_chips": 200},
        {"chosen_ev_chips": 50, "realized_chips": 50},
    ]
    adj = adjust_for_luck(decisions, big_blind=10)
    assert adj.luck_chips == 100.0
    assert adj.luck_bb == 10.0


def test_adjust_for_luck_negative_luck():
    decisions = [
        {"chosen_ev_chips": 100, "realized_chips": -50},
    ]
    adj = adjust_for_luck(decisions, big_blind=10)
    assert adj.luck_chips == -150.0
    assert adj.luck_bb == -15.0


def test_adjust_for_luck_skips_decisions_without_ev():
    decisions = [
        {"chosen_ev_chips": 100, "realized_chips": 110},
        {"realized_chips": 50},  # no chosen_ev_chips -> skipped
    ]
    adj = adjust_for_luck(decisions)
    assert adj.decision_count == 1


def test_adjust_for_luck_sample_adequate_flag():
    short = [{"chosen_ev_chips": 1, "realized_chips": 1}] * 3
    long = [{"chosen_ev_chips": 1, "realized_chips": 1}] * 10
    assert adjust_for_luck(short).sample_adequate is False
    assert adjust_for_luck(long).sample_adequate is True


def test_adjust_for_luck_handles_garbage_values():
    decisions = [
        {"chosen_ev_chips": "not-a-number", "realized_chips": 10},
        {"chosen_ev_chips": float("inf"), "realized_chips": 10},
        {"chosen_ev_chips": 10, "realized_chips": float("nan")},
    ]
    adj = adjust_for_luck(decisions)
    # NaN/inf get coerced to 0 by _safe_float; we just want no crash.
    assert math.isfinite(adj.luck_chips)


# ---------- adjust_session_profits ----------


def test_adjust_session_profits_passes_through_when_no_decisions():
    sessions = [{"id": "s1", "profit": 100, "decision_points": []}]
    out = adjust_session_profits(sessions)
    assert len(out) == 1
    assert out[0]["ev_profit_chips"] is None
    assert out[0]["luck_bb"] is None
    assert out[0]["profit"] == 100  # unchanged


def test_adjust_session_profits_annotates_when_decisions_present():
    sessions = [
        {
            "id": "s1",
            "profit": 100,
            "decision_points": [
                {"chosen_ev_chips": 100, "realized_chips": 150},
                {"chosen_ev_chips": 0, "realized_chips": -50},
            ],
        }
    ]
    out = adjust_session_profits(sessions, big_blind=10)
    assert out[0]["ev_profit_chips"] == 100.0
    assert out[0]["luck_bb"] == 0.0  # realized 100 - ev 100


def test_adjust_session_profits_searches_nested_hand_history():
    sessions = [
        {
            "id": "s1",
            "hands": [
                {"decision_points": [{"chosen_ev_chips": 50, "realized_chips": 50}]},
                {"decision_points": [{"chosen_ev_chips": 20, "realized_chips": 30}]},
            ],
        }
    ]
    out = adjust_session_profits(sessions, big_blind=10)
    assert out[0]["ev_profit_chips"] == 70.0
    assert out[0]["luck_bb"] == 1.0  # +10 realized vs +0 expected luck-contrib


# ---------- rolling_bb100 ----------


def test_rolling_bb100_empty():
    assert rolling_bb100([], []) == []


def test_rolling_bb100_single_session_uses_just_that_session():
    out = rolling_bb100([100.0], [100], window=5)
    assert len(out) == 1
    assert out[0]["value"] == 100.0  # 100 BBs over 100 hands = 100 BB/100
    assert out[0]["window_hands"] == 100


def test_rolling_bb100_averages_over_window():
    profits = [100.0, -100.0, 200.0]
    hands = [100, 100, 100]
    out = rolling_bb100(profits, hands, window=2)
    # Window 2: index 1 averages sessions [0, 1] = 0 BBs / 200 hands = 0
    assert out[0]["value"] == 100.0
    assert math.isclose(out[1]["value"], 0.0, abs_tol=1e-9)
    # Index 2 = avg of [-100, 200] / 200 hands * 100 = 50
    assert math.isclose(out[2]["value"], 50.0, abs_tol=1e-9)


def test_rolling_bb100_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        rolling_bb100([1.0, 2.0], [100])


# ---------- winrate_stats ----------


def test_winrate_stats_empty():
    s = winrate_stats([], [])
    assert s.mean_bb100 == 0.0
    assert s.std_bb100 == 0.0
    assert s.session_count == 0
    assert s.risk_of_ruin is None
    assert s.kelly_fraction is None


def test_winrate_stats_mean_matches_pooled():
    profits = [100.0, 50.0, -30.0]
    hands = [200, 100, 100]
    s = winrate_stats(profits, hands)
    expected = (sum(profits) / sum(hands)) * 100.0
    assert math.isclose(s.mean_bb100, expected, abs_tol=1e-9)


def test_winrate_stats_std_zero_when_all_sessions_match():
    profits = [50.0, 50.0, 50.0]
    hands = [100, 100, 100]
    s = winrate_stats(profits, hands)
    assert math.isclose(s.std_bb100, 0.0, abs_tol=1e-9)


def test_winrate_stats_risk_of_ruin_only_when_positive_mean():
    """Losing player -> RoR isn't a meaningful number."""
    profits = [-50.0, -30.0]
    hands = [100, 100]
    s = winrate_stats(profits, hands, bankroll_bbs=1000)
    assert s.risk_of_ruin is None
    assert s.kelly_fraction is None


def _realistic_sessions():
    """4 sessions of 1000 hands each with poker-typical variance (~100 BB/100 std).

    Mean BB/100 = (50 + 200 - 80 + 100) / 4000 * 100 = 6.75.
    Per-session BB/100 = [5, 20, -8, 10], stdev ~~12. Realistic-low.
    """
    profits = [50.0, 200.0, -80.0, 100.0]
    hands = [1000, 1000, 1000, 1000]
    return profits, hands


def test_winrate_stats_risk_of_ruin_within_zero_one():
    """Winning player with realistic variance -> RoR in (0, 1)."""
    profits, hands = _realistic_sessions()
    s = winrate_stats(profits, hands, bankroll_bbs=300)
    assert s.risk_of_ruin is not None
    assert 0.0 < s.risk_of_ruin <= 1.0


def test_winrate_stats_risk_of_ruin_shrinks_with_bigger_bankroll():
    profits, hands = _realistic_sessions()
    s_small = winrate_stats(profits, hands, bankroll_bbs=100)
    s_big = winrate_stats(profits, hands, bankroll_bbs=10000)
    # Both might be very small; we just check ordering.
    assert s_big.risk_of_ruin <= s_small.risk_of_ruin


def test_winrate_stats_kelly_positive_for_winning_player():
    profits, hands = _realistic_sessions()
    s = winrate_stats(profits, hands, bankroll_bbs=1000)
    assert s.kelly_fraction is not None
    assert s.kelly_fraction > 0.0


# ---------- cumulative_lines ----------


def test_cumulative_lines_basic():
    profits = [100.0, -50.0, 30.0]
    luck = [10.0, -20.0, 5.0]
    out = cumulative_lines(profits, luck)
    assert len(out) == 3
    assert out[0]["realized"] == 100.0
    assert out[0]["ev"] == 90.0  # realized 100 minus luck 10
    assert out[1]["realized"] == 50.0
    assert out[2]["realized"] == 80.0


def test_cumulative_lines_ev_is_none_when_any_luck_missing():
    profits = [100.0, 50.0]
    luck = [10.0, None]
    out = cumulative_lines(profits, luck)
    assert out[0]["ev"] == 90.0
    assert out[1]["ev"] is None
