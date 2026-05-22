"""Regression tests for the three pre-Track-3 bug fixes.

Bug A1: ``_complete_hand`` previously swallowed all ValueError /
AttributeError silently with ``pass``. A real pot-distribution
exception could vanish here and players' winnings would disappear.
We now log instead. The tests verify normal flows still complete.

Bug A2: ``_distribute_pot`` could leave chips on the floor when
``Pot.distribute_to_winners`` returned an empty dict (e.g. due to
eligible-players / best-hands intersection being empty). Now it
defensively splits any uncredited remainder among the winners.

Bug A3: ``_record_hero_decision`` and ``_normalize_recommendation``
could both recommend "fold" when ``can_check`` was True. Fold is
strictly dominated by check (both cost 0; check preserves equity)
so we hard-clamp that case.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
BACKEND = REPO_ROOT / "backend"
for p in (SRC, BACKEND):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.services.game_service import _normalize_recommendation
from game.card import Card, Rank, Suit
from game.game_engine import GameEngine
from game.player import Player
from game.pot import Pot


# ---------- Bug A2: defensive _distribute_pot ----------


class _NullHandler:
    def get_menu_choice(self, options, prompt=""):
        return 1

    def get_number_input(self, *a, **kw):
        return 1.0

    def get_yes_no_input(self, *a, **kw):
        return False


def _make_engine(hero_bankroll=10_000):
    hero = Player("Hero", bankroll=hero_bankroll)
    engine = GameEngine(
        hero,
        data_manager=None,
        display=None,
        input_handler=_NullHandler(),
    )
    engine._test_mode = True
    engine.start_game(
        {
            "type": "cash",
            "limit": "no_limit",
            "small_blind": 50,
            "big_blind": 100,
            "max_players": 2,
        }
    )
    return engine, hero


def test_distribute_pot_credits_chips_even_when_best_hands_empty():
    """The fallback path now correctly splits the entire pot to winners
    when ``player_best_hands`` is empty (test/mocked spot)."""
    engine, hero = _make_engine()
    villain = engine.table.get_players_in_order()[1]
    hero.folded = False
    villain.folded = False
    # No hole cards -> player_best_hands stays empty -> fallback runs.
    hero.hole_cards = []
    villain.hole_cards = []

    engine.pot.add_bet(hero, 5000)
    engine.pot.add_bet(villain, 5000)
    bankroll_before = hero.bankroll

    engine._distribute_pot([hero])

    assert hero.bankroll == bankroll_before + 10_000
    assert engine.pot.total == 0


def test_distribute_pot_idempotent_on_empty_pot():
    engine, hero = _make_engine()
    bankroll_before = hero.bankroll
    engine._distribute_pot([hero])  # pot already empty
    assert hero.bankroll == bankroll_before


def test_distribute_pot_credits_full_amount_at_showdown():
    """End-to-end: pot 38_000 must transfer to the hero who actually
    wins the hand."""
    engine, hero = _make_engine()
    villain = engine.table.get_players_in_order()[1]
    hero.folded = False
    villain.folded = False

    engine.community_cards = [
        Card(Suit.HEARTS, Rank.QUEEN),
        Card(Suit.DIAMONDS, Rank.SEVEN),
        Card(Suit.CLUBS, Rank.TWO),
        Card(Suit.SPADES, Rank.NINE),
        Card(Suit.HEARTS, Rank.FOUR),
    ]
    hero.hole_cards = [
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.CLUBS, Rank.ACE),
    ]
    villain.hole_cards = [
        Card(Suit.SPADES, Rank.JACK),
        Card(Suit.HEARTS, Rank.TEN),
    ]

    pot_size = 38_000
    engine.pot.add_bet(hero, pot_size // 2)
    engine.pot.add_bet(villain, pot_size // 2)
    hero.bankroll = 10_000 - pot_size // 2

    bankroll_before = hero.bankroll
    winners = engine._determine_winners()
    assert winners == [hero]
    engine._distribute_pot(winners)
    assert hero.bankroll == bankroll_before + pot_size
    assert engine.pot.total == 0


# ---------- Bug A3: fold-when-check fixes ----------


def test_normalize_recommendation_never_returns_fold_when_can_check():
    """The live-coach normalizer must clamp fold -> check whenever
    checking is free, regardless of which upstream branch suggested
    fold."""
    pending = {"options": ["Check", "Bet 200"]}
    out = _normalize_recommendation(
        recommendation="fold",
        pending=pending,
        can_check=True,
        call_amount=0,
    )
    assert out == "check"


def test_normalize_recommendation_keeps_fold_when_facing_real_bet():
    """Sanity: when can_check is False and a bet is outstanding, fold
    is still a legal recommendation."""
    pending = {"options": ["Call 200", "Fold"]}
    out = _normalize_recommendation(
        recommendation="fold",
        pending=pending,
        can_check=False,
        call_amount=200,
    )
    assert out == "fold"


def test_normalize_prefers_check_when_call_value_dominated():
    """When the upstream layer says "call" but call_amount is 0 and
    check is legal, we recommend check (not fold)."""
    pending = {"options": ["Check", "Bet 100"]}
    out = _normalize_recommendation(
        recommendation="call",
        pending=pending,
        can_check=True,
        call_amount=0,
    )
    assert out == "check"


# ---------- Engine _record_hero_decision: doesn't store fold when can_check ----------


def test_engine_recommended_action_never_fold_on_check_spot():
    """Drive a postflop decision where check is free and verify the
    decision record's ``recommended_action`` is not "fold"."""
    engine, hero = _make_engine()
    villain = engine.table.get_players_in_order()[1]
    villain.folded = False
    hero.folded = False
    hero.hole_cards = [
        Card(Suit.SPADES, Rank.SEVEN),
        Card(Suit.CLUBS, Rank.TWO),
    ]
    villain.hole_cards = [
        Card(Suit.SPADES, Rank.JACK),
        Card(Suit.HEARTS, Rank.TEN),
    ]
    engine.community_cards = [
        Card(Suit.HEARTS, Rank.QUEEN),
        Card(Suit.DIAMONDS, Rank.SEVEN),
        Card(Suit.CLUBS, Rank.TWO),
    ]
    # Set engine state to a postflop check spot.
    engine.session_tracker.start_hand(hand_meta={"hero_name": hero.name})
    from game.game_engine import BettingRound, GameState

    engine.current_betting_round = BettingRound.FLOP
    engine.game_state = GameState.FLOP

    from game.player import PlayerAction

    context = {
        "current_bet": 0,
        "pot_total": 600,
        "can_check": True,
        "raise_allowed": True,
        "min_raise": 100,
    }
    engine._record_human_decision_point(
        chosen_action=PlayerAction.CHECK,
        chosen_amount=0,
        context=context,
    )

    decisions = engine.session_tracker.hand_history[-1].get("decision_points") or []
    assert decisions, "Decision should have been recorded"
    last = decisions[-1]
    rec = (last.get("recommended_action") or "").lower()
    assert rec != "fold", (
        f"Bug A3 regression: recommended_action='fold' on a free-check spot "
        f"(can_check=True). Full decision: {last}"
    )
