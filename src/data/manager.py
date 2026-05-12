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
from data.schema import PLAYER_SCHEMA as PLAYER_SCHEMA_DEF


def _resolve_db_url(explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return explicit
    db_url = os.getenv("PYHOLDEM_DB_URL")
    if db_url:
        return db_url
    use_db = os.getenv("PYHOLDEM_USE_DB", "").strip().lower()
    if use_db in {"1", "true", "yes", "on"}:
        return os.getenv("DATABASE_URL")
    return None


class DataManager:
    """Manages player data persistence using JSON files."""
    
    # JSON schema for player data validation
    PLAYER_SCHEMA = PLAYER_SCHEMA_DEF
    
    def __init__(
        self,
        data_file: str = "data/players.json",
        *,
        hand_history_dir: Optional[str] = None,
        db_url: Optional[str] = None,
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
        self._db_url = _resolve_db_url(db_url)
        self._use_db = bool(self._db_url)
        self._db = None

        if self._use_db:
            from data.postgres_store import PostgresStore

            self._db = PostgresStore(self._db_url)
            return
        
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
        if self._use_db:
            return self._db.append_hand_history(player_name, hand_record)

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
        if self._use_db:
            return self._db.load_hand_history(player_name, limit=limit, reverse=reverse)

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
        if self._use_db:
            return self._db.create_player(name, initial_bankroll)

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
        if self._use_db:
            return self._db.get_player(name)

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
        if self._use_db:
            return self._db.player_exists(name)

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
        if self._use_db:
            return self._db.update_player_bankroll(name, new_bankroll)

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
        if self._use_db:
            return self._db.update_player_stats(name, stats)

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
        if self._use_db:
            return self._db.save_player(player)

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
        if self._use_db:
            return self._db.delete_player(name)

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
        if self._use_db:
            return self._db.list_players(sort_by=sort_by, reverse=reverse)

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
        if self._use_db:
            return self._db.save_players()

        with self._lock:
            try:
                # Create backup before saving
                if os.path.exists(self.data_file):
                    backup_file = f"{self.data_file}.bak"
                    if os.path.exists(backup_file):
                        os.remove(backup_file)
                    os.replace(self.data_file, backup_file)
                
                # Save to file
                with open(self.data_file, 'w', encoding='utf-8') as f:
                    json.dump(self.players_data, f, indent=2, ensure_ascii=False)
                    
            except (IOError, OSError, PermissionError) as e:
                # Restore backup if save failed
                backup_file = f"{self.data_file}.bak"
                if os.path.exists(backup_file):
                    os.replace(backup_file, self.data_file)
                # Re-raise the original exception
                raise
    
    def load_players(self):
        """
        Load player data from JSON file.
        
        Raises:
            json.JSONDecodeError: If file contains invalid JSON
        """
        if self._use_db:
            return self._db.load_players()

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
        if self._use_db:
            return self._db.backup_players_data(backup_file)

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
        if self._use_db:
            return self._db.restore_players_data(backup_file)

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
        if self._use_db:
            return self._db.validate_player_data(player_data)

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
        if self._use_db:
            return self._db.get_player_statistics(name)

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
        if self._use_db:
            return self._db.get_leaderboard(metric=metric, limit=limit)

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
        if self._use_db:
            return self._db.cleanup_inactive_players(days_inactive=days_inactive)

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
        if self._use_db:
            return self._db.export_data(export_file, format=format)

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
    
    def create_session(self, session_data: Dict[str, Any]) -> None:
        """
        Create a new game session record.
        """
        if self._use_db and self._db:
            self._db.create_session(session_data)
            return

        if not isinstance(session_data, dict):
            raise ValueError("Session data must be a dictionary")

        player_name = str(session_data.get("player_name") or "").strip()
        if not player_name:
            raise ValueError("Session player name is required")

        payload = dict(session_data)
        now = datetime.now().isoformat()
        payload.setdefault("created_at", now)
        payload.setdefault("started_at", payload.get("created_at", now))
        payload.setdefault("hands_played", 0)

        with self._lock:
            player = self.players_data.get(player_name)
            if player is None:
                player = {
                    "name": player_name,
                    "bankroll": int(payload.get("bankroll", 10000) or 10000),
                    "created_at": now,
                    "last_played": now,
                    "games_played": 0,
                    "games_won": 0,
                    "total_winnings": 0.0,
                    "hands_played": 0,
                    "hands_won": 0,
                    "biggest_pot": 0.0,
                }
                self.players_data[player_name] = player

            sessions = player.setdefault("sessions", [])
            if not isinstance(sessions, list):
                sessions = []
                player["sessions"] = sessions

            session_id = payload.get("id")
            existing = None
            for index, session in enumerate(sessions):
                if isinstance(session, dict) and session.get("id") == session_id:
                    existing = index
                    break

            if existing is None:
                sessions.append(payload)
            else:
                merged = dict(sessions[existing])
                merged.update(payload)
                sessions[existing] = merged
                payload = merged

            player["last_session"] = payload
            player["last_played"] = now
            player["games_played"] = len(sessions)
            self.save_players()

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        """
        Update an existing game session record.
        """
        if self._use_db and self._db:
            self._db.update_session(session_id, updates)
            return

        if not session_id:
            raise ValueError("Session ID is required")
        if not isinstance(updates, dict):
            raise ValueError("Session updates must be a dictionary")

        player_name = str(updates.get("player_name") or "").strip()
        now = datetime.now().isoformat()

        with self._lock:
            players = [self.players_data.get(player_name)] if player_name else list(self.players_data.values())
            for player in players:
                if not isinstance(player, dict):
                    continue
                sessions = player.setdefault("sessions", [])
                if not isinstance(sessions, list):
                    sessions = []
                    player["sessions"] = sessions

                target_index = None
                for index, session in enumerate(sessions):
                    if isinstance(session, dict) and session.get("id") == session_id:
                        target_index = index
                        break

                if target_index is None and player_name:
                    payload = {"id": session_id, "player_name": player_name, "created_at": now}
                    payload.update(updates)
                    sessions.append(payload)
                    target_index = len(sessions) - 1

                if target_index is None:
                    continue

                merged = dict(sessions[target_index])
                merged.update(updates)
                merged["id"] = session_id
                merged.setdefault("player_name", player.get("name"))
                merged["updated_at"] = now
                sessions[target_index] = merged
                player["last_session"] = merged
                player["last_played"] = now
                player["games_played"] = len(sessions)
                player["hands_played"] = sum(int(s.get("hands_played", 0) or 0) for s in sessions if isinstance(s, dict))
                if "bankroll_end" in merged:
                    player["bankroll"] = int(merged.get("bankroll_end") or player.get("bankroll", 0))
                if "biggest_pot" in merged:
                    player["biggest_pot"] = max(int(player.get("biggest_pot", 0) or 0), int(merged.get("biggest_pot", 0) or 0))
                self.save_players()
                return

    def get_sessions(self, player_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        if self._use_db and self._db:
            return self._db.get_sessions(player_name, limit)
        with self._lock:
            player = self.players_data.get(player_name)
            if not isinstance(player, dict):
                return []
            sessions = player.get("sessions") or []
            if not isinstance(sessions, list):
                return []
            records = [dict(session) for session in sessions if isinstance(session, dict)]
            records.sort(key=lambda s: s.get("updated_at") or s.get("ended_at") or s.get("started_at") or s.get("created_at") or "")
            return records[-limit:]

    def get_filtered_hands(self, player_name: str, winner: Optional[str] = None, min_pot: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if self._use_db and self._db:
             return self._db.get_filtered_hands(player_name, winner, min_pot, limit)
        records = self.load_hand_history(player_name, limit=max(limit * 5, limit), reverse=True)
        filtered: List[Dict[str, Any]] = []
        for hand in records:
            if winner:
                winners = hand.get("winners") or []
                if winner == "hero":
                    hero_won = player_name in winners or bool((hand.get("meta") or {}).get("hero_won"))
                    if not hero_won:
                        continue
                elif winner not in winners and hand.get("winner") != winner:
                    continue

            if min_pot is not None:
                pot_total = hand.get("pot_total", hand.get("pot_size", 0))
                try:
                    if int(pot_total or 0) < int(min_pot):
                        continue
                except (TypeError, ValueError):
                    continue

            filtered.append(hand)
            if len(filtered) >= limit:
                break
        return filtered

    def get_data_summary(self) -> Dict[str, Any]:
        """
        Get summary of data manager state.
        
        Returns:
            Summary statistics
        """
        if self._use_db:
            return self._db.get_data_summary()

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
