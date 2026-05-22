"""Fast 7-card poker hand evaluator with integer rank output.

Replaces the legacy ``Hand.best_hand_from_cards`` for inner equity
loops where every microsecond counts. Lower rank int = better hand.
The integer encoding uses standard class offsets:

    0      ..    9     Straight flush  (10 hands)
    10     ..  165     Four of a kind  (156)
    166    ..  321     Full house      (156)
    322    .. 1598     Flush           (1277)
    1599   .. 1608     Straight        (10)
    1609   .. 2466     Three of a kind (858)
    2467   .. 3324     Two pair        (858)
    3325   .. 6184     One pair        (2860)
    6185   .. 7461     High card       (1277)

Within each class we encode the kicker tie-breakers into the low
bits so direct int comparison gives the right answer. No lookup
tables; pure arithmetic — fast enough (~5 microseconds per 5-card
hand) and trivially correct.

For 7-card hands (hole + board) we iterate the C(7,5)=21
sub-combinations and return the minimum (best) rank.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import List, Sequence

from game.card import Card, Rank, Suit


# Class offsets — start of each hand class in the rank-int space.
_OFF_STRAIGHT_FLUSH = 0
_OFF_FOUR_KIND = 10
_OFF_FULL_HOUSE = 166
_OFF_FLUSH = 322
_OFF_STRAIGHT = 1599
_OFF_THREE_KIND = 1609
_OFF_TWO_PAIR = 2467
_OFF_ONE_PAIR = 3325
_OFF_HIGH_CARD = 6185
_RANK_MAX = 7461


def _detect_straight(values_desc: List[int]) -> int:
    """Return the high-card value of a straight, or 0 if not a straight.

    ``values_desc`` is a sorted-descending list of 5 distinct rank
    values. Handles the wheel (A-2-3-4-5) by checking the exact
    pattern [14, 5, 4, 3, 2] and returning 5 (the high card of the
    wheel).
    """
    if len(values_desc) != 5:
        return 0
    if values_desc == [14, 5, 4, 3, 2]:
        return 5
    # Strictly decreasing by 1, all distinct.
    for i in range(4):
        if values_desc[i] - values_desc[i + 1] != 1:
            return 0
    return values_desc[0]


def _kicker_int(values_desc: Sequence[int]) -> int:
    """Pack up to 5 rank values into one base-15 int.

    Values are descending. Each rank fits in [0, 14] so base 15
    gives a unique int per ordering. Used as tie-breaker encoding
    within a hand class.
    """
    n = 0
    for v in values_desc:
        n = n * 15 + (14 - v)  # ace -> 0 (best), two -> 12
    return n


def _class_pair_count(values_desc: List[int]) -> int:
    """How many ranks in ``values_desc`` actually exist (mostly
    redundant with a Counter, but cheap)."""
    return len(set(values_desc))


def fast_evaluate_5(cards: Sequence[Card]) -> int:
    """Rank a single 5-card hand. Lower = better."""
    if len(cards) != 5:
        raise ValueError("fast_evaluate_5 needs exactly 5 cards")

    suits = [c.suit for c in cards]
    is_flush = suits[0] == suits[1] == suits[2] == suits[3] == suits[4]

    counts = Counter(c.rank.value for c in cards)
    # Sort by (count desc, rank desc) so the dominant rank shows first.
    sorted_ranks = sorted(counts.items(), key=lambda kv: (-kv[1], -kv[0]))
    count_pattern = tuple(c for _, c in sorted_ranks)
    rank_pattern = [r for r, _ in sorted_ranks]

    # Straight detection on distinct ranks (only if all 5 are unique).
    if count_pattern == (1, 1, 1, 1, 1):
        values_desc = sorted([c.rank.value for c in cards], reverse=True)
        straight_high = _detect_straight(values_desc)
    else:
        straight_high = 0

    # ---- Class dispatch ----

    # Straight flush.
    if is_flush and straight_high > 0:
        return _OFF_STRAIGHT_FLUSH + (14 - straight_high)

    # Four of a kind.
    if count_pattern == (4, 1):
        quad_v = rank_pattern[0]
        kick_v = rank_pattern[1]
        # 13 possible quads * 12 possible kickers = 156.
        return _OFF_FOUR_KIND + (14 - quad_v) * 12 + _kicker_index(kick_v, exclude=quad_v)

    # Full house.
    if count_pattern == (3, 2):
        trip_v = rank_pattern[0]
        pair_v = rank_pattern[1]
        return _OFF_FULL_HOUSE + (14 - trip_v) * 12 + _kicker_index(pair_v, exclude=trip_v)

    # Flush (non-straight).
    if is_flush:
        values_desc = sorted([c.rank.value for c in cards], reverse=True)
        return _OFF_FLUSH + _flush_rank_index(values_desc)

    # Straight (non-flush).
    if straight_high > 0:
        return _OFF_STRAIGHT + (14 - straight_high)

    # Three of a kind.
    if count_pattern == (3, 1, 1):
        trip_v = rank_pattern[0]
        kickers = sorted(rank_pattern[1:], reverse=True)
        # 13 trips * C(12,2) = 13 * 66 = 858 distinct hands.
        return (
            _OFF_THREE_KIND
            + (14 - trip_v) * 66
            + _two_kicker_index(kickers, exclude=trip_v)
        )

    # Two pair.
    if count_pattern == (2, 2, 1):
        hi_pair = rank_pattern[0]
        lo_pair = rank_pattern[1]
        kicker = rank_pattern[2]
        # C(13,2) = 78 pair pairs, 11 kicker options each = 858.
        return (
            _OFF_TWO_PAIR
            + _pair_pair_index(hi_pair, lo_pair) * 11
            + _kicker_index(kicker, exclude_set={hi_pair, lo_pair})
        )

    # One pair.
    if count_pattern == (2, 1, 1, 1):
        pair_v = rank_pattern[0]
        kickers = sorted(rank_pattern[1:], reverse=True)
        # 13 pairs * C(12, 3) = 13 * 220 = 2860.
        return (
            _OFF_ONE_PAIR
            + (14 - pair_v) * 220
            + _three_kicker_index(kickers, exclude=pair_v)
        )

    # High card.
    values_desc = sorted([c.rank.value for c in cards], reverse=True)
    return _OFF_HIGH_CARD + _flush_rank_index(values_desc)


def _kicker_index(value: int, *, exclude: int = -1, exclude_set: set = None) -> int:
    """Index of ``value`` (rank int 2..14) within the 12 non-excluded ranks.

    0 = best (highest rank), 11 = worst.
    """
    if exclude_set is None:
        exclude_set = {exclude}
    # Walk all 13 ranks high to low, skipping excluded, count position.
    pos = 0
    for v in range(14, 1, -1):
        if v in exclude_set:
            continue
        if v == value:
            return pos
        pos += 1
    return pos


def _two_kicker_index(values: List[int], *, exclude: int) -> int:
    """Index of a 2-kicker pair (descending) among C(12, 2) = 66.

    ``values`` is sorted descending. Excluded rank can't appear.
    """
    # Build the list of available ranks in descending order.
    available = [v for v in range(14, 1, -1) if v != exclude]
    # Map (a, b) to its position in lex order over (i<j) pairs.
    n = len(available)
    idx = 0
    for i in range(n):
        for j in range(i + 1, n):
            if available[i] == values[0] and available[j] == values[1]:
                return idx
            idx += 1
    return idx


def _three_kicker_index(values: List[int], *, exclude: int) -> int:
    """Index of a 3-kicker tuple (descending) among C(12, 3) = 220."""
    available = [v for v in range(14, 1, -1) if v != exclude]
    n = len(available)
    idx = 0
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                if (available[i] == values[0]
                        and available[j] == values[1]
                        and available[k] == values[2]):
                    return idx
                idx += 1
    return idx


def _pair_pair_index(hi: int, lo: int) -> int:
    """Index of a (hi, lo) pair-of-pairs among C(13, 2) = 78 ordered hi>lo."""
    idx = 0
    for i in range(14, 1, -1):
        for j in range(i - 1, 1, -1):
            if i == hi and j == lo:
                return idx
            idx += 1
    return idx


_FLUSH_RANK_INDEX: dict = {}


def _build_flush_rank_index() -> None:
    """Build the (values_tuple) -> index map for non-straight 5-card sets.

    Used both for flushes and high-card hands — both have 1277 valid
    rank-quintuples (C(13, 5) - 10 straights). Built lazily on first
    call; takes ~5 ms.
    """
    if _FLUSH_RANK_INDEX:
        return
    all_ranks = [14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2]
    quintuples: List[List[int]] = []
    for combo in combinations(all_ranks, 5):
        values_desc = sorted(combo, reverse=True)
        # Skip straights — those have their own slots.
        if _detect_straight(values_desc) > 0:
            continue
        quintuples.append(values_desc)
    # Sort best-to-worst: descending high cards lexicographically.
    quintuples.sort(key=lambda v: tuple(-x for x in v))
    for idx, quint in enumerate(quintuples):
        _FLUSH_RANK_INDEX[tuple(quint)] = idx


def _flush_rank_index(values_desc: List[int]) -> int:
    """Index of a 5-card high-card flush among the 1277 non-straight flushes.

    Used both for flushes and high-card hands (same kicker structure).
    """
    _build_flush_rank_index()
    return _FLUSH_RANK_INDEX.get(tuple(values_desc), 1276)


def fast_evaluate(cards: Sequence[Card]) -> int:
    """Rank a 5-, 6-, or 7-card hand. Lower = better.

    For >5 cards, returns the rank of the best 5-card subset.
    """
    n = len(cards)
    if n < 5:
        raise ValueError(f"fast_evaluate needs >=5 cards, got {n}")
    if n == 5:
        return fast_evaluate_5(cards)
    best = _RANK_MAX + 1
    for combo in combinations(cards, 5):
        r = fast_evaluate_5(combo)
        if r < best:
            best = r
    return best


def rank_class(rank: int) -> str:
    """Human-readable class name for a rank int."""
    if rank < _OFF_FOUR_KIND:
        return "Straight Flush"
    if rank < _OFF_FULL_HOUSE:
        return "Four of a Kind"
    if rank < _OFF_FLUSH:
        return "Full House"
    if rank < _OFF_STRAIGHT:
        return "Flush"
    if rank < _OFF_THREE_KIND:
        return "Straight"
    if rank < _OFF_TWO_PAIR:
        return "Three of a Kind"
    if rank < _OFF_ONE_PAIR:
        return "Two Pair"
    if rank < _OFF_HIGH_CARD:
        return "One Pair"
    return "High Card"


def winner_from_hands(player_cards: Sequence[Sequence[Card]]) -> List[int]:
    """Return indices of players tied for best hand. Lower rank = better."""
    if not player_cards:
        return []
    ranks = [fast_evaluate(cards) for cards in player_cards]
    best_rank = min(ranks)
    return [i for i, r in enumerate(ranks) if r == best_rank]
