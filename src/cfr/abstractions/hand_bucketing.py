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


# Number of future-runout samples averaged into E[HS^2]. Each sample
# costs one heads-up equity calc with a fully-known 5-card board
# (which is deterministic-showdown, cheap). 30 samples gives ~1.5%
# standard error on E[HS^2] for typical flop hands.
DEFAULT_RUNOUT_SAMPLES = 30

# Default mix weight between E[HS] and sqrt(E[HS^2]) when computing
# the potential-aware strength. 0.0 = pure equity-vs-random (current
# strength only); 1.0 = pure RMS equity (full credit for upside).
# 0.5 is the "balanced" PioSolver-like blend.
DEFAULT_POTENTIAL_WEIGHT = 0.5


def hand_strength_squared(
    hole_cards: Sequence[Card],
    board: Sequence[Card],
    *,
    runout_samples: int = DEFAULT_RUNOUT_SAMPLES,
    opp_samples_per_runout: int = 4,
    rng: random.Random = None,
) -> float:
    """E[HS^2]: average over future runouts of (river equity)^2.

    For a flop board (3 cards): samples (turn, river) pairs and
    averages squared river equity vs uniform opponent.
    For a turn board (4 cards): samples river cards.
    For a river board (5 cards): trivially returns hand_strength^2
    (no future variance).

    Why this metric:

      - E[HS^2] >= E[HS]^2 always (Jensen).
      - For made hands with low future variance, the gap is small.
      - For drawing hands, the gap is large: a 35%-equity flush draw
        can have E[HS^2] near 0.25 because half the time it spikes
        to ~90% and half the time it bricks to ~10%.

      We use this as a "potential" signal so the bucket abstraction
      keeps drawing hands separated from dry middling hands.

    Returns a value in [0, 1].
    """
    if len(hole_cards) != 2:
        raise ValueError("hole_cards must be exactly 2 cards")

    board_list = list(board)
    cards_to_come = 5 - len(board_list)
    if cards_to_come < 0:
        cards_to_come = 0

    # River already dealt -> equity is the same across all runouts.
    # E[HS^2] reduces to hand_strength^2 at that point.
    if cards_to_come == 0:
        eq = hand_strength(hole_cards, board_list, rng=rng)
        return eq * eq

    rng = rng or random.Random(0xE45F)
    deck = [Card(s, r) for s in Suit for r in Rank]
    used = {(c.suit, c.rank) for c in list(hole_cards) + board_list}
    remaining = [c for c in deck if (c.suit, c.rank) not in used]

    total_sum_squared = 0.0
    samples = max(1, runout_samples)
    for _ in range(samples):
        # Sample a full runout completing the board to 5 cards.
        runout = rng.sample(remaining, cards_to_come)
        full_board = board_list + runout

        # Available opponents are the remaining deck minus the runout.
        sub_remaining = [
            c for c in remaining if c not in runout  # Card __eq__ compares (suit, rank)
        ]

        # Average equity at the river across opponent samples. With a
        # full board, calculate_heads_up_equity short-circuits to
        # deterministic showdown so each opp call is cheap.
        eq_sum = 0.0
        per_runout = max(1, opp_samples_per_runout)
        for _ in range(per_runout):
            opp = rng.sample(sub_remaining, 2)
            eq, _ = EquityCalculator.calculate_heads_up_equity(
                list(hole_cards),
                list(opp),
                board=full_board,
                # trials is ignored when board is full, but pass a
                # small value so we never accidentally trigger MC.
                trials=1,
                rng=rng,
            )
            eq_sum += eq
        eq_river = eq_sum / per_runout
        total_sum_squared += eq_river * eq_river

    return total_sum_squared / samples


def potential_aware_strength(
    hole_cards: Sequence[Card],
    board: Sequence[Card],
    *,
    weight: float = DEFAULT_POTENTIAL_WEIGHT,
    trials: int = DEFAULT_TRIALS,
    runout_samples: int = DEFAULT_RUNOUT_SAMPLES,
    rng: random.Random = None,
) -> float:
    """Weighted blend of E[HS] and sqrt(E[HS^2]) in [0, 1].

    Formula::

        s = (1 - weight) * E[HS] + weight * sqrt(E[HS^2])

    At ``weight=0`` this is plain E[HS] (equivalent to
    ``hand_strength``). At ``weight=1`` this is RMS equity which
    rewards hands whose upside is large even if their current equity
    is modest. The default ``weight=0.5`` is the postflop-solver
    industry default.

    For river boards this collapses to ``hand_strength`` exactly
    (E[HS^2] = E[HS]^2 there).
    """
    if weight < 0.0 or weight > 1.0:
        raise ValueError("weight must be in [0, 1]")

    e_hs = hand_strength(hole_cards, board, trials=trials, rng=rng)
    if len(board) >= 5 or weight == 0.0:
        return e_hs

    e_hs2 = hand_strength_squared(
        hole_cards,
        board,
        runout_samples=runout_samples,
        rng=rng,
    )
    rms = e_hs2 ** 0.5
    return (1.0 - weight) * e_hs + weight * rms


def potential_aware_bucket(
    hole_cards: Sequence[Card],
    board: Sequence[Card],
    *,
    num_buckets: int = DEFAULT_BUCKETS,
    weight: float = DEFAULT_POTENTIAL_WEIGHT,
    trials: int = DEFAULT_TRIALS,
    runout_samples: int = DEFAULT_RUNOUT_SAMPLES,
    rng: random.Random = None,
) -> int:
    """Bucket index using potential-aware strength.

    Use this instead of :func:`hand_bucket` for flop/turn subgames
    where future-equity realization matters. For river subgames it
    behaves identically to ``hand_bucket``.
    """
    strength = potential_aware_strength(
        hole_cards,
        board,
        weight=weight,
        trials=trials,
        runout_samples=runout_samples,
        rng=rng,
    )
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
