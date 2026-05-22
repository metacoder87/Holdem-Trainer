"""Tests for poker.fast_eval — 7-card hand ranking via lookup table.

The point of these tests is to pin the *ordering* invariants the
evaluator must respect. We don't try to enumerate every rank
class; instead we assert:
  - Stronger hands get lower rank ints than weaker hands.
  - Same-class hands tie-break correctly on kickers/high card.
  - Class names match the rank ranges.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from game.card import Card, Rank, Suit
from poker.fast_eval import (
    fast_evaluate,
    fast_evaluate_5,
    rank_class,
    winner_from_hands,
)


def C(rank: Rank, suit: Suit) -> Card:
    return Card(suit, rank)


# Common test hands ----------------------------------------------------------

ROYAL_FLUSH_SPADES = [
    C(Rank.ACE, Suit.SPADES),
    C(Rank.KING, Suit.SPADES),
    C(Rank.QUEEN, Suit.SPADES),
    C(Rank.JACK, Suit.SPADES),
    C(Rank.TEN, Suit.SPADES),
]

STRAIGHT_FLUSH_5_HIGH = [
    C(Rank.FIVE, Suit.HEARTS),
    C(Rank.FOUR, Suit.HEARTS),
    C(Rank.THREE, Suit.HEARTS),
    C(Rank.TWO, Suit.HEARTS),
    C(Rank.ACE, Suit.HEARTS),
]

FOUR_ACES_K_KICKER = [
    C(Rank.ACE, Suit.SPADES),
    C(Rank.ACE, Suit.HEARTS),
    C(Rank.ACE, Suit.DIAMONDS),
    C(Rank.ACE, Suit.CLUBS),
    C(Rank.KING, Suit.SPADES),
]

FULL_HOUSE_KINGS_FULL_TWOS = [
    C(Rank.KING, Suit.SPADES),
    C(Rank.KING, Suit.HEARTS),
    C(Rank.KING, Suit.DIAMONDS),
    C(Rank.TWO, Suit.SPADES),
    C(Rank.TWO, Suit.HEARTS),
]

ACE_HIGH_FLUSH = [
    C(Rank.ACE, Suit.DIAMONDS),
    C(Rank.JACK, Suit.DIAMONDS),
    C(Rank.NINE, Suit.DIAMONDS),
    C(Rank.SIX, Suit.DIAMONDS),
    C(Rank.THREE, Suit.DIAMONDS),
]

BROADWAY_STRAIGHT = [
    C(Rank.ACE, Suit.SPADES),
    C(Rank.KING, Suit.HEARTS),
    C(Rank.QUEEN, Suit.DIAMONDS),
    C(Rank.JACK, Suit.CLUBS),
    C(Rank.TEN, Suit.SPADES),
]

THREE_KINGS = [
    C(Rank.KING, Suit.SPADES),
    C(Rank.KING, Suit.HEARTS),
    C(Rank.KING, Suit.DIAMONDS),
    C(Rank.SEVEN, Suit.CLUBS),
    C(Rank.TWO, Suit.SPADES),
]

TWO_PAIR_AK = [
    C(Rank.ACE, Suit.SPADES),
    C(Rank.ACE, Suit.HEARTS),
    C(Rank.KING, Suit.DIAMONDS),
    C(Rank.KING, Suit.CLUBS),
    C(Rank.TWO, Suit.HEARTS),
]

PAIR_OF_ACES = [
    C(Rank.ACE, Suit.SPADES),
    C(Rank.ACE, Suit.HEARTS),
    C(Rank.NINE, Suit.DIAMONDS),
    C(Rank.SIX, Suit.CLUBS),
    C(Rank.TWO, Suit.SPADES),
]

ACE_HIGH = [
    C(Rank.ACE, Suit.SPADES),
    C(Rank.KING, Suit.HEARTS),
    C(Rank.QUEEN, Suit.DIAMONDS),
    C(Rank.JACK, Suit.CLUBS),
    C(Rank.NINE, Suit.SPADES),
]


# ---------- Class ordering ----------


def test_royal_flush_beats_everything():
    royal = fast_evaluate_5(ROYAL_FLUSH_SPADES)
    for hand in (
        FOUR_ACES_K_KICKER,
        FULL_HOUSE_KINGS_FULL_TWOS,
        ACE_HIGH_FLUSH,
        BROADWAY_STRAIGHT,
        THREE_KINGS,
        TWO_PAIR_AK,
        PAIR_OF_ACES,
        ACE_HIGH,
    ):
        assert royal < fast_evaluate_5(hand)


def test_class_strict_ordering():
    """Walk the standard class hierarchy and assert strict ordering."""
    ranks = [
        fast_evaluate_5(ROYAL_FLUSH_SPADES),       # straight flush
        fast_evaluate_5(FOUR_ACES_K_KICKER),       # four of a kind
        fast_evaluate_5(FULL_HOUSE_KINGS_FULL_TWOS),  # full house
        fast_evaluate_5(ACE_HIGH_FLUSH),           # flush
        fast_evaluate_5(BROADWAY_STRAIGHT),        # straight
        fast_evaluate_5(THREE_KINGS),              # three of a kind
        fast_evaluate_5(TWO_PAIR_AK),              # two pair
        fast_evaluate_5(PAIR_OF_ACES),             # one pair
        fast_evaluate_5(ACE_HIGH),                 # high card
    ]
    for i in range(len(ranks) - 1):
        assert ranks[i] < ranks[i + 1], (
            f"class {i} ({rank_class(ranks[i])}) should be stronger than "
            f"class {i+1} ({rank_class(ranks[i + 1])})"
        )


def test_rank_class_labels():
    assert rank_class(fast_evaluate_5(ROYAL_FLUSH_SPADES)) == "Straight Flush"
    assert rank_class(fast_evaluate_5(FOUR_ACES_K_KICKER)) == "Four of a Kind"
    assert rank_class(fast_evaluate_5(FULL_HOUSE_KINGS_FULL_TWOS)) == "Full House"
    assert rank_class(fast_evaluate_5(ACE_HIGH_FLUSH)) == "Flush"
    assert rank_class(fast_evaluate_5(BROADWAY_STRAIGHT)) == "Straight"
    assert rank_class(fast_evaluate_5(THREE_KINGS)) == "Three of a Kind"
    assert rank_class(fast_evaluate_5(TWO_PAIR_AK)) == "Two Pair"
    assert rank_class(fast_evaluate_5(PAIR_OF_ACES)) == "One Pair"
    assert rank_class(fast_evaluate_5(ACE_HIGH)) == "High Card"


# ---------- Tie-breakers within a class ----------


def test_higher_pair_beats_lower_pair():
    aces = fast_evaluate_5(PAIR_OF_ACES)
    pair_of_twos = [
        C(Rank.TWO, Suit.SPADES),
        C(Rank.TWO, Suit.HEARTS),
        C(Rank.KING, Suit.DIAMONDS),
        C(Rank.SEVEN, Suit.CLUBS),
        C(Rank.THREE, Suit.SPADES),
    ]
    assert aces < fast_evaluate_5(pair_of_twos)


def test_higher_kicker_beats_lower_kicker():
    aces_k_kicker = [
        C(Rank.ACE, Suit.SPADES), C(Rank.ACE, Suit.HEARTS),
        C(Rank.KING, Suit.DIAMONDS), C(Rank.SIX, Suit.CLUBS), C(Rank.TWO, Suit.SPADES),
    ]
    aces_q_kicker = [
        C(Rank.ACE, Suit.SPADES), C(Rank.ACE, Suit.HEARTS),
        C(Rank.QUEEN, Suit.DIAMONDS), C(Rank.SIX, Suit.CLUBS), C(Rank.TWO, Suit.SPADES),
    ]
    assert fast_evaluate_5(aces_k_kicker) < fast_evaluate_5(aces_q_kicker)


def test_wheel_straight_recognized():
    wheel = [
        C(Rank.FIVE, Suit.SPADES),
        C(Rank.FOUR, Suit.HEARTS),
        C(Rank.THREE, Suit.DIAMONDS),
        C(Rank.TWO, Suit.CLUBS),
        C(Rank.ACE, Suit.SPADES),
    ]
    assert rank_class(fast_evaluate_5(wheel)) == "Straight"


def test_wheel_straight_flush_recognized():
    assert rank_class(fast_evaluate_5(STRAIGHT_FLUSH_5_HIGH)) == "Straight Flush"


# ---------- 7-card evaluator ----------


def test_seven_card_picks_best_five():
    # 5 cards in hand: AA + flush draw — but board adds a 6th heart for flush.
    cards = [
        C(Rank.ACE, Suit.SPADES),
        C(Rank.ACE, Suit.HEARTS),
        C(Rank.TEN, Suit.HEARTS),
        C(Rank.NINE, Suit.HEARTS),
        C(Rank.FIVE, Suit.HEARTS),
        C(Rank.TWO, Suit.HEARTS),  # the 5th heart
        C(Rank.SEVEN, Suit.DIAMONDS),
    ]
    rank = fast_evaluate(cards)
    assert rank_class(rank) == "Flush"


def test_seven_card_full_house_over_two_pair():
    cards = [
        C(Rank.ACE, Suit.SPADES),
        C(Rank.ACE, Suit.HEARTS),
        C(Rank.ACE, Suit.DIAMONDS),
        C(Rank.KING, Suit.CLUBS),
        C(Rank.KING, Suit.SPADES),
        C(Rank.TWO, Suit.HEARTS),
        C(Rank.SEVEN, Suit.DIAMONDS),
    ]
    rank = fast_evaluate(cards)
    assert rank_class(rank) == "Full House"


def test_evaluate_requires_5_cards():
    with pytest.raises(ValueError):
        fast_evaluate([
            C(Rank.ACE, Suit.SPADES),
            C(Rank.KING, Suit.HEARTS),
        ])


def test_evaluate_5_requires_exactly_5():
    with pytest.raises(ValueError):
        fast_evaluate_5([C(Rank.ACE, Suit.SPADES)])


# ---------- winner_from_hands ----------


def test_winner_picks_best_hand_index():
    """4 players; player 0 has nut flush, others have pair.

    All players share a 5-card "board" (passed by the caller via the
    full 7-card holding). For this test we just verify the winner
    logic by giving each player 5-card hands directly.
    """
    winners = winner_from_hands([
        ROYAL_FLUSH_SPADES,
        PAIR_OF_ACES,
        ACE_HIGH,
        TWO_PAIR_AK,
    ])
    assert winners == [0]


def test_winner_returns_all_tied_indices():
    """Two players with the same hand class + same ranks tie."""
    aa1 = [
        C(Rank.ACE, Suit.SPADES), C(Rank.ACE, Suit.HEARTS),
        C(Rank.KING, Suit.DIAMONDS), C(Rank.SEVEN, Suit.CLUBS), C(Rank.TWO, Suit.SPADES),
    ]
    aa2 = [
        C(Rank.ACE, Suit.DIAMONDS), C(Rank.ACE, Suit.CLUBS),
        C(Rank.KING, Suit.HEARTS), C(Rank.SEVEN, Suit.SPADES), C(Rank.TWO, Suit.HEARTS),
    ]
    winners = winner_from_hands([aa1, aa2])
    assert set(winners) == {0, 1}


def test_winner_empty_returns_empty():
    assert winner_from_hands([]) == []
