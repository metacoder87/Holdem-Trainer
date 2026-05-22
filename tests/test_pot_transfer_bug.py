"""Reproduce the "won 38k pot but stack didn't update" bug.

The user reported: hero won a large pot, the hand-complete display
showed the pot total, but the *next* hand's stack_start was unchanged
from before the win. This means either:

  1. ``Player.add_winnings`` was never called for hero, or
  2. It was called with a wrong amount, or
  3. The bankroll was clobbered between hands.

These tests exercise the end-to-end pot transfer path through
``_distribute_pot`` -> ``Pot.distribute_to_winners`` -> ``Player.add_winnings``
and verify hero's bankroll moves the right amount.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from game.card import Card, Rank, Suit
from game.player import Player
from game.pot import Pot


def _make_hand(cards):
    from game.hand import Hand

    return Hand.best_hand_from_cards(cards)


def test_distribute_to_winners_credits_main_pot_to_best_hand():
    """Direct test of the pot's distribute_to_winners function."""
    p1 = Player("Hero", bankroll=1000)
    p2 = Player("Villain", bankroll=1000)
    pot = Pot()
    pot.add_bet(p1, 500)
    pot.add_bet(p2, 500)
    # Now pot.total = 1000, main_pot = 1000, eligible_players = [p1, p2].
    pot.create_side_pots()

    # Hero has top pair, villain has bottom pair.
    board = [
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.KING),
        Card(Suit.CLUBS, Rank.TWO),
        Card(Suit.SPADES, Rank.SEVEN),
        Card(Suit.HEARTS, Rank.NINE),
    ]
    p1.hole_cards = [Card(Suit.SPADES, Rank.ACE), Card(Suit.CLUBS, Rank.QUEEN)]
    p2.hole_cards = [Card(Suit.SPADES, Rank.TWO), Card(Suit.HEARTS, Rank.TWO)]

    player_best_hands = {
        p1: _make_hand(p1.hole_cards + board),
        p2: _make_hand(p2.hole_cards + board),
    }

    # Wait - p2 has trips of twos (with board 2 + hole 2,2) which beats
    # hero's two pair. So villain wins this one.
    winnings = pot.distribute_to_winners(player_best_hands)
    assert winnings.get(p2, 0) == 1000
    assert winnings.get(p1, 0) == 0


def test_distribute_to_winners_credits_hero_when_hero_wins():
    """Hero wins -> Hero's winnings == pot.total."""
    hero = Player("Hero", bankroll=1000)
    villain = Player("V", bankroll=1000)
    pot = Pot()
    pot.add_bet(hero, 500)
    pot.add_bet(villain, 500)
    pot.create_side_pots()

    # Hero: pair of aces (in hole). Villain: junk (no pair, no draw).
    # Board kept rank-disconnected so villain can't make a straight.
    board = [
        Card(Suit.HEARTS, Rank.QUEEN),
        Card(Suit.DIAMONDS, Rank.SEVEN),
        Card(Suit.CLUBS, Rank.TWO),
        Card(Suit.SPADES, Rank.NINE),
        Card(Suit.HEARTS, Rank.FOUR),
    ]
    hero.hole_cards = [Card(Suit.SPADES, Rank.ACE), Card(Suit.CLUBS, Rank.ACE)]
    villain.hole_cards = [Card(Suit.SPADES, Rank.JACK), Card(Suit.HEARTS, Rank.TEN)]

    player_best_hands = {
        hero: _make_hand(hero.hole_cards + board),
        villain: _make_hand(villain.hole_cards + board),
    }
    winnings = pot.distribute_to_winners(player_best_hands)
    assert winnings.get(hero, 0) == 1000
    assert winnings.get(villain, 0) == 0


def test_player_add_winnings_increments_bankroll():
    p = Player("Hero", bankroll=1000)
    before = p.bankroll
    p.add_winnings(38_000)
    assert p.bankroll == before + 38_000
    assert p.total_winnings == 38_000


def test_engine_end_to_end_pot_to_hero_at_showdown():
    """End-to-end: drive a hand to showdown and verify hero's bankroll
    grew by the pot total."""
    from game.game_engine import GameEngine
    from game.ai_player import AIStyle

    # Setup engine via the test-mode path.
    hero = Player("Hero", bankroll=10_000)

    class _NullHandler:
        def get_menu_choice(self, options, prompt=""):
            for i, opt in enumerate(options, 1):
                low = opt.lower()
                if "check" in low or "call" in low:
                    return i
            return 1

        def get_number_input(self, prompt, min_value=None, max_value=None, integer_only=False):
            return float(min_value or 1)

        def get_yes_no_input(self, prompt):
            return False

    engine = GameEngine(hero, data_manager=None, display=None, input_handler=_NullHandler())
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

    # Manually trigger one hand by calling internal pieces. The full
    # play_hand requires non-trivial mocking; use _complete_hand with
    # a pre-staged pot + hands instead.
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
    villain = engine.table.get_players_in_order()[1]
    villain.hole_cards = [
        Card(Suit.SPADES, Rank.JACK),
        Card(Suit.HEARTS, Rank.TEN),
    ]
    hero.folded = False
    villain.folded = False

    # Stake the pot.
    pot_size = 38_000
    engine.pot.add_bet(hero, pot_size // 2)
    engine.pot.add_bet(villain, pot_size // 2)
    # Synthesize bankrolls reflecting the bets (subtract bets from
    # starting bankrolls so the test is realistic).
    hero.bankroll = 10_000 - pot_size // 2
    villain.bankroll = 10_000 - pot_size // 2

    bankroll_before = hero.bankroll
    pot_before = engine.pot.total
    assert pot_before == pot_size

    # Drive distribution + completion.
    winners = engine._determine_winners()
    assert winners == [hero], f"Hero must be the sole winner, got {winners}"
    engine._distribute_pot(winners)

    # After distribution: hero's bankroll should have grown by the pot.
    assert hero.bankroll == bankroll_before + pot_size, (
        f"Bug reproduction: hero stack didn't increase. "
        f"bankroll_before={bankroll_before}, after={hero.bankroll}, pot={pot_size}"
    )
    # And the pot is reset.
    assert engine.pot.total == 0


def test_engine_pot_transfer_when_hero_won_by_fold():
    """Path 1 of _distribute_pot: opponents folded -> hero wins by fold."""
    from game.game_engine import GameEngine

    hero = Player("Hero", bankroll=10_000)

    class _NullHandler:
        def get_menu_choice(self, options, prompt=""):
            return 1

        def get_number_input(self, *a, **kw):
            return 1.0

        def get_yes_no_input(self, *a, **kw):
            return False

    engine = GameEngine(hero, data_manager=None, display=None, input_handler=_NullHandler())
    engine._test_mode = True
    engine.start_game(
        {"type": "cash", "limit": "no_limit", "small_blind": 50, "big_blind": 100, "max_players": 2}
    )

    villain = engine.table.get_players_in_order()[1]
    villain.folded = True
    hero.folded = False
    hero.hole_cards = [Card(Suit.SPADES, Rank.ACE), Card(Suit.CLUBS, Rank.KING)]
    villain.hole_cards = [Card(Suit.SPADES, Rank.TWO), Card(Suit.HEARTS, Rank.THREE)]

    pot_size = 5000
    engine.pot.add_bet(hero, 2500)
    engine.pot.add_bet(villain, 2500)
    hero.bankroll = 10_000 - 2500

    bankroll_before = hero.bankroll
    winners = engine._determine_winners()
    engine._distribute_pot(winners)

    assert hero.bankroll == bankroll_before + pot_size
    assert engine.pot.total == 0
