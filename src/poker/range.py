"""Weighted poker hand ranges.

A ``Range`` is a mapping from specific 2-card combos to weights in
[0, 1]. Pocket pairs, suited connectors, and offsuit hands are all
represented by their concrete card-pair combos; methods are provided
to construct ranges from compact poker notation strings like
``"AA, KK, AKs, QJs+, 22+"``.

This is the foundation for proper multiway equity, range-vs-range
analysis, and GTO-aware coaching. The legacy ``_estimate_equity``
heuristic in ``ai_player.py`` treats opponent hands as unknown
random cards; with ``Range`` we can model an opponent who 3-bets a
specific tight range and get realistic equity.

Notation parser supports the standard subset:
  - ``AA`` / ``22``                              pocket pairs
  - ``AKs``, ``AKo``, ``AK``                     specific class
  - ``AKs+`` / ``ATs+``                          suited/offsuit-plus
  - ``22+`` / ``88+``                            pair-plus
  - ``AA, KK, QQ, AKs``                          comma-separated lists

Card removal (i.e. excluding combos that contain blockers like the
hero's hole cards or the board) is handled at enumeration time via
``Range.combo_list(blockers=...)``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from game.card import Card, Rank, Suit


# Canonical rank ordering. 2 = lowest, A = highest.
_RANK_ORDER: List[Rank] = [
    Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN,
    Rank.EIGHT, Rank.NINE, Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE,
]

_RANK_GLYPH: Dict[str, Rank] = {
    "2": Rank.TWO, "3": Rank.THREE, "4": Rank.FOUR, "5": Rank.FIVE,
    "6": Rank.SIX, "7": Rank.SEVEN, "8": Rank.EIGHT, "9": Rank.NINE,
    "T": Rank.TEN, "J": Rank.JACK, "Q": Rank.QUEEN, "K": Rank.KING, "A": Rank.ACE,
}

_GLYPH_FOR_RANK: Dict[Rank, str] = {v: k for k, v in _RANK_GLYPH.items()}

# All 52 cards in canonical order. Lazy-built once.
_FULL_DECK: List[Card] = [
    Card(suit, rank) for rank in _RANK_ORDER for suit in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS)
]


@dataclass(frozen=True)
class Combo:
    """A specific 2-card poker hand (e.g. A♠ K♠).

    Combos are stored with cards ordered high-rank-first then by
    suit so ``Combo`` is canonical-form: any two equivalent combos
    compare equal and hash identically.
    """

    high: Card
    low: Card

    @classmethod
    def make(cls, a: Card, b: Card) -> "Combo":
        if a.rank.value > b.rank.value:
            return cls(a, b)
        if a.rank.value < b.rank.value:
            return cls(b, a)
        # Equal ranks: order by suit name for determinism.
        if a.suit.name <= b.suit.name:
            return cls(a, b)
        return cls(b, a)

    def is_suited(self) -> bool:
        return self.high.suit == self.low.suit

    def is_pair(self) -> bool:
        return self.high.rank == self.low.rank

    def cards(self) -> Tuple[Card, Card]:
        return (self.high, self.low)

    def to_notation(self) -> str:
        """Compact class-string form: 'AKs' / 'AKo' / 'TT'."""
        hi = _GLYPH_FOR_RANK[self.high.rank]
        lo = _GLYPH_FOR_RANK[self.low.rank]
        if self.is_pair():
            return f"{hi}{lo}"
        return f"{hi}{lo}{'s' if self.is_suited() else 'o'}"

    def __str__(self) -> str:  # pragma: no cover - debug aid
        return f"{self.high}{self.low}"


def all_combos_for_class(notation: str) -> List[Combo]:
    """Expand a class notation (``AA``, ``AKs``, ``T9o``) into all combos.

    - Pair (``XX``): 6 combos (C(4,2)).
    - Suited (``XYs``): 4 combos (one per suit).
    - Offsuit (``XYo`` or ``XY``): 12 combos.
    """
    notation = notation.strip().upper().replace("10", "T")
    if not (2 <= len(notation) <= 3):
        raise ValueError(f"unparseable hand notation: {notation!r}")

    hi_glyph = notation[0]
    lo_glyph = notation[1]
    suffix = notation[2:3]  # '' / 'S' / 'O'

    if hi_glyph not in _RANK_GLYPH or lo_glyph not in _RANK_GLYPH:
        raise ValueError(f"unknown rank glyph in {notation!r}")
    if suffix not in {"", "S", "O"}:
        raise ValueError(f"unknown suffix in {notation!r}")

    hi_rank = _RANK_GLYPH[hi_glyph]
    lo_rank = _RANK_GLYPH[lo_glyph]

    # Normalize so high-rank glyph is genuinely the higher card.
    if hi_rank.value < lo_rank.value:
        hi_rank, lo_rank = lo_rank, hi_rank

    suits = (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS)
    if hi_rank == lo_rank:
        # Pair: all C(4,2) = 6 same-rank pairs across suit pairs.
        out: List[Combo] = []
        for i in range(len(suits)):
            for j in range(i + 1, len(suits)):
                out.append(Combo.make(Card(suits[i], hi_rank), Card(suits[j], lo_rank)))
        return out

    if suffix == "S":
        return [Combo.make(Card(s, hi_rank), Card(s, lo_rank)) for s in suits]
    if suffix == "O":
        out = []
        for s1 in suits:
            for s2 in suits:
                if s1 == s2:
                    continue
                out.append(Combo.make(Card(s1, hi_rank), Card(s2, lo_rank)))
        return out
    # No suffix: both suited + offsuit (16 combos).
    return (
        all_combos_for_class(f"{hi_glyph}{lo_glyph}S")
        + all_combos_for_class(f"{hi_glyph}{lo_glyph}O")
    )


def _expand_plus_pair(low_pair: str) -> List[str]:
    """``22+`` -> ['22', '33', ..., 'AA']."""
    low_rank = _RANK_GLYPH[low_pair[0].upper()]
    out: List[str] = []
    for r in _RANK_ORDER:
        if r.value >= low_rank.value:
            glyph = _GLYPH_FOR_RANK[r]
            out.append(f"{glyph}{glyph}")
    return out


def _expand_plus_class(notation: str) -> List[str]:
    """``ATs+`` -> ['ATs', 'AJs', 'AQs', 'AKs']."""
    notation = notation.upper().replace("10", "T")
    hi_glyph = notation[0]
    lo_glyph = notation[1]
    suffix = notation[2:3]
    hi_rank = _RANK_GLYPH[hi_glyph]
    low_floor = _RANK_GLYPH[lo_glyph]
    out: List[str] = []
    # Walk every rank strictly less than hi, starting from low_floor.
    for r in _RANK_ORDER:
        if r.value >= hi_rank.value:
            continue
        if r.value < low_floor.value:
            continue
        out.append(f"{hi_glyph}{_GLYPH_FOR_RANK[r]}{suffix}")
    return out


def parse_range_string(spec: str) -> Dict[str, float]:
    """Parse a range string into a class-notation -> weight mapping.

    Examples::

        "AA, KK, AKs"           -> {"AA": 1.0, "KK": 1.0, "AKs": 1.0}
        "22+, ATs+, KQs"        -> all pairs + AT/AJ/AQ/AK suited + KQs
        "AA:0.5"                 -> partial weight (mix strategy)

    Whitespace and case are normalized. Unknown tokens raise
    ValueError.
    """
    out: Dict[str, float] = {}
    if not spec or not spec.strip():
        return out
    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue

        # Optional weight: ``AA:0.5``.
        weight = 1.0
        if ":" in token:
            token, weight_str = token.split(":", 1)
            weight = float(weight_str)
            token = token.strip()
        # ``+`` expansion.
        if token.endswith("+"):
            base = token[:-1].upper().replace("10", "T")
            if len(base) == 2 and base[0] == base[1]:
                expanded = _expand_plus_pair(base)
            else:
                expanded = _expand_plus_class(base)
                expanded.append(base)
            for cls in expanded:
                out[cls] = weight
            continue
        # Single class / pair.
        normalized = token.upper().replace("10", "T")
        # ``AK`` (no suffix) expands to both suited and offsuit.
        if len(normalized) == 2 and normalized[0] != normalized[1]:
            out[f"{normalized}S"] = weight
            out[f"{normalized}O"] = weight
            continue
        # Validate; raises if unparseable.
        all_combos_for_class(normalized)
        out[normalized] = weight
    return out


class Range:
    """Weighted set of two-card combos.

    Internally a dict of ``Combo -> weight``. The same combo never
    appears twice; if a user specifies ``"AKs, AKs:0.5"`` the later
    weight wins. Methods are provided for class-string round-trips
    and for card-removal-aware combo enumeration.
    """

    __slots__ = ("_combos",)

    def __init__(self, combos: Optional[Dict[Combo, float]] = None) -> None:
        self._combos: Dict[Combo, float] = {}
        if combos:
            for combo, weight in combos.items():
                if weight > 0:
                    self._combos[combo] = float(weight)

    # ---- Constructors ----

    @classmethod
    def from_string(cls, spec: str) -> "Range":
        """Build a Range from a notation string. See ``parse_range_string``."""
        notation_map = parse_range_string(spec)
        out: Dict[Combo, float] = {}
        for cls_notation, weight in notation_map.items():
            for combo in all_combos_for_class(cls_notation):
                out[combo] = weight
        return cls(out)

    @classmethod
    def from_classes(cls, classes: Iterable[str], weight: float = 1.0) -> "Range":
        """Build a Range from a list of class strings with one weight."""
        out: Dict[Combo, float] = {}
        for c in classes:
            for combo in all_combos_for_class(c):
                out[combo] = weight
        return cls(out)

    @classmethod
    def empty(cls) -> "Range":
        return cls({})

    # ---- Query ----

    def combo_count(self) -> int:
        """Sum of weights (continuous combo count)."""
        return sum(self._combos.values())

    def total_combos(self) -> int:
        """Discrete combo count, ignoring weights."""
        return len(self._combos)

    def weight(self, combo: Combo) -> float:
        return self._combos.get(combo, 0.0)

    def contains(self, combo: Combo) -> bool:
        return combo in self._combos

    def combos(self) -> Iterator[Combo]:
        return iter(self._combos.keys())

    def items(self) -> Iterator[Tuple[Combo, float]]:
        return iter(self._combos.items())

    # ---- Card removal ----

    def combo_list(
        self, blockers: Optional[Sequence[Card]] = None
    ) -> List[Tuple[Combo, float]]:
        """Return ``[(combo, weight), ...]`` excluding combos that
        contain any of the blocker cards.

        Used by range-vs-range Monte Carlo: hero's hole cards + board
        are blockers when sampling villain combos so we never deal
        the same physical card twice.
        """
        if not blockers:
            return list(self._combos.items())
        block_set = {(c.suit, c.rank) for c in blockers}
        out: List[Tuple[Combo, float]] = []
        for combo, w in self._combos.items():
            if (combo.high.suit, combo.high.rank) in block_set:
                continue
            if (combo.low.suit, combo.low.rank) in block_set:
                continue
            out.append((combo, w))
        return out

    def remove_blockers(self, blockers: Sequence[Card]) -> "Range":
        """Return a new Range with blocker-containing combos dropped."""
        return Range(dict(self.combo_list(blockers)))

    # ---- Set algebra ----

    def union(self, other: "Range") -> "Range":
        merged = dict(self._combos)
        for c, w in other._combos.items():
            merged[c] = max(merged.get(c, 0.0), w)
        return Range(merged)

    def intersection(self, other: "Range") -> "Range":
        out: Dict[Combo, float] = {}
        for c, w in self._combos.items():
            if c in other._combos:
                out[c] = min(w, other._combos[c])
        return Range(out)

    def scaled(self, factor: float) -> "Range":
        """Multiply every weight by ``factor``."""
        return Range({c: w * factor for c, w in self._combos.items()})

    # ---- Serialization ----

    def class_map(self) -> Dict[str, float]:
        """Collapse combos to class strings with averaged weights.

        Multiple combos of the same class (e.g. all 4 suit-pair
        permutations of AKs) collapse to one entry; the resulting
        weight is the mean of the contributing combo weights, so a
        partial range like {AsKs: 1.0, AhKh: 1.0, AdKd: 0.0, AcKc: 0.0}
        renders as {"AKs": 0.5}.
        """
        sums: Dict[str, float] = {}
        counts: Dict[str, int] = {}
        # Iterate over all possible classes that this range could
        # touch, computing the mean across the 4/6/12 combos of that
        # class.
        for combo, weight in self._combos.items():
            cls_str = combo.to_notation()
            sums[cls_str] = sums.get(cls_str, 0.0) + weight
            counts[cls_str] = counts.get(cls_str, 0) + 1

        # Normalize by the *full* combo count for the class (4 for
        # suited, 12 for offsuit, 6 for pair) so partial-class
        # selections show up as weight < 1.
        out: Dict[str, float] = {}
        for cls_str, total_weight in sums.items():
            full_count = _class_full_combo_count(cls_str)
            out[cls_str] = total_weight / full_count if full_count > 0 else 0.0
        return out

    def __len__(self) -> int:
        return len(self._combos)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Range(<{len(self._combos)} combos, weight={self.combo_count():.2f}>)"


def _class_full_combo_count(cls_str: str) -> int:
    """How many combos exist for one class notation."""
    cls_str = cls_str.upper()
    if len(cls_str) == 2 and cls_str[0] == cls_str[1]:
        return 6
    if cls_str.endswith("S"):
        return 4
    if cls_str.endswith("O"):
        return 12
    return 16  # both s+o combined


# ---- Preflop chart library ----

# Standard preflop opening ranges. Slightly tighter than the
# "modern aggressive" charts; intentionally on the safe side for
# coaching defaults. Frontend can let users edit these.
PREFLOP_CHARTS: Dict[str, str] = {
    "UTG_OPEN": "22+, ATs+, KTs+, QTs+, JTs, T9s, 98s, AJo+, KQo",
    "MP_OPEN": "22+, A9s+, K9s+, Q9s+, J9s+, T8s+, 98s, 87s, ATo+, KJo+, QJo",
    "CO_OPEN": (
        "22+, A2s+, K7s+, Q9s+, J9s+, T8s+, 98s, 87s, 76s, 65s, "
        "A9o+, KTo+, QTo+, JTo"
    ),
    "BTN_OPEN": (
        "22+, A2s+, K2s+, Q5s+, J7s+, T7s+, 97s+, 86s+, 75s+, 64s+, 54s, "
        "A2o+, K8o+, Q9o+, J9o+, T8o+, 98o"
    ),
    "SB_OPEN": (
        "22+, A2s+, K6s+, Q9s+, J9s+, T9s, A7o+, KTo+, QTo+, JTo"
    ),
    "BB_DEFEND": (
        "22+, A2s+, K2s+, Q2s+, J5s+, T6s+, 96s+, 85s+, 75s+, 64s+, 54s, "
        "A2o+, K7o+, Q8o+, J8o+, T8o+, 97o+, 87o, 76o, 65o"
    ),
    "TIGHT_3BET": "QQ+, AKs, AKo",
    "LOOSE_3BET": "TT+, AQs+, AKo, A5s, A4s, KJs, QJs",
}


def preflop_range(name: str) -> Range:
    """Return one of the named preflop charts as a Range.

    Raises ``KeyError`` if the name isn't in ``PREFLOP_CHARTS``.
    """
    spec = PREFLOP_CHARTS[name]
    return Range.from_string(spec)


def list_preflop_charts() -> Dict[str, Dict[str, float]]:
    """Return ``{chart_name: {class_string: weight}}`` for every preset.

    Convenient for the frontend's range-grid component to seed
    presets.
    """
    return {name: preflop_range(name).class_map() for name in PREFLOP_CHARTS}
