"""
Tests for decision-point capture in SessionTracker.
"""

from stats.session_tracker import SessionTracker


def test_record_decision_updates_hand_and_metrics():
    tracker = SessionTracker("Hero")
    tracker.start_session(
        game_type="cash",
        limit_type="no_limit",
        bankroll_start=1000,
        small_blind=5,
        big_blind=10,
    )
    tracker.start_hand(hero_hole_cards=["A♠", "K♦"], hand_meta={"game_type": "cash"})

    tracker.record_decision(
        {
            "betting_round": "preflop",
            "chosen_action": "call",
            "chosen_amount": 10,
            "quality": "optimal",
        }
    )
    tracker.record_action(
        player_name="Hero",
        action="call",
        amount=10,
        pot_before=15,
        betting_round="preflop",
        did_raise=False,
    )

    assert tracker.hand_history[-1]["decision_points"][0]["decision_number"] == 1
    assert tracker.hand_history[-1]["actions"][0]["pot_after"] == 25

    tracker.end_hand(winners=["Hero"], pot_total=25)
    metrics = tracker.finalize(bankroll_end=1010)

    assert metrics["decisions_total"] == 1
    assert metrics["decisions_optimal"] == 1
    assert metrics["decision_accuracy"] == 1.0


def test_set_board_tracks_board_by_street():
    tracker = SessionTracker("Hero")
    tracker.start_session(
        game_type="cash",
        limit_type="no_limit",
        bankroll_start=1000,
        small_blind=5,
        big_blind=10,
    )
    tracker.start_hand(hero_hole_cards=["A♠", "K♦"])

    tracker.set_board(["2♥", "7♥", "K♠"])
    assert tracker.hand_history[-1]["board_by_street"]["flop"] == ["2♥", "7♥", "K♠"]

    tracker.set_board(["2♥", "7♥", "K♠", "Q♦"])
    assert tracker.hand_history[-1]["board_by_street"]["turn"] == ["2♥", "7♥", "K♠", "Q♦"]

    tracker.set_board(["2♥", "7♥", "K♠", "Q♦", "A♦"])
    assert tracker.hand_history[-1]["board_by_street"]["river"] == ["2♥", "7♥", "K♠", "Q♦", "A♦"]

