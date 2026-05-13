"""Regression tests for the Monte Carlo equity calculator.

Compares against textbook all-in preflop equities. With 2,000 trials the
standard error is ~1.1%, so a 2% tolerance keeps tests stable while still
catching real regressions.
"""
import random as _random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from game.card import Card, Rank, Suit
from stats.calculator import EquityCalculator, PotOddsCalculator


TRIALS = 2000
# 2,000 trials -> standard error ~1.1%. Use 3% tolerance so legitimate
# Monte Carlo noise doesn't fail the suite.
TOLERANCE = 0.03


def card(rank: Rank, suit: Suit) -> Card:
    return Card(suit, rank)


def test_aa_vs_kk_preflop_about_82_pct():
    """AA vs KK preflop should be ~82/18 in textbook equity tables."""
    aa = [card(Rank.ACE, Suit.HEARTS), card(Rank.ACE, Suit.SPADES)]
    kk = [card(Rank.KING, Suit.HEARTS), card(Rank.KING, Suit.SPADES)]

    rng = _random.Random(2024)
    eq_aa, eq_kk = EquityCalculator.calculate_heads_up_equity(
        aa, kk, board=None, trials=TRIALS, rng=rng
    )
    assert abs(eq_aa - 0.82) < TOLERANCE, f"AA equity {eq_aa:.3f} should be ~0.82"
    assert abs(eq_kk - 0.18) < TOLERANCE, f"KK equity {eq_kk:.3f} should be ~0.18"
    assert abs((eq_aa + eq_kk) - 1.0) < 0.001


def test_ako_suited_vs_qq_preflop_classic_coinflip():
    """AKs vs QQ is ~46/54 (a near coinflip favoring the pair)."""
    aks = [card(Rank.ACE, Suit.HEARTS), card(Rank.KING, Suit.HEARTS)]
    qq = [card(Rank.QUEEN, Suit.SPADES), card(Rank.QUEEN, Suit.CLUBS)]

    rng = _random.Random(7)
    eq_aks, eq_qq = EquityCalculator.calculate_heads_up_equity(
        aks, qq, trials=TRIALS, rng=rng
    )
    # Textbook ~46% for AKs.
    assert abs(eq_aks - 0.46) < TOLERANCE
    assert abs(eq_qq - 0.54) < TOLERANCE


def test_river_with_made_hand_is_deterministic_at_one_or_zero():
    """Post-river the better hand has 100% equity, no simulation needed."""
    # Hero has top set on river vs. opponent's two pair.
    hero = [card(Rank.ACE, Suit.HEARTS), card(Rank.ACE, Suit.CLUBS)]
    villain = [card(Rank.KING, Suit.SPADES), card(Rank.QUEEN, Suit.HEARTS)]
    board = [
        card(Rank.ACE, Suit.DIAMONDS),
        card(Rank.KING, Suit.CLUBS),
        card(Rank.QUEEN, Suit.SPADES),
        card(Rank.SEVEN, Suit.HEARTS),
        card(Rank.TWO, Suit.DIAMONDS),
    ]
    eq_hero, eq_villain = EquityCalculator.calculate_heads_up_equity(
        hero, villain, board=board, trials=10
    )
    assert eq_hero == 1.0
    assert eq_villain == 0.0


def test_multiway_three_premiums_sum_to_one():
    aa = [card(Rank.ACE, Suit.HEARTS), card(Rank.ACE, Suit.SPADES)]
    kk = [card(Rank.KING, Suit.HEARTS), card(Rank.KING, Suit.SPADES)]
    qq = [card(Rank.QUEEN, Suit.HEARTS), card(Rank.QUEEN, Suit.SPADES)]

    rng = _random.Random(99)
    equities = EquityCalculator.calculate_multiway_equity(
        [aa, kk, qq], trials=TRIALS, rng=rng
    )
    assert abs(sum(equities) - 1.0) < 0.01
    assert equities[0] > equities[1] > equities[2]


def test_seeded_rng_is_reproducible():
    """Two runs with the same seed produce identical equities."""
    aa = [card(Rank.ACE, Suit.HEARTS), card(Rank.ACE, Suit.SPADES)]
    kk = [card(Rank.KING, Suit.HEARTS), card(Rank.KING, Suit.SPADES)]

    eq_a = EquityCalculator.calculate_heads_up_equity(
        aa, kk, trials=500, rng=_random.Random(42)
    )
    eq_b = EquityCalculator.calculate_heads_up_equity(
        aa, kk, trials=500, rng=_random.Random(42)
    )
    assert eq_a == eq_b


def test_implied_odds_pinned_textbook_example():
    """Item 1.2 - pin the implied-odds formula:
    pot 100, call 25, future 50 -> 25/175 = 0.1429.
    """
    required = PotOddsCalculator.calculate_implied_odds(100, 25, 50)
    assert abs(required - (25 / 175)) < 1e-6
