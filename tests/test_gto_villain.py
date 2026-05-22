"""GTOAIPlayer tests.

The GTO villain should:

  - Sample actions from the cached policy when a spot is covered.
  - Fall back to BalancedAI logic on cache miss (no crash, returns a
    legal action).
  - Never raise from make_decision, even with degenerate inputs.
  - Track hit/miss counts so the wiring can be inspected at runtime.
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

from cfr.cache import SolverCache
from cfr.policy import Policy
from cfr.spot import SpotKey
from game.ai_player import (
    AIStyle,
    BalancedAI,
    GTOAIPlayer,
    create_ai_player,
)
from game.card import Card, Rank, Suit
from game.player import PlayerAction


def _make_card(rank: Rank, suit: Suit) -> Card:
    return Card(suit, rank)


def _spot_for_game_state() -> SpotKey:
    """Match the SpotKey produced by the game_state below."""
    return SpotKey(
        street="flop",
        board_canonical="Aa,Kb,2c",
        pot_bb=30,
        spr_bucket=2,
        first_actor=0,
    )


def _game_state(**overrides) -> dict:
    base = {
        "betting_round": "flop",
        "pot_size": 60,           # 30 BB at BB=2
        "current_bet": 0,
        "call_amount": 0,
        "min_raise": 4,
        "big_blind": 2,
        "community_cards": [
            _make_card(Rank.ACE, Suit.HEARTS),
            _make_card(Rank.KING, Suit.DIAMONDS),
            _make_card(Rank.TWO, Suit.CLUBS),
        ],
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _seed():
    random.seed(7)
    yield


@pytest.fixture
def gto_villain(tmp_path: Path) -> GTOAIPlayer:
    """A GTOAIPlayer with a cache rooted in tmp_path."""
    villain = GTOAIPlayer(
        "TestVillain",
        bankroll=240,
        epsilon=0.0,            # no exploration noise
        cache_root=str(tmp_path),
    )
    # Hole cards: AKs (top pair top kicker bucket).
    villain.hole_cards = [
        _make_card(Rank.ACE, Suit.SPADES),
        _make_card(Rank.KING, Suit.SPADES),
    ]
    villain.position = 0  # OOP
    villain.current_bet = 0
    return villain


def _seed_cache(cache_root: Path, spot: SpotKey, policy: Policy) -> None:
    cache = SolverCache.open(cache_root)
    cache.put(spot, policy, iterations=42, meta={"num_buckets": 5})


# ---------- Factory & construction ----------


def test_create_ai_player_returns_gto_for_gto_style(tmp_path):
    player = create_ai_player("Bot", 1000, AIStyle.GTO)
    assert isinstance(player, GTOAIPlayer)
    assert player.ai_style == AIStyle.GTO


def test_gto_player_inherits_balanced_fallback():
    """The villain falls back to BalancedAI on cache miss."""
    assert issubclass(GTOAIPlayer, BalancedAI)


def test_gto_player_no_cache_returns_balanced_decision(tmp_path, gto_villain):
    """Empty cache -> villain still produces a legal action."""
    action, amount = gto_villain.make_decision(_game_state())
    assert isinstance(action, PlayerAction)
    assert amount >= 0
    assert gto_villain.gto_hits == 0
    assert gto_villain.gto_misses == 1


# ---------- Cache hit path ----------


def test_gto_player_samples_from_cache_when_covered(tmp_path, gto_villain):
    """100% fold policy -> villain folds (well, checks because can_check)."""
    spot = _spot_for_game_state()
    # Bucket 4 = top bucket with 5 buckets and AKs on AKx flop.
    policy = Policy({f"b=4|h=": {"FOLD": 1.0}})
    _seed_cache(tmp_path, spot, policy)

    action, _amount = gto_villain.make_decision(_game_state())
    # Engine can't fold a free check; villain checks instead.
    assert action == PlayerAction.CHECK
    assert gto_villain.gto_hits == 1


def test_gto_player_raises_when_policy_says_raise(tmp_path, gto_villain):
    spot = _spot_for_game_state()
    policy = Policy({f"b=4|h=": {"RAISE_0.66": 1.0}})
    _seed_cache(tmp_path, spot, policy)

    action, amount = gto_villain.make_decision(_game_state())
    assert action == PlayerAction.RAISE
    # 0.66 * (60 + 0) = ~40, rounded to nearest 5
    assert amount == 40
    assert gto_villain.gto_hits == 1


def test_gto_player_calls_when_policy_says_check_call_facing_bet(tmp_path, gto_villain):
    """CHECK_OR_CALL with a bet outstanding maps to CALL."""
    spot = _spot_for_game_state()
    policy = Policy({f"b=4|h=r": {"CHECK_OR_CALL": 1.0}})
    _seed_cache(tmp_path, spot, policy)

    gs = _game_state(current_bet=30, call_amount=30)
    action, amount = gto_villain.make_decision(gs)
    assert action == PlayerAction.CALL
    assert amount == 30
    assert gto_villain.gto_hits == 1


def test_gto_player_all_in_when_policy_says_all_in(tmp_path, gto_villain):
    spot = _spot_for_game_state()
    policy = Policy({f"b=4|h=": {"ALL_IN": 1.0}})
    _seed_cache(tmp_path, spot, policy)

    action, amount = gto_villain.make_decision(_game_state())
    assert action == PlayerAction.ALL_IN
    assert amount == gto_villain.bankroll
    assert gto_villain.gto_hits == 1


def test_gto_player_falls_back_when_bucket_missing(tmp_path, gto_villain):
    """Policy covers bucket 0 only -> high-bucket hand falls back."""
    spot = _spot_for_game_state()
    policy = Policy({f"b=0|h=": {"FOLD": 1.0}})
    _seed_cache(tmp_path, spot, policy)

    action, _ = gto_villain.make_decision(_game_state())
    assert isinstance(action, PlayerAction)
    assert gto_villain.gto_hits == 0
    assert gto_villain.gto_misses == 1


# ---------- Epsilon-greedy ----------


def test_gto_player_epsilon_one_always_falls_back(tmp_path, gto_villain):
    """epsilon=1 -> never uses the cached strategy."""
    gto_villain.epsilon = 1.0
    spot = _spot_for_game_state()
    _seed_cache(tmp_path, spot, Policy({f"b=4|h=": {"RAISE_0.66": 1.0}}))

    # Run 10 decisions; all should fall back.
    for _ in range(10):
        gto_villain.make_decision(_game_state())
    assert gto_villain.gto_hits == 0
    assert gto_villain.gto_misses == 10


def test_gto_player_distribution_matches_policy_at_zero_epsilon(tmp_path):
    """Sampling at epsilon=0 follows the policy over many trials."""
    spot = _spot_for_game_state()
    policy = Policy(
        {f"b=4|h=": {"RAISE_0.66": 0.8, "CHECK_OR_CALL": 0.2}}
    )
    _seed_cache(tmp_path, spot, policy)

    villain = GTOAIPlayer("Bot", 240, epsilon=0.0, cache_root=str(tmp_path))
    villain.hole_cards = [
        _make_card(Rank.ACE, Suit.SPADES),
        _make_card(Rank.KING, Suit.SPADES),
    ]
    villain.position = 0
    counts = {"RAISE": 0, "CHECK": 0}

    random.seed(42)
    for _ in range(200):
        action, _ = villain.make_decision(_game_state())
        if action == PlayerAction.RAISE:
            counts["RAISE"] += 1
        elif action == PlayerAction.CHECK:
            counts["CHECK"] += 1

    # 0.8 +/- some noise -> at least 60% raises out of 200.
    assert counts["RAISE"] >= 120
    assert counts["CHECK"] >= 20


# ---------- Robustness ----------


def test_gto_player_handles_missing_hole_cards_gracefully(tmp_path):
    villain = GTOAIPlayer("Bot", 240, cache_root=str(tmp_path))
    villain.hole_cards = []  # malformed
    villain.position = 0
    action, _ = villain.make_decision(_game_state())
    assert isinstance(action, PlayerAction)
    assert villain.gto_misses == 1


def test_gto_player_handles_empty_community(tmp_path):
    villain = GTOAIPlayer("Bot", 240, cache_root=str(tmp_path))
    villain.hole_cards = [
        _make_card(Rank.ACE, Suit.SPADES),
        _make_card(Rank.KING, Suit.SPADES),
    ]
    villain.position = 0
    gs = _game_state(community_cards=[], betting_round="preflop")
    action, _ = villain.make_decision(gs)
    # Preflop has no SpotKey -> fallback.
    assert isinstance(action, PlayerAction)
    assert villain.gto_misses == 1
