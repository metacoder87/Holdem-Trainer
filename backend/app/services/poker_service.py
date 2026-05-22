"""Backend service for Track 5 poker math endpoints.

Wraps the pure-math layer in ``src.poker`` for API consumption:
  - GET  /api/poker/preflop-charts  -> named preflop ranges (class maps)
  - POST /api/poker/range-equity    -> equity calc for arbitrary ranges/board

All inputs are validated and shaped here so the route handlers can
stay thin. Card parsing tolerates the suit-symbol form (``A♥``) and
the ASCII form (``Ah``) interchangeably.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Make sure src/ is importable. Same trick used by gto_advisor.
_SRC = Path(__file__).resolve().parents[3] / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from game.card import Card, Rank, Suit  # noqa: E402
from poker.range import (  # noqa: E402
    PREFLOP_CHARTS,
    Range,
    list_preflop_charts,
    preflop_range,
)
from poker.range_equity import multiway_range_equity  # noqa: E402


_RANK_LOOKUP: Dict[str, Rank] = {
    "2": Rank.TWO, "3": Rank.THREE, "4": Rank.FOUR, "5": Rank.FIVE,
    "6": Rank.SIX, "7": Rank.SEVEN, "8": Rank.EIGHT, "9": Rank.NINE,
    "T": Rank.TEN, "10": Rank.TEN, "J": Rank.JACK, "Q": Rank.QUEEN,
    "K": Rank.KING, "A": Rank.ACE,
}

_SUIT_LOOKUP: Dict[str, Suit] = {
    "h": Suit.HEARTS, "♥": Suit.HEARTS,
    "d": Suit.DIAMONDS, "♦": Suit.DIAMONDS,
    "c": Suit.CLUBS, "♣": Suit.CLUBS,
    "s": Suit.SPADES, "♠": Suit.SPADES,
}


def _parse_card(token: str) -> Card:
    """Parse 'Ah', 'A♥', 'Th', '10s' into a Card."""
    cleaned = token.strip()
    if not cleaned:
        raise ValueError("empty card token")
    last = cleaned[-1]
    suit = _SUIT_LOOKUP.get(last) or _SUIT_LOOKUP.get(last.lower())
    if suit is None:
        raise ValueError(f"unknown suit in {token!r}")
    rank_str = cleaned[:-1].upper()
    rank = _RANK_LOOKUP.get(rank_str)
    if rank is None:
        raise ValueError(f"unknown rank in {token!r}")
    return Card(suit, rank)


def _parse_cards(tokens: Sequence[str]) -> List[Card]:
    return [_parse_card(t) for t in tokens]


def get_preflop_charts() -> Dict[str, Any]:
    """Return all named preflop charts in class-map form.

    Response shape::
        {
            "charts": {
                "UTG_OPEN": {"AA": 1.0, "KK": 1.0, ...},
                "BTN_OPEN": {...},
                ...
            },
            "raw": {
                "UTG_OPEN": "22+, ATs+, ...",
                ...
            }
        }

    ``charts`` is what the frontend grid renders; ``raw`` is the
    notation string so users can paste it back into a range editor.
    """
    return {
        "charts": list_preflop_charts(),
        "raw": dict(PREFLOP_CHARTS),
    }


def compute_range_equity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Compute multiway equity from a request payload.

    Expected payload::

        {
            "players": [
                # Each entry is one of:
                {"hand": ["Ah", "Kh"]},                           # fixed pair
                {"range": "22+, AKs"},                             # notation string
                {"preflop_chart": "UTG_OPEN"},                     # named chart
            ],
            "board": ["Qs", "Jh", "2d"],     # optional, 0/3/4/5 cards
            "trials": 1500                    # optional
        }

    Returns::

        {
            "equities": [0.62, 0.38],
            "players": [
                {"label": "Hand: AhKh", "equity": 0.62, "combo_count": 1},
                {"label": "Range: 22+, AKs", "equity": 0.38, "combo_count": 34}
            ],
            "trials": 1500,
            "board": ["Qs", "Jh", "2d"]
        }
    """
    players_in = payload.get("players") or []
    if not players_in or len(players_in) < 2:
        raise ValueError("Need at least 2 players to compute equity.")
    if len(players_in) > 9:
        raise ValueError("Cannot compute equity for more than 9 players.")

    hands_or_ranges: List = []
    labels: List[str] = []
    combo_counts: List[int] = []

    for i, entry in enumerate(players_in):
        if not isinstance(entry, dict):
            raise ValueError(f"player {i} must be an object")
        if "hand" in entry:
            cards = _parse_cards(entry["hand"])
            if len(cards) != 2:
                raise ValueError(f"player {i} hand must be exactly 2 cards")
            hands_or_ranges.append(cards)
            labels.append(f"Hand: {entry['hand'][0]}{entry['hand'][1]}")
            combo_counts.append(1)
        elif "range" in entry:
            rng = Range.from_string(str(entry["range"]))
            if rng.total_combos() == 0:
                raise ValueError(f"player {i} range is empty")
            hands_or_ranges.append(rng)
            labels.append(f"Range: {entry['range']}")
            combo_counts.append(rng.total_combos())
        elif "preflop_chart" in entry:
            name = str(entry["preflop_chart"])
            try:
                rng = preflop_range(name)
            except KeyError:
                raise ValueError(f"unknown preflop chart: {name!r}")
            hands_or_ranges.append(rng)
            labels.append(f"Chart: {name}")
            combo_counts.append(rng.total_combos())
        else:
            raise ValueError(f"player {i} needs 'hand', 'range', or 'preflop_chart'")

    board_tokens = payload.get("board") or []
    if not isinstance(board_tokens, list):
        raise ValueError("board must be a list of card tokens")
    if len(board_tokens) not in (0, 3, 4, 5):
        raise ValueError("board must be 0, 3, 4, or 5 cards")
    board = _parse_cards(board_tokens)

    trials_raw = payload.get("trials")
    trials: Optional[int] = None
    if trials_raw is not None:
        trials_int = int(trials_raw)
        if not (50 <= trials_int <= 50000):
            raise ValueError("trials must be in [50, 50000]")
        trials = trials_int

    equities = multiway_range_equity(
        hands_or_ranges, board=board if board else None, trials=trials
    )

    return {
        "equities": [round(e, 4) for e in equities],
        "players": [
            {
                "label": labels[i],
                "equity": round(equities[i], 4),
                "combo_count": combo_counts[i],
            }
            for i in range(len(labels))
        ],
        "trials": trials,
        "board": list(board_tokens),
    }
