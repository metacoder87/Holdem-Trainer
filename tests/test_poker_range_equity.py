"""Tests for poker.range_equity — multiway equity with card removal.

These pin the *invariants* the equity calculator must respect:
  - Equities sum to 1 (with rounding tolerance).
  - Pocket aces beat pocket twos vs uniform-random preflop.
  - Card removal: hero's blockers reduce villain's range correctly.
  - Heads-up tight-range hero beats wide-range villain.
  - Specific known equities (AA vs KK ~ 82/18, AK vs JJ ~ 46/54).

Trial counts are intentionally lower than production defaults to
keep tests fast (~1-3s total). The asserts use generous tolerance
to absorb Monte Carlo noise.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from game.card import Card, Rank, Suit
from poker.range import Range
from poker.range_equity import (
    equity_for_hand_vs_range,
    multiway_range_equity,
    range_vs_range_equity,
)


def C(rank: Rank, suit: Suit) -> Card:
    return Card(suit, rank)


# ---------- Heads-up specific hand vs hand ----------


def test_aces_beat_kings_preflop():
    hero = [C(Rank.ACE, Suit.SPADES), C(Rank.ACE, Suit.HEARTS)]
    villain = [C(Rank.KING, Suit.DIAMONDS), C(Rank.KING, Suit.CLUBS)]
    eq = multiway_range_equity([hero, villain], trials=600, rng=random.Random(11))
    # AA vs KK is ~82/18 in classic poker math.
    assert 0.75 <= eq[0] <= 0.90
    assert 0.10 <= eq[1] <= 0.25
    assert abs(sum(eq) - 1.0) < 0.05


def test_ak_vs_jj_is_close_to_coinflip():
    hero = [C(Rank.ACE, Suit.SPADES), C(Rank.KING, Suit.SPADES)]
    villain = [C(Rank.JACK, Suit.HEARTS), C(Rank.JACK, Suit.DIAMONDS)]
    eq = multiway_range_equity([hero, villain], trials=800, rng=random.Random(22))
    # AKs vs JJ is roughly 46/54 preflop.
    assert 0.36 <= eq[0] <= 0.55
    assert 0.45 <= eq[1] <= 0.64


def test_equities_sum_to_one_three_way():
    p1 = [C(Rank.ACE, Suit.SPADES), C(Rank.ACE, Suit.HEARTS)]
    p2 = [C(Rank.KING, Suit.SPADES), C(Rank.KING, Suit.HEARTS)]
    p3 = [C(Rank.QUEEN, Suit.SPADES), C(Rank.QUEEN, Suit.HEARTS)]
    eq = multiway_range_equity([p1, p2, p3], trials=400, rng=random.Random(33))
    assert abs(sum(eq) - 1.0) < 0.05
    # Strict ordering for nuts vs marginal preflop.
    assert eq[0] > eq[1] > eq[2]


# ---------- Range vs Range ----------


def test_tight_3bet_beats_wide_open_preflop():
    """QQ+/AK 3-bet range should crush a wide BTN-open range."""
    tight = Range.from_string("QQ+, AKs, AKo")
    wide = Range.from_string(
        "22+, A2s+, K8s+, Q9s+, J9s+, T8s+, 98s, A7o+, KTo+, QTo+, JTo"
    )
    hero_eq, vill_eq = range_vs_range_equity(
        tight, wide, trials=500, rng=random.Random(44)
    )
    assert hero_eq > 0.55
    assert hero_eq + vill_eq > 0.93


def test_range_vs_range_equity_on_postflop_board():
    """Both ranges include flopped sets; equity moves toward 0.5."""
    hero = Range.from_string("AA, KK")
    villain = Range.from_string("AA, KK, QQ, JJ")
    board = [
        C(Rank.QUEEN, Suit.SPADES),
        C(Rank.JACK, Suit.HEARTS),
        C(Rank.TWO, Suit.DIAMONDS),
    ]
    hero_eq, vill_eq = range_vs_range_equity(
        hero, villain, board=board, trials=300, rng=random.Random(55)
    )
    # Villain hits a set ~ half the time on this board (QQ or JJ),
    # so should be well ahead.
    assert vill_eq > hero_eq


def test_card_removal_enforced():
    """Hero holds Ah Ad; villain's AA combos must be reduced to AcAs only."""
    hero = [C(Rank.ACE, Suit.HEARTS), C(Rank.ACE, Suit.DIAMONDS)]
    # Villain's range is just AA — but card removal leaves only AcAs.
    villain_range = Range.from_string("AA")
    eq = multiway_range_equity(
        [hero, villain_range], trials=400, rng=random.Random(66)
    )
    # The two remaining AA combos chop with hero's AA almost always
    # (no flush draws to break the tie cleanly), so hero equity
    # should be near 0.5 with some variance from the runout.
    assert 0.40 <= eq[0] <= 0.60


# ---------- equity_for_hand_vs_range ----------


def test_equity_for_hand_vs_range_returns_scalar():
    hero = [C(Rank.JACK, Suit.SPADES), C(Rank.TEN, Suit.SPADES)]
    villain = Range.from_string("AA, KK, QQ")
    eq = equity_for_hand_vs_range(
        hero, villain, trials=400, rng=random.Random(77)
    )
    # JTs is a notable underdog to a premium-only range.
    assert eq < 0.35


def test_equity_for_hand_vs_uniform_with_three_opponents():
    """Heads-up AA equity ~ 85% vs random; 4-way it drops sharply."""
    from poker.range_equity import equity_for_hand_vs_uniform

    hero = [C(Rank.ACE, Suit.SPADES), C(Rank.ACE, Suit.HEARTS)]
    eq_hu = equity_for_hand_vs_uniform(
        hero, n_opponents=1, trials=400, rng=random.Random(88)
    )
    eq_4way = equity_for_hand_vs_uniform(
        hero, n_opponents=3, trials=400, rng=random.Random(88)
    )
    assert eq_hu > 0.80
    assert eq_4way < eq_hu
    # AA 4-way is still favorite but ~50-65%.
    assert 0.50 <= eq_4way <= 0.75


# ---------- Robustness ----------


def test_empty_input_returns_empty_list():
    assert multiway_range_equity([]) == []


def test_invalid_hand_raises():
    with pytest.raises(ValueError):
        multiway_range_equity([[C(Rank.ACE, Suit.SPADES)]], trials=10)


def test_full_board_is_deterministic():
    """River-already-out board: hero equity should be deterministic."""
    hero = [C(Rank.ACE, Suit.SPADES), C(Rank.ACE, Suit.HEARTS)]
    villain = [C(Rank.SEVEN, Suit.DIAMONDS), C(Rank.TWO, Suit.CLUBS)]
    board = [
        C(Rank.ACE, Suit.DIAMONDS),
        C(Rank.KING, Suit.CLUBS),
        C(Rank.QUEEN, Suit.SPADES),
        C(Rank.JACK, Suit.HEARTS),
        C(Rank.THREE, Suit.DIAMONDS),
    ]
    eq = multiway_range_equity(
        [hero, villain], board=board, trials=50, rng=random.Random(99)
    )
    # Hero has set of aces; villain has nothing. Hero wins 100%.
    assert eq[0] > 0.99
    assert eq[1] < 0.01
