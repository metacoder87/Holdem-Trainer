"""GTO advisor: bridges a recorded hero decision to the CFR cache.

The advisor takes a ``decision`` dict produced by
``game_engine._record_hero_decision`` and returns a coach-notes payload
with the cached GTO action distribution, or ``None`` if no advice is
available for this spot.

Design constraints:

  - **Must never raise on a real gameplay code path.** Anything that
    could fail (card parsing, bucketing, file I/O) is caught and
    turned into a ``None`` return. The engine then falls back to its
    existing heuristic grading.

  - **Cheap on the hot path.** The cache hits or misses on a dict
    lookup; the only expensive call is ``hand_bucket`` (Monte Carlo
    equity), and that only runs on cache hit. Cache miss = 1 dict
    lookup + return.

  - **Decoupled from the game engine.** Only depends on the
    ``decision`` dict shape, which is already a structured record.
    Test fixtures can build the dict directly without spinning up a
    full engine.
"""
from __future__ import annotations

import random
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

# The cfr package lives under src/ which isn't always on sys.path when
# the backend is imported (e.g. from FastAPI startup). Add it once.
_SRC = Path(__file__).resolve().parents[3] / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from cfr.abstractions.hand_bucketing import (  # noqa: E402
    DEFAULT_BUCKETS,
    DEFAULT_POTENTIAL_WEIGHT,
    hand_bucket,
    potential_aware_bucket,
)
from cfr.cache import SolverCache  # noqa: E402
from cfr.policy import Policy  # noqa: E402
from cfr.spot import SpotKey  # noqa: E402

# Lazy-loaded Card type so importing this module doesn't drag the
# entire game stack into the request path unless we actually compute
# a bucket.
try:
    from game.card import Card, Rank, Suit  # noqa: E402
except ImportError:  # pragma: no cover - exercised in some test setups
    Card = Rank = Suit = None  # type: ignore[assignment]


# Default cache root: <repo>/backend/cfr_artifacts. The precompute
# script writes here; the runtime reads here.
_DEFAULT_CACHE_ROOT = Path(__file__).resolve().parents[2] / "cfr_artifacts"


# Map engine action strings (PlayerAction.value lower-cased) to the
# coarse GTO action categories used by the postflop subgame.
_ACTION_CATEGORY_MAP = {
    "fold": "FOLD",
    "check": "CHECK_OR_CALL",
    "call": "CHECK_OR_CALL",
    "raise": "RAISE",
    "bet": "RAISE",
    "all_in": "ALL_IN",
    "all-in": "ALL_IN",
}


# Module-level cache handle. Lazy-initialized on first call so import
# of this module is side-effect-free.
_CACHE: Optional[SolverCache] = None
_CACHE_ROOT: Optional[Path] = None


def configure(cache_root: Path | str) -> None:
    """Override the default cache root (used in tests + custom deploys)."""
    global _CACHE, _CACHE_ROOT
    _CACHE_ROOT = Path(cache_root)
    _CACHE = None  # force re-open on next use


def _get_cache() -> SolverCache:
    global _CACHE
    if _CACHE is None:
        root = _CACHE_ROOT or _DEFAULT_CACHE_ROOT
        _CACHE = SolverCache.open(root)
    return _CACHE


def reset_cache() -> None:
    """Drop the cached cache handle (test cleanup)."""
    global _CACHE
    _CACHE = None


# ---------- Helpers ----------


def _parse_engine_card(card_str: str):
    """Parse a card produced by ``str(Card)`` back to a Card object.

    Cards print as ``f"{rank}{suit}"`` where rank is one of
    ``2-10, J, Q, K, A`` (10 stays as ``10``) and suit is the unicode
    symbol. We accept both that form and the ASCII suit form
    (``Ks``, ``As``, etc.) for robustness.
    """
    if Card is None:
        raise RuntimeError("game.card unavailable; install path is broken")

    cleaned = str(card_str).strip()
    # Normalize unicode suit symbols to ASCII letters.
    suit_glyphs = {"♥": "h", "♦": "d", "♣": "c", "♠": "s"}
    for glyph, letter in suit_glyphs.items():
        cleaned = cleaned.replace(glyph, letter)

    suit_letter = cleaned[-1].lower()
    rank_part = cleaned[:-1].upper()
    rank_map = {
        "2": Rank.TWO, "3": Rank.THREE, "4": Rank.FOUR, "5": Rank.FIVE,
        "6": Rank.SIX, "7": Rank.SEVEN, "8": Rank.EIGHT, "9": Rank.NINE,
        "10": Rank.TEN, "T": Rank.TEN,
        "J": Rank.JACK, "Q": Rank.QUEEN, "K": Rank.KING, "A": Rank.ACE,
    }
    suit_map = {"h": Suit.HEARTS, "d": Suit.DIAMONDS, "c": Suit.CLUBS, "s": Suit.SPADES}
    return Card(suit_map[suit_letter], rank_map[rank_part])


@lru_cache(maxsize=4096)
def _bucket_for_canonical(
    hole_cards: Tuple[str, str],
    board: Tuple[str, ...],
    num_buckets: int,
    bucketing: str,
    potential_weight: float,
) -> Optional[int]:
    """Cached bucket compute keyed by *canonical* card tuples.

    Bucketing method is part of the cache key so a single hand can
    legitimately get different bucket IDs under "plain" vs
    "potential" weighting without clobbering each other in the LRU.
    """
    try:
        hole = [_parse_engine_card(c) for c in hole_cards]
        community = [_parse_engine_card(c) for c in board]
    except (KeyError, ValueError, RuntimeError):
        return None
    try:
        if bucketing == "potential":
            return potential_aware_bucket(
                hole,
                community,
                num_buckets=num_buckets,
                weight=potential_weight,
                # Deterministic RNG so coach output is reproducible.
                rng=random.Random(0x60A1),
            )
        return hand_bucket(
            hole,
            community,
            num_buckets=num_buckets,
            rng=random.Random(0x60A1),
        )
    except (ValueError, RuntimeError):
        return None


def _hero_bucket(
    hole_cards: Sequence[str],
    board: Sequence[str],
    *,
    num_buckets: int = DEFAULT_BUCKETS,
    bucketing: str = "plain",
    potential_weight: float = DEFAULT_POTENTIAL_WEIGHT,
) -> Optional[int]:
    """Convert string cards to a strength bucket. Returns None on failure.

    ``bucketing`` must match the method used when the target Policy
    was trained. Cache meta now records this so callers can read it
    from the entry and pass it through here.
    """
    if not hole_cards or len(hole_cards) != 2:
        return None
    hole_tuple = (str(hole_cards[0]), str(hole_cards[1]))
    board_tuple = tuple(str(c) for c in board)
    return _bucket_for_canonical(
        hole_tuple,
        board_tuple,
        num_buckets,
        bucketing,
        potential_weight,
    )


def _infer_history(decision: Dict[str, Any]) -> Optional[str]:
    """Heuristic mapping of decision context to subgame action history.

    The CFR subgame keys infosets by ``b=<bucket>|h=<history>`` where
    history is a short string of action characters:

      ``""``   -- subgame root, first to act, no bet outstanding
      ``"k"``  -- second to act, opponent checked, no bet outstanding
      ``"r"``  -- second to act, facing a bet (single raise/bet)

    Deeper sequences ("krk", "rcr") aren't yet covered by the v1
    precompute set; we return None for those so the caller falls back
    to the heuristic grader.
    """
    to_call = int(decision.get("to_call") or 0)
    can_check = bool(decision.get("can_check"))
    first_actor = int(decision.get("hero_position") or 0)

    if to_call > 0:
        # We're facing a bet on this street.
        return "r"
    if can_check and first_actor == 0:
        # First to act, no bet -> subgame root.
        return ""
    if can_check and first_actor != 0:
        # Second to act, no bet -> opponent checked.
        return "k"
    return None


def _aggregate_actions(probs: Dict[str, float]) -> Dict[str, float]:
    """Collapse the fine-grained policy actions to engine-level categories.

    Input keys look like ``CHECK_OR_CALL``, ``FOLD``, ``RAISE_0.33``,
    ``RAISE_0.66``, ``RAISE_1.0``, ``ALL_IN``. We collapse the various
    raise sizes to ``RAISE`` because the engine decision only records
    a single ``raise`` action; the precise sizing is captured in
    ``chosen_amount``.
    """
    out: Dict[str, float] = {"FOLD": 0.0, "CHECK_OR_CALL": 0.0, "RAISE": 0.0, "ALL_IN": 0.0}
    for action, prob in probs.items():
        if action == "FOLD":
            out["FOLD"] += prob
        elif action == "CHECK_OR_CALL":
            out["CHECK_OR_CALL"] += prob
        elif action == "ALL_IN":
            out["ALL_IN"] += prob
        elif action.startswith("RAISE"):
            out["RAISE"] += prob
        # Anything unknown is silently dropped.
    # Normalize to defend against rounding error / unknown buckets.
    total = sum(out.values())
    if total > 0 and abs(total - 1.0) > 1e-6:
        for k in out:
            out[k] = out[k] / total
    return out


def _classify_chosen(decision: Dict[str, Any]) -> Optional[str]:
    """Engine action -> aggregated GTO category."""
    raw = str(decision.get("chosen_action") or "").lower().replace("-", "_").strip()
    cat = _ACTION_CATEGORY_MAP.get(raw)
    if cat is None:
        return None
    return "RAISE" if cat == "RAISE" else cat


def _label_for(action: str, decision: Dict[str, Any]) -> str:
    """User-facing label for a GTO action category."""
    if action == "FOLD":
        return "fold"
    if action == "CHECK_OR_CALL":
        return "check" if bool(decision.get("can_check")) else "call"
    if action == "RAISE":
        return "raise"
    if action == "ALL_IN":
        return "all-in"
    return action.lower()


def _ev_delta_bb(
    hero_action: Optional[str],
    aggregated: Dict[str, float],
    *,
    pot_bb: int,
) -> Optional[float]:
    """Frequency-based EV-delta estimate, in BB.

    The intuition: GTO at this spot picks ``argmax(aggregated)`` most
    of the time. If you took an action GTO picks rarely, you're
    almost certainly leaking EV; if you took GTO's modal action, EV
    delta is ~zero. We don't have per-action value estimates in the
    Policy yet, so we approximate the cost as ::

        ev_delta_bb = (gto_top_freq - hero_freq) * pot_bb * leak_factor

    ``leak_factor = 0.15`` calibrates the BB cost against a typical
    "this is the wrong third of the time" CFR spot. Real per-action
    EV will replace this once we extend the policy format.
    """
    if hero_action is None or not aggregated:
        return None
    top_action = max(aggregated, key=aggregated.get)
    top_freq = aggregated[top_action]
    hero_freq = aggregated.get(hero_action, 0.0)
    if hero_action == top_action:
        return 0.0
    delta = (top_freq - hero_freq) * pot_bb * 0.15
    # Round to one decimal; users don't need more precision than that.
    return round(-abs(delta), 1)


# ---------- Public entry point ----------


def gto_advice(
    decision: Dict[str, Any],
    *,
    big_blind: int = 1,
    cache: Optional[SolverCache] = None,
) -> Optional[Dict[str, Any]]:
    """Return GTO coaching for ``decision`` or None if not cached.

    The shape on success::

        {
            "gto_action": "raise",
            "gto_frequency": 0.72,
            "hero_action": "call",
            "hero_frequency": 0.18,
            "ev_delta_bb": -1.4,
            "action_breakdown": {"raise": 0.72, "call": 0.20, "fold": 0.08},
            "source": "cache",
            "spot_signature": "flop__Aa-Kb-2c__p20__spr2__fa0",
            "iterations": 5000,
        }
    """
    try:
        spot = SpotKey.from_decision(decision, big_blind=big_blind)
        if spot is None:
            return None

        cache = cache or _get_cache()
        if not cache.has(spot):
            return None
        policy = cache.get(spot)
        if policy is None:
            return None

        # Bucket count + method must match what the cache was trained
        # with. Falls back to plain bucketing for legacy entries.
        entry = cache.entry(spot)
        meta = entry.meta if (entry and entry.meta) else {}
        num_buckets = int(meta.get("num_buckets") or DEFAULT_BUCKETS)
        bucketing = str(meta.get("bucketing") or "plain").lower()
        if bucketing not in {"plain", "potential"}:
            bucketing = "plain"
        try:
            potential_weight = float(
                meta.get("potential_weight") or DEFAULT_POTENTIAL_WEIGHT
            )
        except (TypeError, ValueError):
            potential_weight = DEFAULT_POTENTIAL_WEIGHT

        bucket = _hero_bucket(
            decision.get("hero_hole_cards") or [],
            decision.get("board") or [],
            num_buckets=num_buckets,
            bucketing=bucketing,
            potential_weight=potential_weight,
        )
        if bucket is None:
            return None

        history = _infer_history(decision)
        if history is None:
            return None

        infoset_key = f"b={bucket}|h={history}"
        probs = policy.probs(infoset_key)
        if not probs:
            return None

        aggregated = _aggregate_actions(probs)
        chosen = _classify_chosen(decision)
        top_action = max(aggregated, key=aggregated.get)

        return {
            "gto_action": _label_for(top_action, decision),
            "gto_frequency": round(aggregated[top_action], 3),
            "hero_action": _label_for(chosen, decision) if chosen else None,
            "hero_frequency": round(aggregated.get(chosen, 0.0), 3) if chosen else None,
            "ev_delta_bb": _ev_delta_bb(chosen, aggregated, pot_bb=spot.pot_bb),
            "action_breakdown": {
                _label_for(a, decision): round(p, 3) for a, p in aggregated.items() if p > 0.0
            },
            "source": "cache",
            "spot_signature": spot.signature(),
            "iterations": entry.iterations if entry else None,
        }
    except Exception:
        # Last-resort guard. Coach advice is best-effort; we never
        # want to break gameplay because of it.
        return None
