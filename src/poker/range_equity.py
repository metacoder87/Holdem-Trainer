"""Range-vs-range equity via Monte Carlo with proper card removal.

Replaces two long-standing equity holes in the codebase:

  1. ``BalancedAI._estimate_equity`` used ``base_strength ** (n-1)``
     which is a heuristic that ignores card removal and doesn't
     model villain ranges at all.

  2. ``GameEngine._compute_equity_and_outs`` returned
     ``(hand_strength + hand_potential * 0.4) * opponent_factor``
     which is fast but a similarly rough approximation.

Both can now call ``multiway_range_equity`` for a properly-sampled
estimate that respects card removal and lets us specify villains'
actual ranges (e.g. "tight UTG range") rather than uniform random
opponent hands.

Performance: with the precomputed ``fast_evaluate`` lookup, ~5000
trials/sec on a single core for 3-way river equity. The default
trial counts here are tuned so a live coach call stays under
~150 ms even on slow runtimes.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence, Tuple

from game.card import Card, Rank, Suit
from poker.fast_eval import fast_evaluate, winner_from_hands
from poker.range import Combo, Range


# Default trial counts. Tuned so worst-case (preflop, 3+ players,
# wide ranges) still fits in a reasonable response time budget.
DEFAULT_TRIALS_PREFLOP = 1500
DEFAULT_TRIALS_POSTFLOP = 1000

_FULL_DECK: List[Card] = [
    Card(suit, rank)
    for rank in (
        Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN,
        Rank.EIGHT, Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE,
    )
    for suit in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS)
]


def _card_key(c: Card) -> Tuple:
    return (c.suit.value, c.rank.value)


def _weighted_sample(
    combos: Sequence[Tuple[Combo, float]],
    rng: random.Random,
) -> Optional[Combo]:
    """Sample one combo proportional to weight. Returns None on empty."""
    if not combos:
        return None
    total = sum(w for _, w in combos)
    if total <= 0:
        return None
    r = rng.uniform(0, total)
    acc = 0.0
    for combo, w in combos:
        acc += w
        if acc >= r:
            return combo
    return combos[-1][0]


def multiway_range_equity(
    hands_or_ranges: Sequence,
    board: Optional[Sequence[Card]] = None,
    *,
    trials: Optional[int] = None,
    rng: Optional[random.Random] = None,
) -> List[float]:
    """Per-player equity from a mix of fixed hole-pairs and Ranges.

    ``hands_or_ranges[i]`` can be either:
      - ``List[Card]`` (length 2): a fixed hole pair (hero's hand).
      - ``Range``: a probabilistic range; villain's combo is
        sampled each trial proportional to combo weight.

    ``board`` is the community cards already on the table (0, 3, 4,
    or 5 cards). The remaining board cards are sampled per trial
    from the unblocked deck.

    Card removal is enforced both across players (no two players
    can hold the same physical card) and against the board.

    Returns equities summing to 1.0 (with rounding tolerance).
    """
    if not hands_or_ranges:
        return []

    board_cards = list(board or [])
    n = len(hands_or_ranges)
    board_keys = {_card_key(c) for c in board_cards}

    if trials is None:
        trials = (
            DEFAULT_TRIALS_PREFLOP if len(board_cards) == 0
            else DEFAULT_TRIALS_POSTFLOP
        )

    rng = rng or random.Random()
    cards_to_come = 5 - len(board_cards)
    if cards_to_come < 0:
        cards_to_come = 0

    equities = [0.0] * n
    skipped = 0

    for _ in range(trials):
        # Assign each player a concrete pair this trial, sampling
        # ranges with card removal as we go.
        used_keys = set(board_keys)
        player_hands: List[Optional[List[Card]]] = [None] * n
        trial_valid = True

        for i, entry in enumerate(hands_or_ranges):
            if isinstance(entry, Range):
                # Filter to combos that don't conflict with already-
                # used cards this trial.
                available: List[Tuple[Combo, float]] = []
                for combo, weight in entry.items():
                    if _card_key(combo.high) in used_keys:
                        continue
                    if _card_key(combo.low) in used_keys:
                        continue
                    available.append((combo, weight))
                chosen = _weighted_sample(available, rng)
                if chosen is None:
                    trial_valid = False
                    break
                player_hands[i] = [chosen.high, chosen.low]
                used_keys.add(_card_key(chosen.high))
                used_keys.add(_card_key(chosen.low))
            else:
                fixed = list(entry)
                if len(fixed) != 2:
                    raise ValueError(
                        f"player {i} must be a Range or 2-card list"
                    )
                # Skip the trial if the fixed hand conflicts with
                # already-claimed cards.
                if (_card_key(fixed[0]) in used_keys
                        or _card_key(fixed[1]) in used_keys):
                    trial_valid = False
                    break
                player_hands[i] = fixed
                used_keys.add(_card_key(fixed[0]))
                used_keys.add(_card_key(fixed[1]))

        if not trial_valid:
            skipped += 1
            continue

        # Sample remaining board cards from the unblocked deck.
        remaining = [c for c in _FULL_DECK if _card_key(c) not in used_keys]
        if cards_to_come > 0:
            if cards_to_come > len(remaining):
                skipped += 1
                continue
            runout = rng.sample(remaining, cards_to_come)
        else:
            runout = []
        full_board = board_cards + runout

        # Build each player's 7-card holding and evaluate.
        per_player_cards = [hand + full_board for hand in player_hands]
        winners = winner_from_hands(per_player_cards)
        if not winners:
            skipped += 1
            continue
        share = 1.0 / len(winners)
        for w in winners:
            equities[w] += share

    valid_trials = trials - skipped
    if valid_trials <= 0:
        return [1.0 / n] * n  # all-skip: degenerate input, split evenly
    return [e / valid_trials for e in equities]


def range_vs_range_equity(
    hero_range: Range,
    villain_range: Range,
    board: Optional[Sequence[Card]] = None,
    *,
    trials: Optional[int] = None,
    rng: Optional[random.Random] = None,
) -> Tuple[float, float]:
    """Heads-up range-vs-range equity. Returns (hero_equity, villain_equity).

    Wraps ``multiway_range_equity`` for the 2-player case.
    """
    result = multiway_range_equity(
        [hero_range, villain_range],
        board=board,
        trials=trials,
        rng=rng,
    )
    if len(result) != 2:
        return (0.5, 0.5)
    return result[0], result[1]


def equity_for_hand_vs_range(
    hero_hole: Sequence[Card],
    villain_range: Range,
    board: Optional[Sequence[Card]] = None,
    *,
    trials: Optional[int] = None,
    rng: Optional[random.Random] = None,
) -> float:
    """Single hand vs villain range. The most common live-coach call.

    Returns hero's equity in [0, 1].
    """
    result = multiway_range_equity(
        [list(hero_hole), villain_range],
        board=board,
        trials=trials,
        rng=rng,
    )
    if not result:
        return 0.5
    return result[0]


def equity_for_hand_vs_uniform(
    hero_hole: Sequence[Card],
    board: Optional[Sequence[Card]] = None,
    n_opponents: int = 1,
    *,
    trials: Optional[int] = None,
    rng: Optional[random.Random] = None,
) -> float:
    """Hero vs N random-uniform opponents (any-two hands).

    Drop-in for the legacy ``calculate_heads_up_equity(hero, opp)``
    pattern when no villain range is known. Multiway-aware: pass
    ``n_opponents=2`` for 3-way pots, ``n_opponents=3`` for 4-way,
    etc.
    """
    if n_opponents < 1:
        return 1.0
    # Build a uniform random Range: every two-card combo with weight 1.
    uniform = Range.from_string(
        # All 169 starting-hand classes:
        "22+, A2s+, A2o+, K2s+, K2o+, Q2s+, Q2o+, J2s+, J2o+, "
        "T2s+, T2o+, 92s+, 92o+, 82s+, 82o+, 72s+, 72o+, 62s+, "
        "62o+, 52s+, 52o+, 42s+, 42o+, 32s, 32o"
    )
    hands = [list(hero_hole)] + [uniform] * n_opponents
    result = multiway_range_equity(
        hands, board=board, trials=trials, rng=rng
    )
    if not result:
        return 0.5
    return result[0]
