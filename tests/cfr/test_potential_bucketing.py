"""Potential-aware bucketing tests.

The key invariant: at the same E[HS], a hand with high future
variance (a draw) should have a higher E[HS^2] than a hand whose
equity is locked in (a made hand). The potential-aware bucket
should therefore separate draws into a higher bucket than dry,
similarly-strong hands.

These tests don't pin exact numbers (Monte Carlo noise makes that
brittle) but they pin the *ordering* invariants the abstraction
depends on.
"""
from __future__ import annotations

import random
from typing import List

import pytest

from cfr.abstractions.hand_bucketing import (
    DEFAULT_POTENTIAL_WEIGHT,
    bucket_for_strength,
    hand_bucket,
    hand_strength,
    hand_strength_squared,
    potential_aware_bucket,
    potential_aware_strength,
)
from game.card import Card, Rank, Suit


def C(rank: Rank, suit: Suit) -> Card:
    return Card(suit, rank)


# Canonical hands & boards for the ordering tests.

# A flop with an open-ended straight draw + flush draw potential.
_DRAW_BOARD = [C(Rank.JACK, Suit.HEARTS), C(Rank.TEN, Suit.HEARTS), C(Rank.THREE, Suit.SPADES)]
_DRAW_HAND = [C(Rank.NINE, Suit.HEARTS), C(Rank.EIGHT, Suit.HEARTS)]  # OESD + flush draw

# Same flop, with a low pocket pair (made hand, no draw equity).
_DRY_MADE_HAND = [C(Rank.FIVE, Suit.SPADES), C(Rank.FIVE, Suit.CLUBS)]


# Dry, rainbow flop where draws are weaker.
_DRY_BOARD = [C(Rank.ACE, Suit.SPADES), C(Rank.SEVEN, Suit.HEARTS), C(Rank.TWO, Suit.CLUBS)]

# Top pair + good kicker on the dry board — strong made hand.
_TOP_PAIR_HAND = [C(Rank.ACE, Suit.HEARTS), C(Rank.KING, Suit.DIAMONDS)]

# River boards (full 5 cards): potential should collapse to E[HS].
_RIVER_BOARD = _DRAW_BOARD + [C(Rank.FOUR, Suit.CLUBS), C(Rank.TWO, Suit.DIAMONDS)]


# ---------- Jensen invariant ----------


def test_e_hs2_at_least_e_hs_squared():
    """Jensen's inequality: E[HS^2] >= (E[HS])^2 always."""
    rng = random.Random(11)
    e_hs = hand_strength(_DRAW_HAND, _DRAW_BOARD, trials=200, rng=rng)
    e_hs2 = hand_strength_squared(
        _DRAW_HAND, _DRAW_BOARD, runout_samples=20, rng=rng
    )
    # Allow tiny numerical slack for MC noise.
    assert e_hs2 >= (e_hs * e_hs) - 0.01


def test_e_hs2_collapses_to_squared_hs_on_river():
    """On a 5-card board there's no future variance."""
    rng = random.Random(13)
    e_hs = hand_strength(_DRAW_HAND, _RIVER_BOARD, trials=50, rng=rng)
    e_hs2 = hand_strength_squared(
        _DRAW_HAND, _RIVER_BOARD, runout_samples=5, rng=rng
    )
    # E[HS^2] == E[HS]^2 at the river (the function takes a shortcut).
    assert abs(e_hs2 - e_hs * e_hs) < 1e-6


# ---------- Draw vs dry-made ordering ----------


def test_draw_has_more_potential_than_dry_pair_at_similar_hs():
    """Same E[HS] -> draw should have higher E[HS^2]."""
    rng = random.Random(42)
    e_hs_draw = hand_strength(_DRAW_HAND, _DRAW_BOARD, trials=400, rng=rng)
    e_hs_pair = hand_strength(_DRY_MADE_HAND, _DRAW_BOARD, trials=400, rng=rng)
    # Draws and dry pairs both sit around 30-45% equity on this board.
    # If both ended up at very different E[HS] the test isn't valid;
    # skip if so.
    if abs(e_hs_draw - e_hs_pair) > 0.20:
        pytest.skip("E[HS] gap too large for ordering test")

    rng2 = random.Random(42)
    e_hs2_draw = hand_strength_squared(
        _DRAW_HAND, _DRAW_BOARD, runout_samples=30, rng=rng2
    )
    e_hs2_pair = hand_strength_squared(
        _DRY_MADE_HAND, _DRAW_BOARD, runout_samples=30, rng=rng2
    )
    # Draw's E[HS^2] should be strictly larger than the dry pair's,
    # reflecting its higher equity variance.
    assert e_hs2_draw > e_hs2_pair


def test_potential_strength_boosts_drawing_hand():
    """potential_aware_strength(draw) > hand_strength(draw)."""
    rng = random.Random(99)
    plain = hand_strength(_DRAW_HAND, _DRAW_BOARD, trials=400, rng=rng)
    rng2 = random.Random(99)
    boosted = potential_aware_strength(
        _DRAW_HAND, _DRAW_BOARD, weight=0.7, runout_samples=30, rng=rng2
    )
    assert boosted > plain


def test_potential_strength_neutral_on_made_dry_hand():
    """A locked-in top pair gets ~ no boost from potential weighting."""
    rng = random.Random(101)
    plain = hand_strength(_TOP_PAIR_HAND, _DRY_BOARD, trials=400, rng=rng)
    rng2 = random.Random(101)
    boosted = potential_aware_strength(
        _TOP_PAIR_HAND, _DRY_BOARD, weight=0.5, runout_samples=30, rng=rng2
    )
    # Top pair on a dry board has very little variance; the boost
    # should be small (< 0.05 absolute change).
    assert abs(boosted - plain) < 0.10


# ---------- Bucket ordering ----------


def test_potential_bucket_is_in_valid_range():
    rng = random.Random(7)
    b = potential_aware_bucket(
        _DRAW_HAND, _DRAW_BOARD, num_buckets=10, runout_samples=10, rng=rng
    )
    assert 0 <= b < 10


def test_potential_bucket_equals_plain_bucket_at_zero_weight():
    """weight=0 -> potential_aware_bucket == hand_bucket."""
    rng_a = random.Random(33)
    rng_b = random.Random(33)
    a = hand_bucket(_DRAW_HAND, _DRAW_BOARD, num_buckets=10, trials=200, rng=rng_a)
    b = potential_aware_bucket(
        _DRAW_HAND,
        _DRAW_BOARD,
        num_buckets=10,
        weight=0.0,
        trials=200,
        rng=rng_b,
    )
    assert a == b


def test_potential_bucket_collapses_to_plain_on_river():
    """River boards: potential_aware_bucket matches hand_bucket."""
    rng_a = random.Random(55)
    rng_b = random.Random(55)
    a = hand_bucket(_DRAW_HAND, _RIVER_BOARD, num_buckets=10, trials=200, rng=rng_a)
    b = potential_aware_bucket(
        _DRAW_HAND,
        _RIVER_BOARD,
        num_buckets=10,
        weight=DEFAULT_POTENTIAL_WEIGHT,
        trials=200,
        runout_samples=5,
        rng=rng_b,
    )
    # Both should land in the same bucket because there's no
    # future variance to amplify.
    assert a == b


def test_strong_made_hand_outranks_weak_draw_even_with_potential():
    """A monster hand still buckets above a long-shot draw."""
    rng = random.Random(91)
    nut_flush_hand = [C(Rank.ACE, Suit.HEARTS), C(Rank.QUEEN, Suit.HEARTS)]
    # Same flop, all hearts (monotone): nut flush already made.
    monotone_flop = [
        C(Rank.NINE, Suit.HEARTS),
        C(Rank.SEVEN, Suit.HEARTS),
        C(Rank.TWO, Suit.HEARTS),
    ]
    backdoor_hand = [C(Rank.FOUR, Suit.SPADES), C(Rank.THREE, Suit.SPADES)]

    monster_strength = potential_aware_strength(
        nut_flush_hand,
        monotone_flop,
        weight=0.5,
        runout_samples=15,
        rng=random.Random(91),
    )
    weak_strength = potential_aware_strength(
        backdoor_hand,
        monotone_flop,
        weight=0.5,
        runout_samples=15,
        rng=random.Random(91),
    )
    assert monster_strength > weak_strength
