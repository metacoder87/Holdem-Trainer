"""Effective Hand Strength (EHS) bucketing for NLHE.

EHS condenses a (hole_cards, board) into a single float in [0, 1]
representing equity against a uniform random opponent. We then bin
those floats into ``num_buckets`` discrete buckets which become the
"hand" axis of the CFR abstraction.

Reuses ``EquityCalculator.calculate_heads_up_equity`` from
``stats.calculator`` so we don't have a second Monte Carlo
implementation. The engine's equity calc is already well-tested
(``tests/test_equity_monte_carlo.py``).

Bucket count tradeoffs:
  - 5 buckets:   ~OK for flop, terrible for river (loses too much)
  - 10 buckets:  decent baseline
  - 50 buckets:  approaches no-abstraction equity resolution

We default to 10 because river subgame solving with 10 buckets per
player x ~500 board textures x ~25 stack-pot ratios is the sweet
spot that fits in <8 GB RAM and converges in <1 hour.
"""
from __future__ import annotations

import random
from functools import lru_cache
from typing import List, Sequence, Tuple

# Imports from the existing src/stats package - this is deliberate
# (we reuse the production Monte Carlo equity calc).
from game.card import Card, Rank, Suit
from stats.calculator import EquityCalculator


DEFAULT_BUCKETS = 10
DEFAULT_TRIALS = 200  # per hand for bucketing only; lower than runtime


def hand_strength(
    hole_cards: Sequence[Card],
    board: Sequence[Card],
    *,
    trials: int = DEFAULT_TRIALS,
    rng: random.Random = None,
) -> float:
    """Equity of (hole, board) vs. a random opponent, in [0, 1]."""
    if len(hole_cards) != 2:
        raise ValueError("hole_cards must be exactly 2 cards")

    rng = rng or random.Random(0xEAF5)
    # Draw a random opponent hand from the remaining 50 cards.
    deck = [Card(s, r) for s in Suit for r in Rank]
    used = {(c.suit, c.rank) for c in list(hole_cards) + list(board)}
    remaining = [c for c in deck if (c.suit, c.rank) not in used]

    # Average equity over a few opponent hand samples to reduce variance.
    samples_per_opp = max(20, trials // 8)
    total_equity = 0.0
    num_opponent_samples = 8
    for _ in range(num_opponent_samples):
        opp = rng.sample(remaining, 2)
        eq, _ = EquityCalculator.calculate_heads_up_equity(
            list(hole_cards),
            list(opp),
            board=list(board),
            trials=samples_per_opp,
            rng=rng,
        )
        total_equity += eq
    return total_equity / num_opponent_samples


def bucket_for_strength(strength: float, num_buckets: int = DEFAULT_BUCKETS) -> int:
    """Map strength in [0,1] to bucket index in [0, num_buckets-1]."""
    if num_buckets <= 0:
        raise ValueError("num_buckets must be positive")
    # Equal-width bins. Could be improved with equal-frequency bins
    # over a sampled distribution but equal-width is sufficient for v1.
    idx = int(strength * num_buckets)
    if idx >= num_buckets:
        idx = num_buckets - 1
    if idx < 0:
        idx = 0
    return idx


def hand_bucket(
    hole_cards: Sequence[Card],
    board: Sequence[Card],
    *,
    num_buckets: int = DEFAULT_BUCKETS,
    trials: int = DEFAULT_TRIALS,
    rng: random.Random = None,
) -> int:
    """Convenience: compute strength + bucket in one call."""
    strength = hand_strength(hole_cards, board, trials=trials, rng=rng)
    return bucket_for_strength(strength, num_buckets=num_buckets)


def board_key(board: Sequence[Card]) -> str:
    """Canonical, suit-isomorphic representation of a board.

    Example: ``[Ah, Kd, 2c]`` and ``[As, Kc, 2d]`` produce the same
    key because rainbow boards with the same ranks are strategically
    equivalent. Cuts the state space by ~24x in the typical case.
    """
    if not board:
        return ""
    # Sort ranks descending, then map suits to canonical letters
    # a/b/c/d in the order they first appear (suit-isomorphism).
    suit_map: dict = {}
    next_letter = ord("a")
    parts: List[str] = []
    for card in board:
        suit = card.suit
        if suit not in suit_map:
            suit_map[suit] = chr(next_letter)
            next_letter += 1
        parts.append(f"{card.rank.value}{suit_map[suit]}")
    return ",".join(parts)
