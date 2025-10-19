"""
Player module for PyHoldem Pro.
Implements Player class for managing player state and actions.
"""
from enum import Enum
from typing import List, Optional, Tuple
from src.game.card import Card


class PlayerAction(Enum):
    """Enumeration for player actions."""
    FOLD = "fold"
    CALL = "call"
    RAISE = "raise"
    CHECK = "check"
    ALL_IN = "all_in"


class Player:
    """Represents a poker player."""
    
    def __init__(self, name: str, bankroll: float):
        """
        Initialize a player.
        
        Args:
            name: Player name
            bankroll: Starting bankroll
            
        Raises:
            ValueError: If name is empty or bankroll is negative
        """
        if not name or not name.strip():
            raise ValueError("Player name cannot be empty")
        if bankroll < 0:
            raise ValueError("Bankroll must be non-negative")
        
        self.name = name.strip()
        self.bankroll = bankroll
        self.hole_cards: List[Card] = []
        self.current_bet = 0
        self.total_bet = 0
        self.folded = False
        self.all_in = False
        self.position = 0
        
        # Statistics tracking
        self.hands_played = 0
        self.hands_won = 0
        self.total_winnings = 0
        self._initial_bankroll = bankroll
    
    def deal_hole_cards(self, cards: List[Card]):
        """
        Deal hole cards to the player.
        
        Args:
            cards: List of exactly 2 cards
            
        Raises:
            ValueError: If not exactly 2 cards provided
        """
        if len(cards) != 2:
            raise ValueError(f"Must deal exactly 2 hole cards, got {len(cards)}")
        self.hole_cards = cards.copy()
    
    def place_bet(self, amount: float):
        """
        Place a bet.
        
        Args:
            amount: Amount to bet
            
        Raises:
            ValueError: If amount is invalid or insufficient funds
        """
        if amount <= 0:
            raise ValueError("Bet amount must be positive")
        if amount > self.bankroll:
            raise ValueError(f"Insufficient funds: trying to bet {amount} with bankroll {self.bankroll}")
        
        self.bankroll -= amount
        self.current_bet += amount
        self.total_bet += amount
    
    def add_to_bet(self, amount: float):
        """
        Add to existing bet (for raises).
        
        Args:
            amount: Additional amount to bet
        """
        self.place_bet(amount)
    
    def call(self, target_amount: float) -> float:
        """
        Call a bet.
        
        Args:
            target_amount: The amount to call to
            
        Returns:
            The amount actually called
        """
        call_amount = target_amount - self.current_bet
        if call_amount <= 0:
            return 0
        
        actual_call = min(call_amount, self.bankroll)
        if actual_call > 0:
            self.place_bet(actual_call)
        return actual_call
    
    def raise_bet(self, current_bet: float, raise_to: float) -> float:
        """
        Raise the bet.
        
        Args:
            current_bet: Current bet amount
            raise_to: Amount to raise to
            
        Returns:
            The raise amount
        """
        amount_to_add = raise_to - self.current_bet
        self.place_bet(amount_to_add)
        return raise_to - current_bet
    
    def go_all_in(self) -> float:
        """
        Go all-in with remaining bankroll.
        
        Returns:
            The all-in amount
        """
        all_in_amount = self.bankroll
        if all_in_amount > 0:
            self.place_bet(all_in_amount)
            self.all_in = True
        return all_in_amount
    
    def fold(self):
        """Fold the hand."""
        self.folded = True
    
    def can_bet(self, amount: float) -> bool:
        """
        Check if player can bet the specified amount.
        
        Args:
            amount: Amount to check
            
        Returns:
            True if player can bet this amount
        """
        return amount <= self.bankroll
    
    def can_call(self, target_amount: float) -> bool:
        """
        Check if player can call to the target amount.
        
        Args:
            target_amount: Target bet amount
            
        Returns:
            True if player can call
        """
        call_amount = target_amount - self.current_bet
        return call_amount <= self.bankroll
    
    def can_raise(self, current_bet: float, raise_to: float) -> bool:
        """
        Check if player can raise to specified amount.
        
        Args:
            current_bet: Current bet amount
            raise_to: Amount to raise to
            
        Returns:
            True if player can make this raise
        """
        amount_needed = raise_to - self.current_bet
        return amount_needed <= self.bankroll
    
    def reset_for_new_hand(self):
        """Reset player state for a new hand."""
        self.hole_cards = []
        self.current_bet = 0
        self.folded = False
        self.all_in = False
        # Note: total_bet and bankroll are NOT reset
    
    def reset_for_new_round(self):
        """Reset player state for a new betting round."""
        self.current_bet = 0
        # total_bet and bankroll remain unchanged
    
    def add_winnings(self, amount: float):
        """
        Add winnings to player's bankroll.
        
        Args:
            amount: Amount won
        """
        self.bankroll += amount
        self.total_winnings += amount
    
    @property
    def is_active(self) -> bool:
        """Check if player is active (not folded and not all-in)."""
        return not self.folded and not self.all_in
    
    @property
    def total_invested(self) -> float:
        """Return total amount invested in current hand."""
        return self.total_bet
    
    @property
    def net_position(self) -> float:
        """Calculate player's net position (current bankroll - initial + winnings - losses)."""
        return self.bankroll - self._initial_bankroll
    
    def __str__(self) -> str:
        """Return string representation of player."""
        status = []
        if self.folded:
            status.append("Folded")
        if self.all_in:
            status.append("All-in")
        status_str = f" ({', '.join(status)})" if status else ""
        return f"{self.name}: ${self.bankroll:.2f}{status_str}"
    
    def __repr__(self) -> str:
        """Return repr representation of player."""
        return f"Player(name='{self.name}', bankroll={self.bankroll})"
    
    def __eq__(self, other) -> bool:
        """Check player equality based on name."""
        if not isinstance(other, Player):
            return NotImplemented
        return self.name == other.name
    
    def __hash__(self) -> int:
        """Return hash for use in sets/dicts."""
        return hash(self.name)
