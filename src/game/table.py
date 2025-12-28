"""
Table module for PyHoldem Pro.
Implements table management, seating, and position handling.
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from game.player import Player


class TableType(Enum):
    """Enumeration for table types."""
    CASH_GAME = "cash_game"
    TOURNAMENT = "tournament"


class SeatPosition(Enum):
    """Enumeration for seat positions around the table."""
    SEAT_1 = 1
    SEAT_2 = 2
    SEAT_3 = 3
    SEAT_4 = 4
    SEAT_5 = 5
    SEAT_6 = 6
    SEAT_7 = 7
    SEAT_8 = 8
    SEAT_9 = 9
    
    def __lt__(self, other):
        """Compare seat positions."""
        if not isinstance(other, SeatPosition):
            return NotImplemented
        return self.value < other.value


class Table:
    """Represents a poker table with seating and position management."""
    
    def __init__(self, table_type: TableType, max_players: int = 9):
        """
        Initialize a poker table.
        
        Args:
            table_type: Type of table (cash game or tournament)
            max_players: Maximum number of players (2-9)
            
        Raises:
            ValueError: If max_players is not between 2 and 9
        """
        if not 2 <= max_players <= 9:
            raise ValueError("Max players must be between 2 and 9")
        
        self.table_type = table_type
        self.max_players = max_players
        
        # Initialize 9 seats (None = empty)
        self.seats: List[Optional[Player]] = [None] * 9
        self._num_players = 0
        
        # Position tracking (0-based indices into seats array)
        self.dealer_position = 0
        self.small_blind_position = 1
        self.big_blind_position = 2
    
    @property
    def num_players(self) -> int:
        """Return the number of players currently seated."""
        return self._num_players
    
    def add_player(self, player: Player) -> int:
        """
        Add a player to the table.
        
        Args:
            player: The player to add
            
        Returns:
            The seat number (1-9) where the player was seated
            
        Raises:
            ValueError: If table is full or player is already seated
        """
        if self.is_full():
            raise ValueError("Table is full")
        
        if player in self.get_players_in_order():
            raise ValueError(f"Player {player.name} is already seated at this table")
        
        # Find first empty seat
        for i, seat in enumerate(self.seats):
            if seat is None:
                self.seats[i] = player
                player.position = i  # Position matches seat index (0-8)
                self._num_players += 1
                
                # Update positions if we now have enough players
                if self._num_players >= 2:
                    self._update_positions()
                
                return i  # Return seat index (0-8)
        
        raise ValueError("No empty seats available")
    
    def remove_player(self, player: Player):
        """
        Remove a player from the table.
        
        Args:
            player: The player to remove
            
        Raises:
            ValueError: If player is not seated at this table
        """
        for i, seat in enumerate(self.seats):
            if seat == player:
                self.seats[i] = None
                player.position = 0  # Reset position
                self._num_players -= 1
                return
        
        raise ValueError(f"Player {player.name} is not seated at this table")
    
    def get_players_in_order(self) -> List[Player]:
        """
        Get all seated players in seating order (seat 1 to 9).
        
        Returns:
            List of players in seat order
        """
        return [player for player in self.seats if player is not None]
    
    def get_active_players(self) -> List[Player]:
        """
        Get all active players (not folded, not busted).
        
        Returns:
            List of active players
        """
        return [player for player in self.get_players_in_order() 
                if not player.folded and player.bankroll > 0]
    
    def get_players_in_hand(self) -> List[Player]:
        """
        Get all players still in the current hand (not folded).
        
        Returns:
            List of players still in hand
        """
        return [player for player in self.get_players_in_order() if not player.folded]

    def get_players_in_tournament(self) -> List[Player]:
        """
        Get all players still in the tournament (bankroll > 0).

        Returns:
            List of players still in the tournament
        """
        return [player for player in self.get_players_in_order() if player.bankroll > 0]
    
    def rotate_dealer_button(self):
        """Rotate the dealer button to the next active player."""
        active_positions = []
        for i, player in enumerate(self.seats):
            if player is not None and player.bankroll > 0:
                active_positions.append(i)
        
        if len(active_positions) < 2:
            return  # Not enough players to rotate
        
        # Find current dealer in active positions
        try:
            current_index = active_positions.index(self.dealer_position)
            # Move to next active position
            next_index = (current_index + 1) % len(active_positions)
            self.dealer_position = active_positions[next_index]
        except ValueError:
            # Current dealer not active, reset to first active player
            self.dealer_position = active_positions[0]
        
        # Update blind positions
        self._update_blind_positions(active_positions)
    
    def _update_blind_positions(self, active_positions: List[int]):
        """Update small blind and big blind positions."""
        if len(active_positions) < 2:
            return
        
        dealer_index = active_positions.index(self.dealer_position)
        
        if len(active_positions) == 2:
            # Heads-up: dealer is small blind
            self.small_blind_position = self.dealer_position
            self.big_blind_position = active_positions[1 - dealer_index]
        else:
            # Multi-way: small blind is left of dealer
            sb_index = (dealer_index + 1) % len(active_positions)
            bb_index = (dealer_index + 2) % len(active_positions)
            self.small_blind_position = active_positions[sb_index]
            self.big_blind_position = active_positions[bb_index]
    
    def _update_positions(self):
        """Update dealer and blind positions when table configuration changes."""
        active_positions = []
        for i, player in enumerate(self.seats):
            if player is not None and player.bankroll > 0:
                active_positions.append(i)
        
        if len(active_positions) >= 2:
            # Set dealer to first active player if not set properly
            if self.dealer_position not in active_positions:
                self.dealer_position = active_positions[0]
            
            self._update_blind_positions(active_positions)
    
    def get_dealer_player(self) -> Optional[Player]:
        """Get the player in the dealer position."""
        return self.seats[self.dealer_position]
    
    def get_small_blind_player(self) -> Optional[Player]:
        """Get the player in the small blind position."""
        return self.seats[self.small_blind_position]
    
    def get_big_blind_player(self) -> Optional[Player]:
        """Get the player in the big blind position."""
        return self.seats[self.big_blind_position]
    
    def get_next_to_act(self, current_position: Optional[int] = None) -> Optional[Player]:
        """
        Get the next player to act.
        
        Args:
            current_position: Current position (0-8), if None starts from big blind
            
        Returns:
            Next active player to act, or None if none found
        """
        active_positions = []
        for i, player in enumerate(self.seats):
            if (player is not None and not player.folded and 
                not player.all_in and player.bankroll > 0):
                active_positions.append(i)
        
        if not active_positions:
            return None
        
        # Start from position after big blind if not specified
        if current_position is None:
            start_pos = (self.big_blind_position + 1) % 9
        else:
            start_pos = (current_position + 1) % 9
        
        # Find next active player
        for _ in range(9):  # Maximum 9 positions to check
            if start_pos in active_positions:
                return self.seats[start_pos]
            start_pos = (start_pos + 1) % 9
        
        return None
    
    def get_seat_number(self, player: Player) -> Optional[int]:
        """
        Get the seat index for a player.
        
        Args:
            player: The player to find
            
        Returns:
            Seat index (0-8) or None if not found
        """
        for i, seat in enumerate(self.seats):
            if seat == player:
                return i
        return None

    def get_player_position(self, player: Player) -> Optional[int]:
        """
        Get the position (seat index) of a player.

        Args:
            player: The player to find

        Returns:
            The seat index (0-8) or None if not found
        """
        return self.get_seat_number(player)
    
    def is_full(self) -> bool:
        """Check if the table is full."""
        return self._num_players >= self.max_players
    
    def can_start_game(self) -> bool:
        """Check if there are enough players to start a game."""
        return self._num_players >= 2
    
    def reset_for_new_hand(self):
        """Reset table state for a new hand."""
        for player in self.get_players_in_order():
            player.reset_for_new_hand()
    
    def get_table_state(self) -> Dict[str, Any]:
        """
        Get current table state for serialization.
        
        Returns:
            Dictionary containing table state
        """
        players_data = []
        for i, player in enumerate(self.seats):
            if player is not None:
                players_data.append({
                    'seat': i + 1,
                    'name': player.name,
                    'bankroll': player.bankroll,
                    'position': player.position,
                    'folded': player.folded,
                    'all_in': player.all_in
                })
        
        return {
            'table_type': self.table_type.value,
            'max_players': self.max_players,
            'num_players': self.num_players,
            'dealer_position': self.dealer_position + 1,  # Convert to 1-9
            'small_blind_position': self.small_blind_position + 1,
            'big_blind_position': self.big_blind_position + 1,
            'players': players_data
        }
    
    def __str__(self) -> str:
        """Return string representation of table."""
        table_type_str = "Cash Game" if self.table_type == TableType.CASH_GAME else "Tournament"
        players_str = f"{self.num_players}/{self.max_players}"
        
        player_names = [p.name for p in self.get_players_in_order()]
        players_list = ", ".join(player_names[:3])
        if len(player_names) > 3:
            players_list += f" and {len(player_names) - 3} others"
        
        return f"{table_type_str} Table ({players_str}): {players_list}"
    
    def __repr__(self) -> str:
        """Return repr representation of table."""
        return f"Table(type={self.table_type.value}, players={self.num_players}/{self.max_players})"
