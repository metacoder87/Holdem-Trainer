"""
Test suite for Player class.
Tests player creation, actions, and state management.
"""
import pytest
from src.game.player import Player, PlayerAction
from src.game.card import Card, Suit, Rank


class TestPlayerAction:
    """Test cases for PlayerAction enum."""
    
    def test_action_values(self):
        """Test player action enum values."""
        assert PlayerAction.FOLD.value == "fold"
        assert PlayerAction.CALL.value == "call"
        assert PlayerAction.RAISE.value == "raise"
        assert PlayerAction.CHECK.value == "check"
        assert PlayerAction.ALL_IN.value == "all_in"


class TestPlayer:
    """Test cases for Player class."""
    
    def test_player_creation(self):
        """Test creating a new player."""
        player = Player("TestPlayer", 1000)
        
        assert player.name == "TestPlayer"
        assert player.bankroll == 1000
        assert player.current_bet == 0
        assert player.total_bet == 0
        assert player.hole_cards == []
        assert not player.folded
        assert not player.all_in
        assert player.position == 0
        
    def test_player_invalid_bankroll(self):
        """Test creating player with invalid bankroll."""
        with pytest.raises(ValueError, match="Bankroll must be non-negative"):
            Player("TestPlayer", -100)
            
    def test_player_invalid_name(self):
        """Test creating player with invalid name."""
        with pytest.raises(ValueError, match="Player name cannot be empty"):
            Player("", 1000)
            
    def test_deal_hole_cards(self):
        """Test dealing hole cards to player."""
        player = Player("TestPlayer", 1000)
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.SPADES, Rank.KING)
        ]
        
        player.deal_hole_cards(cards)
        
        assert len(player.hole_cards) == 2
        assert player.hole_cards == cards
        
    def test_deal_invalid_hole_cards(self):
        """Test dealing wrong number of hole cards."""
        player = Player("TestPlayer", 1000)
        cards = [Card(Suit.HEARTS, Rank.ACE)]  # Only one card
        
        with pytest.raises(ValueError, match="Must deal exactly 2 hole cards"):
            player.deal_hole_cards(cards)
            
    def test_place_bet(self):
        """Test placing a bet."""
        player = Player("TestPlayer", 1000)
        
        player.place_bet(100)
        
        assert player.current_bet == 100
        assert player.total_bet == 100
        assert player.bankroll == 900
        
    def test_place_bet_insufficient_funds(self):
        """Test placing bet with insufficient funds."""
        player = Player("TestPlayer", 100)
        
        with pytest.raises(ValueError, match="Insufficient funds"):
            player.place_bet(150)
            
    def test_place_bet_invalid_amount(self):
        """Test placing invalid bet amount."""
        player = Player("TestPlayer", 1000)
        
        with pytest.raises(ValueError, match="Bet amount must be positive"):
            player.place_bet(-50)
            
        with pytest.raises(ValueError, match="Bet amount must be positive"):
            player.place_bet(0)
            
    def test_add_to_bet(self):
        """Test adding to existing bet."""
        player = Player("TestPlayer", 1000)
        
        player.place_bet(100)
        player.add_to_bet(50)
        
        assert player.current_bet == 150
        assert player.total_bet == 150
        assert player.bankroll == 850
        
    def test_call_bet(self):
        """Test calling a bet."""
        player = Player("TestPlayer", 1000)
        player.place_bet(50)  # Already bet 50
        
        call_amount = player.call(100)  # Call to 100
        
        assert call_amount == 50  # Only need to add 50 more
        assert player.current_bet == 100
        assert player.total_bet == 100
        assert player.bankroll == 900
        
    def test_call_bet_already_called(self):
        """Test calling when already at call amount."""
        player = Player("TestPlayer", 1000)
        player.place_bet(100)
        
        call_amount = player.call(100)  # Already at call amount
        
        assert call_amount == 0
        assert player.current_bet == 100
        
    def test_raise_bet(self):
        """Test raising a bet."""
        player = Player("TestPlayer", 1000)
        
        raise_amount = player.raise_bet(50, 150)  # Raise from 50 to 150
        
        assert raise_amount == 100  # The raise amount
        assert player.current_bet == 150
        assert player.total_bet == 150
        assert player.bankroll == 850
        
    def test_all_in(self):
        """Test going all-in."""
        player = Player("TestPlayer", 500)
        
        all_in_amount = player.go_all_in()
        
        assert all_in_amount == 500
        assert player.current_bet == 500
        assert player.total_bet == 500
        assert player.bankroll == 0
        assert player.all_in
        
    def test_all_in_with_existing_bet(self):
        """Test going all-in with existing bet."""
        player = Player("TestPlayer", 500)
        player.place_bet(200)
        
        all_in_amount = player.go_all_in()
        
        assert all_in_amount == 300  # Additional amount
        assert player.current_bet == 500
        assert player.total_bet == 500
        assert player.bankroll == 0
        assert player.all_in
        
    def test_fold(self):
        """Test folding."""
        player = Player("TestPlayer", 1000)
        player.place_bet(100)
        
        player.fold()
        
        assert player.folded
        assert player.current_bet == 100  # Bet remains but player is out
        
    def test_can_bet(self):
        """Test checking if player can bet."""
        player = Player("TestPlayer", 100)
        
        assert player.can_bet(50)
        assert player.can_bet(100)
        assert not player.can_bet(150)
        
    def test_can_call(self):
        """Test checking if player can call."""
        player = Player("TestPlayer", 100)
        player.place_bet(30)
        
        assert player.can_call(50)  # Needs 20 more, has enough
        assert player.can_call(100)  # Needs 70 more, has enough
        assert not player.can_call(200)  # Needs 170 more, not enough
        
    def test_can_raise(self):
        """Test checking if player can raise."""
        player = Player("TestPlayer", 200)
        
        assert player.can_raise(50, 150)  # Raise to 150, has enough
        assert not player.can_raise(50, 250)  # Raise to 250, not enough
        
    def test_reset_for_new_hand(self):
        """Test resetting player for new hand."""
        player = Player("TestPlayer", 1000)
        player.deal_hole_cards([
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.SPADES, Rank.KING)
        ])
        player.place_bet(100)
        player.fold()
        
        player.reset_for_new_hand()
        
        assert player.hole_cards == []
        assert player.current_bet == 0
        assert not player.folded
        assert not player.all_in
        # Bankroll and total_bet should remain
        assert player.bankroll == 900
        
    def test_reset_for_new_round(self):
        """Test resetting player for new betting round."""
        player = Player("TestPlayer", 1000)
        player.place_bet(100)
        
        player.reset_for_new_round()
        
        assert player.current_bet == 0
        # total_bet and bankroll should remain unchanged
        assert player.total_bet == 100
        assert player.bankroll == 900
        
    def test_add_winnings(self):
        """Test adding winnings to player."""
        player = Player("TestPlayer", 800)
        
        player.add_winnings(500)
        
        assert player.bankroll == 1300
        
    def test_player_string_representation(self):
        """Test string representation of player."""
        player = Player("TestPlayer", 1000)
        player_str = str(player)
        
        assert "TestPlayer" in player_str
        assert "1000" in player_str
        
    def test_player_equality(self):
        """Test player equality comparison."""
        player1 = Player("TestPlayer", 1000)
        player2 = Player("TestPlayer", 1000)
        player3 = Player("OtherPlayer", 1000)
        
        assert player1 == player2
        assert player1 != player3
        
    def test_player_hash(self):
        """Test player hashing for use in sets/dicts."""
        player1 = Player("TestPlayer", 1000)
        player2 = Player("TestPlayer", 1000)
        player3 = Player("OtherPlayer", 1000)
        
        player_set = {player1, player2, player3}
        assert len(player_set) == 2  # player1 and player2 should be same
        
    def test_player_is_active(self):
        """Test checking if player is active (not folded, not all-in)."""
        player = Player("TestPlayer", 1000)
        
        assert player.is_active
        
        player.fold()
        assert not player.is_active
        
        player.reset_for_new_hand()
        player.go_all_in()
        assert not player.is_active  # All-in players are not active for betting
        
    def test_player_total_invested(self):
        """Test calculating total amount invested in current hand."""
        player = Player("TestPlayer", 1000)
        
        player.place_bet(100)
        assert player.total_invested == 100
        
        player.add_to_bet(50)
        assert player.total_invested == 150
        
    def test_player_net_position(self):
        """Test calculating player's net position."""
        player = Player("TestPlayer", 1000)
        
        # Initial position
        assert player.net_position == 0
        
        # After betting
        player.place_bet(200)
        assert player.net_position == -200
        
        # After winning
        player.add_winnings(500)
        assert player.net_position == 300
        
    def test_player_position_property(self):
        """Test player position property."""
        player = Player("TestPlayer", 1000)
        
        player.position = 3
        assert player.position == 3
        
    def test_player_statistics(self):
        """Test player statistics tracking."""
        player = Player("TestPlayer", 1000)
        
        # These would be implemented as the game tracks stats
        assert hasattr(player, 'hands_played')
        assert hasattr(player, 'hands_won')
        assert hasattr(player, 'total_winnings')
        
        # Initialize stats
        player.hands_played = 0
        player.hands_won = 0
        player.total_winnings = 0
        
        assert player.hands_played == 0
        assert player.hands_won == 0
        assert player.total_winnings == 0
