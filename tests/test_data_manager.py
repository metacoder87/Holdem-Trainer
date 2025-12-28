"""
Test suite for DataManager class.
Tests JSON file operations, player data persistence, and data validation.
"""
import pytest
import json
import os
import tempfile
from unittest.mock import patch, mock_open
from data.manager import DataManager
from game.player import Player


class TestDataManager:
    """Test cases for DataManager class."""
    
    def setup_method(self):
        """Set up test with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_file = os.path.join(self.temp_dir, "test_players.json")
        self.manager = DataManager(self.data_file)
        
    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        
    def test_data_manager_creation(self):
        """Test creating a DataManager instance."""
        assert self.manager.data_file == self.data_file
        assert isinstance(self.manager.players_data, dict)
        
    def test_create_new_player(self):
        """Test creating a new player."""
        player_data = self.manager.create_player("TestPlayer", 5000)
        
        assert player_data["name"] == "TestPlayer"
        assert player_data["bankroll"] == 5000
        assert "created_at" in player_data
        assert "last_played" in player_data
        assert player_data["games_played"] == 0
        assert player_data["total_winnings"] == 0
        
    def test_create_duplicate_player(self):
        """Test creating player with existing name."""
        self.manager.create_player("TestPlayer", 5000)
        
        with pytest.raises(ValueError, match="Player 'TestPlayer' already exists"):
            self.manager.create_player("TestPlayer", 3000)
            
    def test_create_player_invalid_name(self):
        """Test creating player with invalid name."""
        with pytest.raises(ValueError, match="Player name cannot be empty"):
            self.manager.create_player("", 5000)
            
        with pytest.raises(ValueError, match="Player name cannot be empty"):
            self.manager.create_player("   ", 5000)
            
    def test_create_player_invalid_bankroll(self):
        """Test creating player with invalid bankroll."""
        with pytest.raises(ValueError, match="Initial bankroll must be positive"):
            self.manager.create_player("TestPlayer", 0)
            
        with pytest.raises(ValueError, match="Initial bankroll must be positive"):
            self.manager.create_player("TestPlayer", -1000)
            
    def test_save_and_load_players(self):
        """Test saving players to file and loading them back."""
        # Create players
        self.manager.create_player("Player1", 5000)
        self.manager.create_player("Player2", 10000)
        
        # Save to file
        self.manager.save_players()
        
        # Create new manager instance and load
        new_manager = DataManager(self.data_file)
        new_manager.load_players()
        
        assert len(new_manager.players_data) == 2
        assert "Player1" in new_manager.players_data
        assert "Player2" in new_manager.players_data
        assert new_manager.players_data["Player1"]["bankroll"] == 5000
        assert new_manager.players_data["Player2"]["bankroll"] == 10000
        
    def test_load_players_nonexistent_file(self):
        """Test loading players from non-existent file."""
        non_existent_file = os.path.join(self.temp_dir, "nonexistent.json")
        manager = DataManager(non_existent_file)
        
        # Should not raise exception, should create empty data
        manager.load_players()
        assert len(manager.players_data) == 0
        
    def test_load_players_corrupted_file(self):
        """Test loading players from corrupted JSON file."""
        # Write invalid JSON
        with open(self.data_file, 'w') as f:
            f.write("invalid json content")
            
        with pytest.raises(json.JSONDecodeError):
            self.manager.load_players()
            
    def test_get_player_exists(self):
        """Test getting existing player."""
        original_data = self.manager.create_player("TestPlayer", 5000)
        player_data = self.manager.get_player("TestPlayer")
        
        assert player_data == original_data
        assert player_data["name"] == "TestPlayer"
        assert player_data["bankroll"] == 5000
        
    def test_get_player_not_exists(self):
        """Test getting non-existent player."""
        player_data = self.manager.get_player("NonExistentPlayer")
        assert player_data is None
        
    def test_update_player_bankroll(self):
        """Test updating player bankroll."""
        self.manager.create_player("TestPlayer", 5000)
        
        self.manager.update_player_bankroll("TestPlayer", 7500)
        
        player_data = self.manager.get_player("TestPlayer")
        assert player_data["bankroll"] == 7500
        
    def test_update_player_bankroll_not_exists(self):
        """Test updating bankroll for non-existent player."""
        with pytest.raises(ValueError, match="Player 'NonExistentPlayer' not found"):
            self.manager.update_player_bankroll("NonExistentPlayer", 5000)
            
    def test_update_player_bankroll_invalid_amount(self):
        """Test updating bankroll with invalid amount."""
        self.manager.create_player("TestPlayer", 5000)
        
        with pytest.raises(ValueError, match="Bankroll cannot be negative"):
            self.manager.update_player_bankroll("TestPlayer", -1000)
            
    def test_update_player_stats(self):
        """Test updating player statistics."""
        self.manager.create_player("TestPlayer", 5000)
        
        stats = {
            "games_played": 10,
            "games_won": 3,
            "total_winnings": 2500,
            "biggest_pot": 1000
        }
        
        self.manager.update_player_stats("TestPlayer", stats)
        
        player_data = self.manager.get_player("TestPlayer")
        assert player_data["games_played"] == 10
        assert player_data["games_won"] == 3
        assert player_data["total_winnings"] == 2500
        assert player_data["biggest_pot"] == 1000
        
    def test_update_player_stats_not_exists(self):
        """Test updating stats for non-existent player."""
        stats = {"games_played": 5}
        
        with pytest.raises(ValueError, match="Player 'NonExistentPlayer' not found"):
            self.manager.update_player_stats("NonExistentPlayer", stats)
            
    def test_delete_player(self):
        """Test deleting a player."""
        self.manager.create_player("TestPlayer", 5000)
        assert "TestPlayer" in self.manager.players_data
        
        self.manager.delete_player("TestPlayer")
        assert "TestPlayer" not in self.manager.players_data
        
    def test_delete_player_not_exists(self):
        """Test deleting non-existent player."""
        with pytest.raises(ValueError, match="Player 'NonExistentPlayer' not found"):
            self.manager.delete_player("NonExistentPlayer")
            
    def test_list_players(self):
        """Test listing all players."""
        self.manager.create_player("Player1", 5000)
        self.manager.create_player("Player2", 10000)
        self.manager.create_player("Player3", 2500)
        
        players = self.manager.list_players()
        
        assert len(players) == 3
        player_names = [p["name"] for p in players]
        assert "Player1" in player_names
        assert "Player2" in player_names
        assert "Player3" in player_names
        
    def test_list_players_sorted_by_bankroll(self):
        """Test listing players sorted by bankroll."""
        self.manager.create_player("Poor", 1000)
        self.manager.create_player("Rich", 50000)
        self.manager.create_player("Middle", 10000)
        
        players = self.manager.list_players(sort_by="bankroll", reverse=True)
        
        assert players[0]["name"] == "Rich"
        assert players[1]["name"] == "Middle"
        assert players[2]["name"] == "Poor"
        
    def test_list_players_sorted_by_games(self):
        """Test listing players sorted by games played."""
        self.manager.create_player("Newbie", 5000)
        self.manager.create_player("Veteran", 5000)
        
        self.manager.update_player_stats("Newbie", {"games_played": 5})
        self.manager.update_player_stats("Veteran", {"games_played": 100})
        
        players = self.manager.list_players(sort_by="games_played", reverse=True)
        
        assert players[0]["name"] == "Veteran"
        assert players[1]["name"] == "Newbie"
        
    def test_player_exists(self):
        """Test checking if player exists."""
        assert not self.manager.player_exists("TestPlayer")
        
        self.manager.create_player("TestPlayer", 5000)
        assert self.manager.player_exists("TestPlayer")
        
    def test_backup_players_data(self):
        """Test creating backup of players data."""
        self.manager.create_player("Player1", 5000)
        self.manager.create_player("Player2", 10000)
        
        backup_file = os.path.join(self.temp_dir, "backup_players.json")
        self.manager.backup_players_data(backup_file)
        
        assert os.path.exists(backup_file)
        
        # Verify backup content
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)
            
        assert len(backup_data) == 2
        assert "Player1" in backup_data
        assert "Player2" in backup_data
        
    def test_restore_players_data(self):
        """Test restoring players data from backup."""
        # Create backup data
        backup_data = {
            "BackupPlayer1": {
                "name": "BackupPlayer1",
                "bankroll": 7500,
                "games_played": 15
            },
            "BackupPlayer2": {
                "name": "BackupPlayer2", 
                "bankroll": 12000,
                "games_played": 8
            }
        }
        
        backup_file = os.path.join(self.temp_dir, "restore_players.json")
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f)
            
        self.manager.restore_players_data(backup_file)
        
        assert len(self.manager.players_data) == 2
        assert "BackupPlayer1" in self.manager.players_data
        assert "BackupPlayer2" in self.manager.players_data
        assert self.manager.players_data["BackupPlayer1"]["bankroll"] == 7500
        
    def test_validate_player_data_valid(self):
        """Test validating valid player data."""
        valid_data = {
            "name": "TestPlayer",
            "bankroll": 5000,
            "created_at": "2023-01-01T00:00:00",
            "games_played": 10
        }
        
        assert self.manager.validate_player_data(valid_data) is True
        
    def test_validate_player_data_invalid(self):
        """Test validating invalid player data."""
        # Missing required fields
        invalid_data = {
            "name": "TestPlayer"
            # Missing bankroll
        }
        
        assert self.manager.validate_player_data(invalid_data) is False
        
        # Invalid data types
        invalid_data = {
            "name": "TestPlayer",
            "bankroll": "invalid",  # Should be number
            "created_at": "2023-01-01T00:00:00"
        }
        
        assert self.manager.validate_player_data(invalid_data) is False
        
    def test_get_player_statistics(self):
        """Test getting comprehensive player statistics."""
        self.manager.create_player("TestPlayer", 5000)
        
        # Update with some stats
        stats = {
            "games_played": 50,
            "games_won": 15,
            "total_winnings": 12500,
            "biggest_pot": 2500,
            "hands_played": 1000,
            "hands_won": 200
        }
        self.manager.update_player_stats("TestPlayer", stats)
        
        player_stats = self.manager.get_player_statistics("TestPlayer")
        
        assert player_stats["win_rate"] == 15/50  # games won / games played
        assert player_stats["hand_win_rate"] == 200/1000  # hands won / hands played
        assert player_stats["average_winnings"] == 12500/50  # total winnings / games
        
    def test_data_manager_thread_safety(self):
        """Test thread safety of data operations."""
        import threading
        
        def create_players():
            for i in range(10):
                try:
                    self.manager.create_player(f"Player{i}", 1000 + i * 100)
                except ValueError:
                    pass  # Player might already exist
                    
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=create_players)
            threads.append(thread)
            
        # Start all threads
        for thread in threads:
            thread.start()
            
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
            
        # Should have created players successfully
        assert len(self.manager.players_data) <= 10  # At most 10 unique players
        
    def test_data_file_permissions(self):
        """Test handling of file permission errors."""
        with patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = PermissionError("Permission denied")
            
            with pytest.raises(PermissionError):
                self.manager.save_players()
                
    def test_disk_space_error(self):
        """Test handling of disk space errors."""
        with patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = OSError("No space left on device")
            
            with pytest.raises(OSError):
                self.manager.save_players()

    def test_append_and_load_hand_history(self):
        """Hand histories append as JSONL and load back in order."""
        hand1 = {
            "hand_number": 1,
            "actions": [
                {
                    "player": "TestPlayer",
                    "action": "call",
                    "amount": 10,
                    "pot_before": 0,
                    "betting_round": "preflop",
                    "did_raise": False,
                }
            ],
            "winners": ["TestPlayer"],
            "pot_total": 20,
        }
        hand2 = {
            "hand_number": 2,
            "actions": [
                {
                    "player": "TestPlayer",
                    "action": "raise",
                    "amount": 20,
                    "pot_before": 20,
                    "betting_round": "preflop",
                    "did_raise": True,
                }
            ],
            "winners": ["AI_1"],
            "pot_total": 60,
        }

        path = self.manager.append_hand_history("TestPlayer", hand1)
        assert os.path.exists(path)
        assert path.endswith(".jsonl")
        assert os.path.dirname(path) == self.manager.hand_history_dir

        self.manager.append_hand_history("TestPlayer", hand2)

        newest_first = self.manager.load_hand_history("TestPlayer", limit=10, reverse=True)
        assert [h.get("hand_number") for h in newest_first[:2]] == [2, 1]

        oldest_first = self.manager.load_hand_history("TestPlayer", limit=10, reverse=False)
        assert [h.get("hand_number") for h in oldest_first[:2]] == [1, 2]

    def test_load_hand_history_missing_file(self):
        """Missing hand history file returns empty list."""
        assert self.manager.load_hand_history("MissingPlayer", limit=10, reverse=True) == []

    def test_append_hand_history_rejects_non_dict(self):
        """Non-dict hand payloads are rejected."""
        with pytest.raises(ValueError):
            self.manager.append_hand_history("TestPlayer", ["not", "a", "dict"])  # type: ignore[arg-type]
