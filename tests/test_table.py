"""
Test suite for Table class.
Tests table management, player seating, and game state tracking.
"""
import pytest
from src.game.table import Table, TableType, SeatPosition
from src.game.player import Player
from src.game.ai_player import AIPlayer, AIStyle


class TestSeatPosition:
    """Test cases for SeatPosition enum."""
    
    def test_seat_position_values(self):
        """Test seat position enum values."""
        assert SeatPosition.SEAT_1.value == 1
        assert SeatPosition.SEAT_9.value == 9
        
    def test_seat_position_ordering(self):
        """Test seat position comparison."""
        assert SeatPosition.SEAT_1 < SeatPosition.SEAT_2
        assert SeatPosition.SEAT_9 > SeatPosition.SEAT_1


class TestTable:
    """Test cases for Table class."""
    
    def test_table_creation(self):
        """Test creating a new table."""
        table = Table(table_type=TableType.CASH_GAME, max_players=6)
        
        assert table.table_type == TableType.CASH_GAME
        assert table.max_players == 6
        assert len(table.seats) == 9  # Always 9 seats
        assert table.num_players == 0
        assert table.dealer_position == 0
        assert table.small_blind_position == 1
        assert table.big_blind_position == 2
        
    def test_table_invalid_max_players(self):
        """Test creating table with invalid max players."""
        with pytest.raises(ValueError, match="Max players must be between 2 and 9"):
            Table(TableType.CASH_GAME, max_players=1)
            
        with pytest.raises(ValueError, match="Max players must be between 2 and 9"):
            Table(TableType.CASH_GAME, max_players=10)
            
    def test_add_player_to_empty_table(self):
        """Test adding first player to empty table."""
        table = Table(TableType.CASH_GAME, max_players=6)
        player = Player("TestPlayer", 1000)
        
        seat_num = table.add_player(player)
        
        assert seat_num is not None
        assert table.num_players == 1
        assert table.seats[seat_num] == player
        assert player.position == seat_num
        
    def test_add_multiple_players(self):
        """Test adding multiple players to table."""
        table = Table(TableType.CASH_GAME, max_players=6)
        players = [Player(f"Player{i}", 1000) for i in range(3)]
        
        seat_positions = []
        for player in players:
            seat_num = table.add_player(player)
            seat_positions.append(seat_num)
            
        assert table.num_players == 3
        assert len(set(seat_positions)) == 3  # All different seats
        
        # Verify players are in seats
        for i, player in enumerate(players):
            assert table.seats[seat_positions[i]] == player
            
    def test_add_player_to_full_table(self):
        """Test adding player to full table."""
        table = Table(TableType.CASH_GAME, max_players=2)
        
        # Fill table
        table.add_player(Player("Player1", 1000))
        table.add_player(Player("Player2", 1000))
        
        # Try to add one more
        with pytest.raises(ValueError, match="Table is full"):
            table.add_player(Player("Player3", 1000))
            
    def test_add_duplicate_player(self):
        """Test adding same player twice."""
        table = Table(TableType.CASH_GAME, max_players=6)
        player = Player("TestPlayer", 1000)
        
        table.add_player(player)
        
        with pytest.raises(ValueError, match="Player .* is already seated"):
            table.add_player(player)
            
    def test_remove_player(self):
        """Test removing player from table."""
        table = Table(TableType.CASH_GAME, max_players=6)
        player = Player("TestPlayer", 1000)
        
        seat_num = table.add_player(player)
        assert table.num_players == 1
        
        table.remove_player(player)
        
        assert table.num_players == 0
        assert table.seats[seat_num] is None
        assert player.position == 0  # Reset position
        
    def test_remove_player_not_seated(self):
        """Test removing player not at table."""
        table = Table(TableType.CASH_GAME, max_players=6)
        player = Player("TestPlayer", 1000)
        
        with pytest.raises(ValueError, match="Player .* is not seated at this table"):
            table.remove_player(player)
            
    def test_get_active_players(self):
        """Test getting list of active players."""
        table = Table(TableType.CASH_GAME, max_players=6)
        
        # Add players
        players = [Player(f"Player{i}", 1000) for i in range(4)]
        for player in players:
            table.add_player(player)
            
        # Make one player fold
        players[1].fold()
        
        active_players = table.get_active_players()
        
        assert len(active_players) == 3  # 4 - 1 folded
        assert players[1] not in active_players
        
    def test_get_players_in_order(self):
        """Test getting players in seating order."""
        table = Table(TableType.CASH_GAME, max_players=6)
        
        # Add players to specific seats
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 1000)
        player3 = Player("Player3", 1000)
        
        # Manually place players (simulating specific seating)
        table.seats[2] = player1
        table.seats[5] = player2
        table.seats[7] = player3
        table._num_players = 3
        
        players_in_order = table.get_players_in_order()
        
        assert len(players_in_order) == 3
        assert players_in_order[0] == player1  # Seat 2
        assert players_in_order[1] == player2  # Seat 5
        assert players_in_order[2] == player3  # Seat 7
        
    def test_rotate_dealer_button(self):
        """Test rotating dealer button."""
        table = Table(TableType.CASH_GAME, max_players=6)
        
        # Add 3 players
        players = [Player(f"Player{i}", 1000) for i in range(3)]
        for player in players:
            table.add_player(player)
            
        # Initial positions
        initial_dealer = table.dealer_position
        initial_sb = table.small_blind_position
        initial_bb = table.big_blind_position
        
        table.rotate_dealer_button()
        
        # Positions should have moved
        assert table.dealer_position != initial_dealer
        assert table.small_blind_position != initial_sb
        assert table.big_blind_position != initial_bb
        
    def test_get_next_to_act(self):
        """Test getting next player to act."""
        table = Table(TableType.CASH_GAME, max_players=6)
        
        # Add players
        players = [Player(f"Player{i}", 1000) for i in range(4)]
        for player in players:
            table.add_player(player)
            
        # First to act should be left of big blind
        next_player = table.get_next_to_act()
        
        assert next_player is not None
        assert next_player != table.get_small_blind_player()
        assert next_player != table.get_big_blind_player()
        
    def test_get_small_blind_player(self):
        """Test getting small blind player."""
        table = Table(TableType.CASH_GAME, max_players=6)
        
        # Add players
        players = [Player(f"Player{i}", 1000) for i in range(3)]
        for player in players:
            table.add_player(player)
            
        sb_player = table.get_small_blind_player()
        
        assert sb_player is not None
        assert sb_player.position == table.small_blind_position
        
    def test_get_big_blind_player(self):
        """Test getting big blind player."""
        table = Table(TableType.CASH_GAME, max_players=6)
        
        # Add players
        players = [Player(f"Player{i}", 1000) for i in range(3)]
        for player in players:
            table.add_player(player)
            
        bb_player = table.get_big_blind_player()
        
        assert bb_player is not None
        assert bb_player.position == table.big_blind_position
        
    def test_table_minimum_players(self):
        """Test table with minimum players (heads-up)."""
        table = Table(TableType.CASH_GAME, max_players=2)
        
        # Add 2 players
        player1 = Player("Player1", 1000)
        player2 = Player("Player2", 1000)
        
        table.add_player(player1)
        table.add_player(player2)
        
        # In heads-up, dealer is small blind
        dealer = table.get_dealer_player()
        sb_player = table.get_small_blind_player()
        
        assert dealer == sb_player
        
    def test_table_reset_for_new_hand(self):
        """Test resetting table for new hand."""
        table = Table(TableType.CASH_GAME, max_players=6)
        
        # Add players and simulate some action
        players = [Player(f"Player{i}", 1000) for i in range(3)]
        for player in players:
            table.add_player(player)
            
        # Simulate some bets and folds
        players[0].place_bet(50)
        players[1].fold()
        
        table.reset_for_new_hand()
        
        # Players should be reset but still seated
        assert table.num_players == 3
        assert not players[1].folded  # Fold status reset
        assert players[0].current_bet == 0  # Bets reset
        
    def test_is_table_full(self):
        """Test checking if table is full."""
        table = Table(TableType.CASH_GAME, max_players=3)
        
        assert not table.is_full()
        
        # Add players one by one
        for i in range(3):
            table.add_player(Player(f"Player{i}", 1000))
            
        assert table.is_full()
        
    def test_can_start_game(self):
        """Test checking if game can start."""
        table = Table(TableType.CASH_GAME, max_players=6)
        
        # Need at least 2 players
        assert not table.can_start_game()
        
        table.add_player(Player("Player1", 1000))
        assert not table.can_start_game()
        
        table.add_player(Player("Player2", 1000))
        assert table.can_start_game()
        
    def test_get_seat_number(self):
        """Test getting seat number for player."""
        table = Table(TableType.CASH_GAME, max_players=6)
        player = Player("TestPlayer", 1000)
        
        # Player not seated
        assert table.get_seat_number(player) is None
        
        # Seat player
        expected_seat = table.add_player(player)
        actual_seat = table.get_seat_number(player)
        
        assert actual_seat == expected_seat
        
    def test_table_string_representation(self):
        """Test string representation of table."""
        table = Table(TableType.CASH_GAME, max_players=6)
        
        # Add some players
        table.add_player(Player("Player1", 1000))
        table.add_player(Player("Player2", 1500))
        
        table_str = str(table)
        
        assert "Cash Game" in table_str
        assert "2/6" in table_str  # Players count
        assert "Player1" in table_str
        assert "Player2" in table_str


class TestTableType:
    """Test cases for TableType enum."""
    
    def test_table_type_values(self):
        """Test table type enum values."""
        assert TableType.CASH_GAME.value == "cash_game"
        assert TableType.TOURNAMENT.value == "tournament"


class TestTableIntegration:
    """Integration tests for table with players and game flow."""
    
    def test_table_with_ai_players(self):
        """Test table with mixed human and AI players."""
        table = Table(TableType.CASH_GAME, max_players=6)
        
        # Add human player
        human = Player("Human", 1000)
        table.add_player(human)
        
        # Add AI players
        ai_players = [
            AIPlayer("AI_Cautious", 1000, AIStyle.CAUTIOUS),
            AIPlayer("AI_Wild", 1000, AIStyle.WILD),
            AIPlayer("AI_Balanced", 1000, AIStyle.BALANCED)
        ]
        
        for ai in ai_players:
            table.add_player(ai)
            
        assert table.num_players == 4
        
        # Verify mix of player types
        all_players = table.get_players_in_order()
        human_count = sum(1 for p in all_players if not hasattr(p, 'ai_style'))
        ai_count = sum(1 for p in all_players if hasattr(p, 'ai_style'))
        
        assert human_count == 1
        assert ai_count == 3
        
    def test_table_betting_positions(self):
        """Test table position management during betting."""
        table = Table(TableType.CASH_GAME, max_players=6)
        
        # Add 4 players
        players = [Player(f"Player{i}", 1000) for i in range(4)]
        for player in players:
            table.add_player(player)
            
        # Check initial positions
        dealer = table.get_dealer_player()
        sb = table.get_small_blind_player()
        bb = table.get_big_blind_player()
        
        assert dealer != sb != bb
        
        # Rotate and check again
        old_dealer = dealer
        table.rotate_dealer_button()
        new_dealer = table.get_dealer_player()
        
        assert new_dealer != old_dealer
        
    def test_table_player_elimination(self):
        """Test handling player elimination/leaving."""
        table = Table(TableType.TOURNAMENT, max_players=6)
        
        # Add players
        players = [Player(f"Player{i}", 1000) for i in range(4)]
        for player in players:
            table.add_player(player)
            
        assert table.num_players == 4
        
        # Eliminate player (simulate bust out)
        eliminated_player = players[1]
        table.remove_player(eliminated_player)
        
        assert table.num_players == 3
        assert eliminated_player not in table.get_active_players()
        
        # Table should still be playable
        assert table.can_start_game()
        
    def test_table_serialization(self):
        """Test table state serialization for saving/loading."""
        table = Table(TableType.CASH_GAME, max_players=6)
        
        # Add players
        players = [Player(f"Player{i}", 1000 + i*500) for i in range(3)]
        for player in players:
            table.add_player(player)
            
        # Get table state
        table_state = table.get_table_state()
        
        assert 'table_type' in table_state
        assert 'max_players' in table_state
        assert 'dealer_position' in table_state
        assert 'players' in table_state
        assert len(table_state['players']) == 3
