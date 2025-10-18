"""
Test suite for Pot management.
Tests pot creation, side pot handling, and distribution logic.
"""
import pytest
from src.game.pot import Pot, SidePot
from src.game.player import Player


class TestPot:
    """Test cases for the main Pot class."""
    
    def test_pot_creation(self):
        """Test creating a new pot."""
        pot = Pot()
        
        assert pot.total == 0
        assert pot.main_pot == 0
        assert len(pot.side_pots) == 0
        assert len(pot.eligible_players) == 0
        
    def test_add_bet_single_player(self):
        """Test adding bet from single player."""
        pot = Pot()
        player = Player("TestPlayer", 1000)
        
        pot.add_bet(player, 100)
        
        assert pot.total == 100
        assert pot.main_pot == 100
        assert player in pot.eligible_players
        assert pot.get_player_contribution(player) == 100
        
    def test_add_bet_multiple_players(self):
        """Test adding bets from multiple players."""
        pot = Pot()
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 1000)
        player3 = Player("Player3", 1000)
        
        pot.add_bet(player1, 100)
        pot.add_bet(player2, 150)
        pot.add_bet(player3, 200)
        
        assert pot.total == 450
        assert pot.main_pot == 450
        assert len(pot.eligible_players) == 3
        
    def test_add_bet_same_player_multiple_times(self):
        """Test adding multiple bets from same player."""
        pot = Pot()
        player = Player("TestPlayer", 1000)
        
        pot.add_bet(player, 50)
        pot.add_bet(player, 75)
        pot.add_bet(player, 25)
        
        assert pot.total == 150
        assert pot.get_player_contribution(player) == 150
        
    def test_create_side_pot_all_in(self):
        """Test creating side pot when player goes all-in."""
        pot = Pot()
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 100)  # Short stack
        player3 = Player("Player3", 1000)
        
        # All players bet
        pot.add_bet(player1, 200)
        pot.add_bet(player2, 100)  # All-in
        pot.add_bet(player3, 200)
        
        # Create side pot for all-in scenario
        pot.create_side_pots()
        
        assert pot.total == 500
        assert len(pot.side_pots) >= 1
        
        # Main pot should be contested by all players
        main_pot_amount = 100 * 3  # 300
        assert pot.main_pot == main_pot_amount
        
        # Side pot should be contested by remaining players
        side_pot_amount = (200 - 100) * 2  # 200
        assert any(sp.amount == side_pot_amount for sp in pot.side_pots)
        
    def test_multiple_all_ins(self):
        """Test multiple all-in situations creating multiple side pots."""
        pot = Pot()
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 50)   # Shortest stack
        player3 = Player("Player3", 150)  # Medium stack
        player4 = Player("Player4", 1000)
        
        pot.add_bet(player1, 200)
        pot.add_bet(player2, 50)   # All-in
        pot.add_bet(player3, 150)  # All-in
        pot.add_bet(player4, 200)
        
        pot.create_side_pots()
        
        assert pot.total == 600
        assert len(pot.side_pots) >= 2  # Should create multiple side pots
        
        # Verify pot structure
        # Main pot: 50 * 4 = 200 (all 4 players)
        # Side pot 1: (150-50) * 3 = 300 (players 1, 3, 4)
        # Side pot 2: (200-150) * 2 = 100 (players 1, 4)
        
        total_side_pot_amount = sum(sp.amount for sp in pot.side_pots)
        assert pot.main_pot + total_side_pot_amount == pot.total
        
    def test_distribute_to_single_winner(self):
        """Test distributing pot to single winner."""
        pot = Pot()
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 1000)
        
        pot.add_bet(player1, 100)
        pot.add_bet(player2, 150)
        
        winnings = pot.distribute([player1])  # Player1 wins
        
        assert winnings[player1] == 250  # Wins entire pot
        assert pot.total == 0  # Pot should be empty
        
    def test_distribute_split_pot(self):
        """Test distributing split pot between multiple winners."""
        pot = Pot()
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 1000)
        player3 = Player("Player3", 1000)
        
        pot.add_bet(player1, 100)
        pot.add_bet(player2, 100)
        pot.add_bet(player3, 101)  # Odd amount for remainder test
        
        winnings = pot.distribute([player1, player2])  # Two winners
        
        # Should split 301 between two players (150 each + 1 remainder)
        total_distributed = sum(winnings.values())
        assert total_distributed == 301
        assert winnings[player1] + winnings[player2] == 301
        
    def test_distribute_with_side_pots(self):
        """Test distributing pot with side pots."""
        pot = Pot()
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 100)  # All-in player
        player3 = Player("Player3", 1000)
        
        pot.add_bet(player1, 200)
        pot.add_bet(player2, 100)  # All-in
        pot.add_bet(player3, 200)
        
        pot.create_side_pots()
        
        # Player2 (all-in) wins
        winnings = pot.distribute([player2])
        
        # Player2 should only win main pot (eligible for)
        # Remaining players should get side pot back or it goes to next best hand
        assert player2 in winnings
        assert winnings[player2] == 300  # Main pot only
        
    def test_get_pot_odds(self):
        """Test calculating pot odds for a bet."""
        pot = Pot()
        player = Player("TestPlayer", 1000)
        
        pot.add_bet(player, 100)
        
        # To call 50 more into pot of 100
        odds = pot.get_pot_odds(50)
        expected_odds = 50 / (100 + 50)  # bet / (pot + bet)
        
        assert abs(odds - expected_odds) < 0.01
        
    def test_reset_pot(self):
        """Test resetting pot for new hand."""
        pot = Pot()
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 1000)
        
        pot.add_bet(player1, 100)
        pot.add_bet(player2, 150)
        pot.create_side_pots()
        
        pot.reset()
        
        assert pot.total == 0
        assert pot.main_pot == 0
        assert len(pot.side_pots) == 0
        assert len(pot.eligible_players) == 0
        
    def test_pot_string_representation(self):
        """Test string representation of pot."""
        pot = Pot()
        player = Player("TestPlayer", 1000)
        
        pot.add_bet(player, 150)
        pot_str = str(pot)
        
        assert "150" in pot_str
        assert "pot" in pot_str.lower()


class TestSidePot:
    """Test cases for SidePot class."""
    
    def test_side_pot_creation(self):
        """Test creating a side pot."""
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 1000)
        eligible_players = [player1, player2]
        
        side_pot = SidePot(200, eligible_players)
        
        assert side_pot.amount == 200
        assert side_pot.eligible_players == eligible_players
        assert len(side_pot.eligible_players) == 2
        
    def test_side_pot_distribution_single_winner(self):
        """Test distributing side pot to single winner."""
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 1000)
        player3 = Player("Player3", 1000)
        
        side_pot = SidePot(300, [player1, player2])
        
        # Player1 wins (eligible)
        winnings = side_pot.distribute([player1])
        assert winnings[player1] == 300
        
        # Player3 wins (not eligible) - should return empty
        winnings = side_pot.distribute([player3])
        assert len(winnings) == 0
        
    def test_side_pot_distribution_multiple_winners(self):
        """Test distributing side pot among multiple winners."""
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 1000)
        player3 = Player("Player3", 1000)
        
        side_pot = SidePot(300, [player1, player2, player3])
        
        # Two eligible winners
        winnings = side_pot.distribute([player1, player2])
        
        assert len(winnings) == 2
        assert winnings[player1] == 150
        assert winnings[player2] == 150
        
    def test_side_pot_distribution_mixed_eligibility(self):
        """Test distributing side pot with mixed winner eligibility."""
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 1000)
        player3 = Player("Player3", 1000)
        player4 = Player("Player4", 1000)
        
        side_pot = SidePot(400, [player1, player2])  # Only 1 and 2 eligible
        
        # Winners include eligible and non-eligible players
        winnings = side_pot.distribute([player1, player3])
        
        # Only eligible winner should receive
        assert len(winnings) == 1
        assert winnings[player1] == 400
        assert player3 not in winnings
        
    def test_side_pot_string_representation(self):
        """Test string representation of side pot."""
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 1000)
        
        side_pot = SidePot(250, [player1, player2])
        side_pot_str = str(side_pot)
        
        assert "250" in side_pot_str
        assert "2" in side_pot_str  # Number of eligible players


class TestPotIntegration:
    """Integration tests for pot with player interactions."""
    
    def test_pot_with_player_betting_actions(self):
        """Test pot management through player betting actions."""
        pot = Pot()
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 500)
        
        # Preflop betting
        player1.place_bet(50)
        player2.place_bet(50)
        pot.add_bet(player1, 50)
        pot.add_bet(player2, 50)
        
        # Flop betting
        player1.add_to_bet(100)
        player2.go_all_in()  # Remaining 450
        pot.add_bet(player1, 100)
        pot.add_bet(player2, 450)
        
        pot.create_side_pots()
        
        assert pot.total == 600
        # Main pot: 100 * 2 = 200
        # Side pot: (500 - 100) * 1 = 400 (only player1 eligible)
        
    def test_pot_rake_calculation(self):
        """Test pot rake calculation for cash games."""
        pot = Pot()
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 1000)
        
        pot.add_bet(player1, 500)
        pot.add_bet(player2, 500)
        
        # Calculate rake (typically 5% capped)
        rake = pot.calculate_rake(rate=0.05, cap=25)
        
        expected_rake = min(1000 * 0.05, 25)
        assert rake == expected_rake
        
    def test_pot_tournament_blinds_antes(self):
        """Test pot with tournament blinds and antes."""
        pot = Pot()
        players = [Player(f"Player{i}", 1000) for i in range(6)]
        
        # Add antes from all players
        ante = 10
        for player in players:
            pot.add_bet(player, ante)
            
        # Add blinds
        pot.add_bet(players[0], 25)  # Small blind (additional)
        pot.add_bet(players[1], 50)  # Big blind (additional)
        
        expected_total = (ante * 6) + 25 + 50  # 60 + 75 = 135
        assert pot.total == expected_total
