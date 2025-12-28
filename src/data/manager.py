"""
Data Manager module for PyHoldem Pro.
Handles JSON file operations for player data persistence.
"""
import hashlib
import json
import os
import re
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional
from jsonschema import validate, ValidationError


class DataManager:
    """Manages player data persistence using JSON files."""
    
    # JSON schema for player data validation
    PLAYER_SCHEMA = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "bankroll": {"type": "number", "minimum": 0},
            "created_at": {"type": "string"},
            "last_played": {"type": "string"},
            "games_played": {"type": "integer", "minimum": 0},
            "games_won": {"type": "integer", "minimum": 0},
            "total_winnings": {"type": "number"},
            "hands_played": {"type": "integer", "minimum": 0},
            "hands_won": {"type": "integer", "minimum": 0},
            "biggest_pot": {"type": "number", "minimum": 0}
        },
        "required": ["name", "bankroll", "created_at"],
        "additionalProperties": True
    }
    
    def __init__(
        self,
        data_file: str = "data/players.json",
        *,
        hand_history_dir: Optional[str] = None,
    ):
        """
        Initialize the data manager.
        
        Args:
            data_file: Path to the JSON data file
            hand_history_dir: Optional directory for per-player JSONL hand histories
        """
        self.data_file = data_file
        base_dir = os.path.dirname(os.path.abspath(data_file))
        self.hand_history_dir = hand_history_dir or os.path.join(base_dir, "hand_histories")
        self.players_data: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()  # Thread-safe operations
        
        # Ensure data directory exists
        os.makedirs(base_dir, exist_ok=True)
        
        # Load existing data
        self.load_players()

    def _hand_history_path_for_player(self, name: str) -> str:
        normalized = (name or "").strip()
        if not normalized:
            raise ValueError("Player name cannot be empty")

        slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", normalized).strip("_")
        if not slug:
            slug = "player"

        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10]
        filename = f"{slug}__{digest}.jsonl"
        return os.path.join(self.hand_history_dir, filename)

    def append_hand_history(self, player_name: str, hand_record: Dict[str, Any]) -> str:
        """
        Append a single hand record to a per-player JSONL hand history file.

        Args:
            player_name: Player name
            hand_record: JSON-serializable hand record (dict)

        Returns:
            Path to the JSONL history file written.
        """
        if not isinstance(hand_record, dict):
            raise ValueError("Hand record must be a dictionary")

        with self._lock:
            path = self._hand_history_path_for_player(player_name)
            os.makedirs(os.path.dirname(path), exist_ok=True)

            payload = dict(hand_record)
            payload.setdefault("schema_version", 1)
            payload.setdefault("saved_at", datetime.now().isoformat())

            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")

            return path

    def _read_last_jsonl_lines(self, path: str, limit: int) -> List[str]:
        if limit <= 0:
            return []

        # Read from the end of the file in chunks until we have enough lines.
        chunk_size = 8192
        lines: List[bytes] = []
        buffer = b""
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            position = f.tell()

            while position > 0 and len(lines) <= limit:
                read_size = min(chunk_size, position)
                position -= read_size
                f.seek(position)
                chunk = f.read(read_size)
                buffer = chunk + buffer
                lines = buffer.splitlines()

        tail = lines[-limit:]
        decoded: List[str] = []
        for raw in tail:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("utf-8", errors="replace")
            if text.strip():
                decoded.append(text)
        return decoded

    def load_hand_history(
        self,
        player_name: str,
        *,
        limit: int = 200,
        reverse: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Load a player's hand history from their JSONL file.

        Args:
            player_name: Player name
            limit: Maximum number of hands to return (most recent if reverse=True)
            reverse: If True, return newest-first; otherwise oldest-first

        Returns:
            List of hand record dictionaries.
        """
        with self._lock:
            path = self._hand_history_path_for_player(player_name)
            if not os.path.exists(path):
                return []

            if limit <= 0:
                return []

            try:
                lines = self._read_last_jsonl_lines(path, limit)
            except OSError:
                return []

            records: List[Dict[str, Any]] = []
            for line in lines:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    records.append(record)

            if reverse:
                records.reverse()
            return records
    
    def create_player(self, name: str, initial_bankroll: int) -> Dict[str, Any]:
        """
        Create a new player profile.
        
        Args:
            name: Player name
            initial_bankroll: Starting bankroll
            
        Returns:
            Player data dictionary
            
        Raises:
            ValueError: If name is invalid, bankroll is invalid, or player exists
        """
        if not name or not name.strip():
            raise ValueError("Player name cannot be empty")
        
        if initial_bankroll <= 0:
            raise ValueError("Initial bankroll must be positive")
        
        name = name.strip()
        
        with self._lock:
            if name in self.players_data:
                raise ValueError(f"Player '{name}' already exists")
            
            now = datetime.now().isoformat()
            player_data = {
                "name": name,
                "bankroll": int(initial_bankroll),
                "created_at": now,
                "last_played": now,
                "games_played": 0,
                "games_won": 0,
                "total_winnings": 0.0,
                "hands_played": 0,
                "hands_won": 0,
                "biggest_pot": 0.0
            }
            
            # Validate data
            self.validate_player_data(player_data)
            
            self.players_data[name] = player_data
            return player_data.copy()
    
    def get_player(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get player data by name.
        
        Args:
            name: Player name
            
        Returns:
            Player data dictionary or None if not found
        """
        with self._lock:
            if not name or name.strip() not in self.players_data:
                return None
            return self.players_data[name.strip()].copy()
    
    def player_exists(self, name: str) -> bool:
        """
        Check if a player exists.
        
        Args:
            name: Player name
            
        Returns:
            True if player exists
        """
        with self._lock:
            return name.strip() in self.players_data if name else False
    
    def update_player_bankroll(self, name: str, new_bankroll: int):
        """
        Update a player's bankroll.
        
        Args:
            name: Player name
            new_bankroll: New bankroll amount
            
        Raises:
            ValueError: If player not found or invalid bankroll
        """
        if new_bankroll < 0:
            raise ValueError("Bankroll cannot be negative")
        
        with self._lock:
            if name not in self.players_data:
                raise ValueError(f"Player '{name}' not found")
            
            self.players_data[name]["bankroll"] = int(new_bankroll)
            self.players_data[name]["last_played"] = datetime.now().isoformat()
    
    def update_player_stats(self, name: str, stats: Dict[str, Any]):
        """
        Update player statistics.
        
        Args:
            name: Player name
            stats: Dictionary of statistics to update
            
        Raises:
            ValueError: If player not found
        """
        with self._lock:
            if name not in self.players_data:
                raise ValueError(f"Player '{name}' not found")
            
            # Update stats
            for key, value in stats.items():
                self.players_data[name][key] = value
            
            self.players_data[name]["last_played"] = datetime.now().isoformat()
    
    def save_player(self, player):
        """
        Save/update a player object to the data store.
        
        Args:
            player: Player object with name and bankroll attributes
        """
        # Update player statistics (if available on the object)
        stats: Dict[str, Any] = {}
        for attr in ("hands_played", "hands_won", "total_winnings"):
            if hasattr(player, attr):
                stats[attr] = getattr(player, attr)

        if stats:
            try:
                self.update_player_stats(player.name, stats)
            except ValueError:
                # Player profile may not exist yet in some contexts.
                pass

        # Update the player's bankroll
        self.update_player_bankroll(player.name, player.bankroll)
        # Save to file
        self.save_players()
    
    def delete_player(self, name: str):
        """
        Delete a player profile.
        
        Args:
            name: Player name
            
        Raises:
            ValueError: If player not found
        """
        with self._lock:
            if name not in self.players_data:
                raise ValueError(f"Player '{name}' not found")
            
            del self.players_data[name]
    
    def list_players(self, sort_by: str = "name", reverse: bool = False) -> List[Dict[str, Any]]:
        """
        List all players with optional sorting.
        
        Args:
            sort_by: Field to sort by (name, bankroll, games_played, etc.)
            reverse: Sort in reverse order
            
        Returns:
            List of player data dictionaries
        """
        with self._lock:
            players = list(self.players_data.values())
            
            if sort_by and players:
                try:
                    players.sort(key=lambda p: p.get(sort_by, 0), reverse=reverse)
                except (TypeError, KeyError):
                    # Fall back to name sorting if sort_by field doesn't exist
                    players.sort(key=lambda p: p.get("name", ""), reverse=reverse)
            
            return [player.copy() for player in players]
    
    def save_players(self):
        """
        Save player data to JSON file.
        
        Raises:
            IOError: If file cannot be written
        """
        with self._lock:
            try:
                # Create backup before saving
                if os.path.exists(self.data_file):
                    backup_file = f"{self.data_file}.bak"
                    os.rename(self.data_file, backup_file)
                
                # Save to file
                with open(self.data_file, 'w', encoding='utf-8') as f:
                    json.dump(self.players_data, f, indent=2, ensure_ascii=False)
                    
            except (IOError, OSError, PermissionError) as e:
                # Restore backup if save failed
                backup_file = f"{self.data_file}.bak"
                if os.path.exists(backup_file):
                    os.rename(backup_file, self.data_file)
                # Re-raise the original exception
                raise
    
    def load_players(self):
        """
        Load player data from JSON file.
        
        Raises:
            json.JSONDecodeError: If file contains invalid JSON
        """
        with self._lock:
            if not os.path.exists(self.data_file):
                # Create empty data structure
                self.players_data = {}
                return
            
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Handle different file formats
                if isinstance(data, dict):
                    if "players" in data:
                        # New format with metadata
                        self.players_data = data["players"]
                    else:
                        # Direct player data
                        self.players_data = data
                else:
                    self.players_data = {}
                    
            except json.JSONDecodeError:
                raise
            except Exception:
                # If file is corrupted, start fresh
                self.players_data = {}
    
    def backup_players_data(self, backup_file: str):
        """
        Create a backup of player data.
        
        Args:
            backup_file: Path to backup file
        """
        with self._lock:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(self.players_data, f, indent=2, ensure_ascii=False)
    
    def restore_players_data(self, backup_file: str):
        """
        Restore player data from backup.
        
        Args:
            backup_file: Path to backup file
            
        Raises:
            IOError: If backup file cannot be read
        """
        with self._lock:
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    self.players_data = json.load(f)
            except Exception as e:
                raise IOError(f"Failed to restore from backup: {e}")
    
    def validate_player_data(self, player_data: Dict[str, Any]) -> bool:
        """
        Validate player data against schema.
        
        Args:
            player_data: Player data to validate
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If data is invalid
        """
        try:
            validate(instance=player_data, schema=self.PLAYER_SCHEMA)
            return True
        except ValidationError:
            return False
    
    def get_player_statistics(self, name: str) -> Dict[str, Any]:
        """
        Get comprehensive player statistics.
        
        Args:
            name: Player name
            
        Returns:
            Dictionary with calculated statistics
        """
        with self._lock:
            player = self.players_data.get(name)
            if not player:
                return {}
            
            stats = player.copy()
            
            # Calculate derived statistics
            games_played = player.get("games_played", 0)
            games_won = player.get("games_won", 0)
            hands_played = player.get("hands_played", 0)
            hands_won = player.get("hands_won", 0)
            total_winnings = player.get("total_winnings", 0)
            
            if games_played > 0:
                stats["win_rate"] = games_won / games_played
                stats["average_winnings"] = total_winnings / games_played
            else:
                stats["win_rate"] = 0.0
                stats["average_winnings"] = 0.0
            
            if hands_played > 0:
                stats["hand_win_rate"] = hands_won / hands_played
            else:
                stats["hand_win_rate"] = 0.0
            
            return stats
    
    def get_leaderboard(self, metric: str = "bankroll", limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get player leaderboard.
        
        Args:
            metric: Metric to rank by (bankroll, total_winnings, games_won, etc.)
            limit: Maximum number of players to return
            
        Returns:
            List of top players
        """
        players = self.list_players(sort_by=metric, reverse=True)
        return players[:limit]
    
    def cleanup_inactive_players(self, days_inactive: int = 365):
        """
        Remove players who haven't played in specified days.
        
        Args:
            days_inactive: Number of days of inactivity before removal
            
        Returns:
            Number of players removed
        """
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_inactive)
        removed_count = 0
        
        with self._lock:
            players_to_remove = []
            
            for name, player_data in self.players_data.items():
                try:
                    last_played = datetime.fromisoformat(player_data["last_played"])
                    if last_played < cutoff_date:
                        players_to_remove.append(name)
                except (KeyError, ValueError):
                    # Remove players with invalid/missing last_played date
                    players_to_remove.append(name)
            
            for name in players_to_remove:
                del self.players_data[name]
                removed_count += 1
        
        return removed_count
    
    def export_data(self, export_file: str, format: str = "json"):
        """
        Export player data to file.
        
        Args:
            export_file: Path to export file
            format: Export format ("json" or "csv")
        """
        with self._lock:
            if format.lower() == "json":
                with open(export_file, 'w', encoding='utf-8') as f:
                    json.dump(self.players_data, f, indent=2, ensure_ascii=False)
            elif format.lower() == "csv":
                import csv
                players = list(self.players_data.values())
                if players:
                    with open(export_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=players[0].keys())
                        writer.writeheader()
                        writer.writerows(players)
    
    def get_data_summary(self) -> Dict[str, Any]:
        """
        Get summary of data manager state.
        
        Returns:
            Summary statistics
        """
        with self._lock:
            total_players = len(self.players_data)
            total_bankroll = sum(p.get("bankroll", 0) for p in self.players_data.values())
            total_games = sum(p.get("games_played", 0) for p in self.players_data.values())
            
            return {
                "total_players": total_players,
                "total_bankroll": total_bankroll,
                "total_games_played": total_games,
                "data_file": self.data_file,
                "file_exists": os.path.exists(self.data_file)
            }
