"""Canonical key for cached postflop spots.

A ``SpotKey`` identifies a CFR-solvable subgame independent of the
absolute chip values used at runtime. Two situations that are
strategically equivalent (same canonical board, same pot relative to
stack, same actor order) collapse to the same key, so the cache stays
small and hit-rates stay high.

The canonicalization rules:

  - **Board**: suit-isomorphic. ``A♥ K♦ 2♣`` and ``A♠ K♣ 2♦`` are the
    same spot (both rainbow A-K-2). We collapse suits to letters
    ``a/b/c/d`` in the order they first appear, and sort cards by rank
    so the order of dealing is irrelevant.

  - **Pot**: discretized in BB to keep the cache from exploding on
    tiny chip-level variation. Default rounding: nearest 5 BB up to
    100 BB, then nearest 10 BB.

  - **SPR (stack-to-pot ratio)**: 5 buckets covering the strategically
    distinct ranges. SPR is what actually drives the postflop tree
    shape; raw stack size doesn't.

  - **first_actor**: 0 = OOP (out of position), 1 = IP. The CFR
    solver's first_actor field uses the same convention.

Decision dicts produced by ``game_engine._record_hero_decision`` carry
all the inputs needed; ``SpotKey.from_decision`` does the conversion.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


# Mirror of cfr.abstractions.hand_bucketing.DEFAULT_BUCKETS so callers
# don't have to import the abstractions module to construct keys.
DEFAULT_NUM_BUCKETS = 10


# Suit symbols we accept on input. The game engine prints cards via
# ``str(Card)`` which uses the unicode suit characters.
_SUIT_SYMBOLS = {"♥": "H", "♦": "D", "♣": "C", "♠": "S"}
_SUIT_LETTERS = {"H", "D", "C", "S", "h", "d", "c", "s"}

# Rank glyph -> numeric value (Two..Ace = 2..14).
_RANK_LOOKUP = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "10": 10, "T": 10, "t": 10,
    "J": 11, "j": 11,
    "Q": 12, "q": 12,
    "K": 13, "k": 13,
    "A": 14, "a": 14,
}


# Streets known to the cache. Preflop is intentionally excluded; preflop
# is covered by canonical range charts, not by the CFR cache.
_KNOWN_STREETS = ("flop", "turn", "river")

# SPR bucket boundaries. Bucket i covers (bounds[i], bounds[i+1]].
# Last bucket is unbounded above.
_SPR_BUCKET_BOUNDS = (0.0, 3.0, 6.0, 12.0, 25.0)


def _parse_card(card_str: str) -> tuple[int, str]:
    """Parse a card string like 'A♠' or 'Ks' to (rank_value, suit_letter).

    Suit letter is normalized to upper case H/D/C/S regardless of input
    format. Raises ValueError on unparseable input.
    """
    if not isinstance(card_str, str):
        raise ValueError(f"card must be a string, got {type(card_str).__name__}")
    cleaned = card_str.strip()
    if not cleaned:
        raise ValueError("empty card string")

    # Normalize any unicode suit glyphs to ASCII letters.
    for glyph, letter in _SUIT_SYMBOLS.items():
        cleaned = cleaned.replace(glyph, letter)

    # The last character is the suit; everything before it is the rank.
    suit = cleaned[-1]
    rank_part = cleaned[:-1]
    if suit not in _SUIT_LETTERS:
        raise ValueError(f"unknown suit in {card_str!r}")
    rank = _RANK_LOOKUP.get(rank_part)
    if rank is None:
        raise ValueError(f"unknown rank in {card_str!r}")
    return rank, suit.upper()


def _rank_glyph(value: int) -> str:
    """Inverse of _RANK_LOOKUP for emitting canonical board strings."""
    if value <= 9:
        return str(value)
    return {10: "T", 11: "J", 12: "Q", 13: "K", 14: "A"}[value]


def canonical_board(cards: Sequence[str]) -> str:
    """Suit-isomorphic canonical key for a sequence of community cards.

    Examples (all hashed identically)::

        canonical_board(['A♥', 'K♦', '2♣']) == 'Aa,Kb,2c'
        canonical_board(['A♠', 'K♣', '2♦']) == 'Aa,Kb,2c'

    Ranks are not reordered: card order matters for the strategic
    meaning (turn card vs river card), so we preserve it. Suit
    letters are re-mapped in the order suits first appear.
    """
    if not cards:
        return ""
    parsed = [_parse_card(c) for c in cards]
    suit_map: dict[str, str] = {}
    next_letter = ord("a")
    parts: list[str] = []
    for rank_value, suit in parsed:
        if suit not in suit_map:
            suit_map[suit] = chr(next_letter)
            next_letter += 1
        parts.append(f"{_rank_glyph(rank_value)}{suit_map[suit]}")
    return ",".join(parts)


def spr_bucket_for(spr: float) -> int:
    """Map raw SPR to a bucket index in [0, len(_SPR_BUCKET_BOUNDS)-1]."""
    if spr is None or spr != spr:  # None or NaN
        return 0
    for idx, upper in enumerate(_SPR_BUCKET_BOUNDS):
        if spr <= upper:
            return idx
    return len(_SPR_BUCKET_BOUNDS)


def pot_bb_discretize(pot_bb: float) -> int:
    """Round pot in BB to a coarser bucket the cache can hit reliably.

      <= 100 BB:  nearest 5
      <= 500 BB:  nearest 25
      otherwise:  nearest 100
    """
    if pot_bb is None or pot_bb != pot_bb:
        return 0
    if pot_bb <= 0:
        return 0
    if pot_bb <= 100:
        return int(round(pot_bb / 5.0) * 5) or 5
    if pot_bb <= 500:
        return int(round(pot_bb / 25.0) * 25)
    return int(round(pot_bb / 100.0) * 100)


def _street_for_board(board: Sequence[str]) -> Optional[str]:
    """Infer street from number of community cards. Returns None if invalid."""
    n = len(board) if board else 0
    if n == 3:
        return "flop"
    if n == 4:
        return "turn"
    if n == 5:
        return "river"
    return None


@dataclass(frozen=True)
class SpotKey:
    """Hashable, disk-stable identifier for a cached subgame.

    Equality and hashing fall through to dataclass-frozen defaults; the
    ``signature`` is the form used as the cache-file basename.
    """

    street: str
    board_canonical: str
    pot_bb: int
    spr_bucket: int
    first_actor: int

    def __post_init__(self) -> None:  # type: ignore[override]
        if self.street not in _KNOWN_STREETS:
            raise ValueError(
                f"street must be one of {_KNOWN_STREETS!r}, got {self.street!r}"
            )
        if self.first_actor not in (0, 1):
            raise ValueError(
                f"first_actor must be 0 (OOP) or 1 (IP), got {self.first_actor!r}"
            )
        if self.pot_bb < 0:
            raise ValueError(f"pot_bb must be >= 0, got {self.pot_bb!r}")
        if self.spr_bucket < 0 or self.spr_bucket > len(_SPR_BUCKET_BOUNDS):
            raise ValueError(f"spr_bucket out of range: {self.spr_bucket!r}")

    def signature(self) -> str:
        """Filename-safe signature string. Stable across processes."""
        # Suit letters and digits already safe; replace comma to keep it
        # filesystem-friendly on Windows where commas in filenames are
        # legal but visually ugly.
        board = self.board_canonical.replace(",", "-") or "empty"
        return (
            f"{self.street}__{board}"
            f"__p{self.pot_bb}__spr{self.spr_bucket}"
            f"__fa{self.first_actor}"
        )

    @classmethod
    def from_decision(
        cls,
        decision: dict,
        *,
        big_blind: int = 1,
    ) -> Optional["SpotKey"]:
        """Build a SpotKey from a ``decision`` dict, or None if unparseable.

        Returns None (rather than raising) when:

          - The street is not flop/turn/river (e.g. preflop or unknown).
          - The board is missing or malformed.
          - Pot or stack data is missing.

        The caller is expected to treat None as "this spot isn't
        eligible for cached GTO advice" and fall back to its existing
        heuristic.
        """
        try:
            board = decision.get("board") or []
            street_hint = str(decision.get("betting_round") or "").lower()
            if street_hint not in _KNOWN_STREETS:
                street = _street_for_board(board)
                if street is None:
                    return None
            else:
                street = street_hint

            board_key = canonical_board(board)
            if not board_key and street in _KNOWN_STREETS:
                return None

            pot_total = float(decision.get("pot_total") or 0)
            hero_stack = float(decision.get("hero_stack") or 0)
            bb = max(1, int(big_blind))
            pot_bb_raw = pot_total / bb
            pot_bb = pot_bb_discretize(pot_bb_raw)
            if pot_bb <= 0:
                return None
            spr = (hero_stack / pot_total) if pot_total > 0 else 0.0
            spr_bucket = spr_bucket_for(spr)

            # Hero is the *acting* player at this decision; convention
            # we adopt: position == 0 means "earliest seat" which in HU
            # is the small blind, post-flop the OOP player. For 3+
            # handed, we still treat hero_position == 0 as OOP for
            # bucketing purposes. Refine in v2 with real positional
            # mapping.
            hero_position = int(decision.get("hero_position") or 0)
            first_actor = 0 if hero_position == 0 else 1

            return cls(
                street=street,
                board_canonical=board_key,
                pot_bb=pot_bb,
                spr_bucket=spr_bucket,
                first_actor=first_actor,
            )
        except (ValueError, TypeError):
            return None


def iter_spr_bounds() -> Iterable[float]:
    """Expose SPR bucket bounds for downstream test/inspection."""
    return tuple(_SPR_BUCKET_BOUNDS)
