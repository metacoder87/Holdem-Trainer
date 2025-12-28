"""
Edge case tests for PyHoldem Pro.
Tests complex scenarios in hand evaluation, winner determination, and pot distribution.
"""
import pytest
from game.card import Card, Suit, Rank
from game.hand import Hand, HandRank
from game.game_engine import GameEngine
from game.player import Player
from game.table import Table, TableType
from game.pot import Pot, SidePot

def test_identical_hands_split():
    """Test that identical hands correctly split the pot."""
    # Create identical hands
    hand1 = Hand([
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.ACE),
        Card(Suit.HEARTS, Rank.KING),
        Card(Suit.DIAMONDS, Rank.KING),
        Card(Suit.HEARTS, Rank.TEN)
    ])
    
    hand2 = Hand([
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.CLUBS, Rank.ACE),
        Card(Suit.SPADES, Rank.KING),
        Card(Suit.CLUBS, Rank.KING),
        Card(Suit.CLUBS, Rank.TEN)
    ])
    
    assert not (hand1 > hand2)
    assert not (hand2 > hand1)
    assert hand1 == hand2

def test_kicker_comparison():
    """Test hands with same rank but different kickers."""
    # Two pairs with different kickers
    hand1 = Hand([
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.ACE),
        Card(Suit.HEARTS, Rank.KING),
        Card(Suit.DIAMONDS, Rank.KING),
        Card(Suit.HEARTS, Rank.QUEEN)  # Higher kicker
    ])
    
    hand2 = Hand([
        Card(Suit.SPADES, Rank.ACE),
        Card(Suit.CLUBS, Rank.ACE),
        Card(Suit.SPADES, Rank.KING),
        Card(Suit.CLUBS, Rank.KING),
        Card(Suit.CLUBS, Rank.JACK)  # Lower kicker
    ])
    
    assert hand1 > hand2

def test_ace_low_straight():
    """Test ace-low straight (A-2-3-4-5) vs other hands."""
    ace_low = Hand([
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.TWO),
        Card(Suit.HEARTS, Rank.THREE),
        Card(Suit.DIAMONDS, Rank.FOUR),
        Card(Suit.HEARTS, Rank.FIVE)
    ])
    
    six_high = Hand([
        Card(Suit.SPADES, Rank.TWO),
        Card(Suit.CLUBS, Rank.THREE),
        Card(Suit.SPADES, Rank.FOUR),
        Card(Suit.CLUBS, Rank.FIVE),
        Card(Suit.HEARTS, Rank.SIX)
    ])
    
    assert six_high > ace_low  # 6-high straight beats A-5 straight

def test_complex_side_pot_distribution():
    """Test distribution of multiple side pots with all-in players."""
    table = Table(TableType.CASH_GAME)
    
    # Create players with different stack sizes
    player1 = Player("P1", 1000)  # All-in for 1000
    player2 = Player("P2", 500)   # All-in for 500
    player3 = Player("P3", 200)   # All-in for 200
    player4 = Player("P4", 1000)  # Active with matching chips
    
    table.add_player(player1)
    table.add_player(player2)
    table.add_player(player3)
    table.add_player(player4)
    
    pot = Pot()
    
    # Simulate betting where everyone goes all-in
    pot.add_bet(player1, 1000)
    pot.add_bet(player2, 500)
    pot.add_bet(player3, 200)
    pot.add_bet(player4, 1000)
    
    pot.create_side_pots()
    
    # There should be three pots:
    # Main pot: 800 (200 × 4 players = 800)
    # Side pot 1: 900 (300 × 3 players = 900)
    # Side pot 2: 1000 (500 × 2 players = 1000)
    
    assert len(pot.side_pots) == 2
    assert abs(pot.main_pot - 800) < 0.01
    assert abs(pot.side_pots[0].amount - 900) < 0.01
    assert abs(pot.side_pots[1].amount - 1000) < 0.01

def test_best_hand_from_seven():
    """Test finding best 5-card hand from 7 cards with tricky scenarios."""
    cards = [
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.ACE),
        Card(Suit.HEARTS, Rank.KING),
        Card(Suit.DIAMONDS, Rank.KING),
        Card(Suit.CLUBS, Rank.KING),
        Card(Suit.HEARTS, Rank.TWO),
        Card(Suit.DIAMONDS, Rank.TWO)
    ]
    
    best_hand = Hand.best_hand_from_cards(cards)
    assert best_hand.rank == HandRank.FULL_HOUSE
    # Should choose Kings full of Aces over Aces full of Kings
    assert best_hand.high_card.rank == Rank.KING

def test_multiple_straight_flush_possibilities():
    """Test selecting best straight flush when multiple are possible."""
    cards = [
        Card(Suit.HEARTS, Rank.NINE),
        Card(Suit.HEARTS, Rank.EIGHT),
        Card(Suit.HEARTS, Rank.SEVEN),
        Card(Suit.HEARTS, Rank.SIX),
        Card(Suit.HEARTS, Rank.FIVE),
        Card(Suit.HEARTS, Rank.FOUR),
        Card(Suit.HEARTS, Rank.THREE)
    ]
    
    best_hand = Hand.best_hand_from_cards(cards)
    assert best_hand.rank == HandRank.STRAIGHT_FLUSH
    # Should select 9-high straight flush over lower possibilities
    assert best_hand.high_card.rank == Rank.NINE

def test_three_way_all_in_pot_distribution():
    """Test pot distribution in a three-way all-in situation."""
    pot = Pot()
    
    player1 = Player("P1", 1000)
    player2 = Player("P2", 500)
    player3 = Player("P3", 250)
    
    # All players go all-in
    pot.add_bet(player1, 1000)
    pot.add_bet(player2, 500)
    pot.add_bet(player3, 250)
    
    pot.create_side_pots()
    
    # Give each player incrementally better hands
    hand1 = Hand([  # Weakest hand (pair)
        Card(Suit.HEARTS, Rank.TWO),
        Card(Suit.DIAMONDS, Rank.TWO),
        Card(Suit.HEARTS, Rank.SEVEN),
        Card(Suit.DIAMONDS, Rank.EIGHT),
        Card(Suit.HEARTS, Rank.KING)
    ])
    
    hand2 = Hand([  # Medium hand (two pair)
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.ACE),
        Card(Suit.HEARTS, Rank.KING),
        Card(Suit.DIAMONDS, Rank.KING),
        Card(Suit.HEARTS, Rank.TWO)
    ])
    
    hand3 = Hand([  # Best hand (three of a kind)
        Card(Suit.HEARTS, Rank.ACE),
        Card(Suit.DIAMONDS, Rank.ACE),
        Card(Suit.CLUBS, Rank.ACE),
        Card(Suit.HEARTS, Rank.KING),
        Card(Suit.DIAMONDS, Rank.QUEEN)
    ])
    
    # Simulate distribution per-pot by providing best hands for each player
    player_best_hands = {player1: hand1, player2: hand2, player3: hand3}
    winnings = pot.distribute_to_winners(player_best_hands)

    # Expected: main pot (750) goes to player3, first side pot (500) to player2,
    # second side pot (500) to player1
    assert abs(winnings.get(player3, 0) - 750) < 0.01
    assert abs(winnings.get(player2, 0) - 500) < 0.01
    assert abs(winnings.get(player1, 0) - 500) < 0.01

def test_all_in_less_than_blind():
    """Test handling of player going all-in for less than the big blind."""
    table = Table(TableType.CASH_GAME)
    
    player1 = Player("P1", 15)  # Can't cover big blind
    player2 = Player("P2", 1000)
    player3 = Player("P3", 1000)
    
    table.add_player(player1)
    table.add_player(player2)
    table.add_player(player3)
    
    pot = Pot()
    
    # P1 goes all-in for 15
    pot.add_bet(player1, 15)
    # Others call
    pot.add_bet(player2, 15)
    pot.add_bet(player3, 15)
    
    pot.create_side_pots()
    
    # Should be only main pot of 45 (15 × 3)
    assert abs(pot.total - 45) < 0.01
    assert len(pot.side_pots) == 0

def test_partial_raise_all_in():
    """Test handling of all-in raises that don't meet minimum raise requirements."""
    pot = Pot()
    
    player1 = Player("P1", 1000)
    player2 = Player("P2", 95)  # Not enough for min-raise
    player3 = Player("P3", 1000)
    
    # P1 bets 50
    pot.add_bet(player1, 50)
    # P2 raises all-in to 95 (not meeting min-raise of 100)
    pot.add_bet(player2, 95)
    # P3 just needs to call 95, not 100
    pot.add_bet(player3, 95)
    
    pot.create_side_pots()
    
    assert abs(pot.total - 240) < 0.01  # 50 + 95 + 95
    assert len(pot.side_pots) == 1