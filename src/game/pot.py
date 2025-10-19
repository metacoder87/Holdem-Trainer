"""
Pot module for PyHoldem Pro.
Implements pot management including side pots.
"""
from typing import List, Dict, Optional
from collections import defaultdict
from src.game.player import Player


class SidePot:
    """Represents a side pot in a poker game."""
    
    def __init__(self, amount: float, eligible_players: List[Player]):
        """
        Initialize a side pot.
        
        Args:
            amount: The pot amount
            eligible_players: Players eligible to win this pot
        """
        self.amount = amount
        self.eligible_players = eligible_players.copy()
    
    def distribute(self, winners: List[Player]) -> Dict[Player, float]:
        """
        Distribute the side pot to eligible winners.
        
        Args:
            winners: List of winning players
            
        Returns:
            Dictionary of player -> winnings
        """
        eligible_winners = [w for w in winners if w in self.eligible_players]
        
        if not eligible_winners:
            return {}
        
        # Split pot evenly among eligible winners
        amount_per_winner = self.amount / len(eligible_winners)
        
        winnings = {}
        for winner in eligible_winners:
            winnings[winner] = amount_per_winner
        
        return winnings
    
    def __str__(self) -> str:
        """Return string representation of side pot."""
        return f"SidePot: ${self.amount:.2f} ({len(self.eligible_players)} players eligible)"


class Pot:
    """Manages the main pot and side pots in a poker game."""
    
    def __init__(self):
        """Initialize an empty pot."""
        self.total = 0.0
        self.main_pot = 0.0
        self.side_pots: List[SidePot] = []
        self.player_contributions: Dict[Player, float] = defaultdict(float)
        self.eligible_players: List[Player] = []
    
    def add_bet(self, player: Player, amount: float):
        """
        Add a bet to the pot.
        
        Args:
            player: The betting player
            amount: The bet amount
        """
        self.total += amount
        self.main_pot += amount
        self.player_contributions[player] += amount
        
        if player not in self.eligible_players:
            self.eligible_players.append(player)
    
    def get_player_contribution(self, player: Player) -> float:
        """
        Get a player's total contribution to the pot.
        
        Args:
            player: The player to check
            
        Returns:
            The player's total contribution
        """
        return self.player_contributions.get(player, 0.0)
    
    def create_side_pots(self):
        """Create side pots when players are all-in for different amounts."""
        if not self.player_contributions:
            return
        
        # Reset side pots
        self.side_pots = []
        
        # Get all contribution amounts and sort them
        contribution_levels = sorted(set(self.player_contributions.values()))
        
        last_level = 0
        for level in contribution_levels:
            # Find players eligible for this pot level
            eligible = [p for p, amt in self.player_contributions.items() 
                       if amt >= level]
            
            if eligible:
                # Calculate pot for this level
                pot_amount = (level - last_level) * len(eligible)
                
                if last_level == 0:
                    # This is the main pot
                    self.main_pot = pot_amount
                else:
                    # This is a side pot  
                    side_pot = SidePot(pot_amount, eligible)
                    self.side_pots.append(side_pot)
                
                last_level = level
        
        # Recalculate total
        self.total = self.main_pot + sum(sp.amount for sp in self.side_pots)
    
    def distribute(self, winners: List[Player]) -> Dict[Player, float]:
        """
        Distribute the pot to winners.
        
        Args:
            winners: List of winning players
            
        Returns:
            Dictionary of player -> winnings
        """
        if not winners:
            return {}
        
        all_winnings = defaultdict(float)
        
        # Distribute main pot
        if self.main_pot > 0:
            amount_per_winner = self.main_pot / len(winners)
            for winner in winners:
                all_winnings[winner] += amount_per_winner
            self.main_pot = 0
        
        # Distribute side pots
        for side_pot in self.side_pots:
            side_winnings = side_pot.distribute(winners)
            for player, amount in side_winnings.items():
                all_winnings[player] += amount
        
        # Clear the pot
        self.total = 0
        self.side_pots = []
        self.player_contributions.clear()
        self.eligible_players = []
        
        return dict(all_winnings)
    
    def get_pot_odds(self, bet_amount: float) -> float:
        """
        Calculate pot odds for a bet.
        
        Args:
            bet_amount: The amount to call
            
        Returns:
            The pot odds as a decimal
        """
        if bet_amount <= 0:
            return 0.0
        
        return bet_amount / (self.total + bet_amount)
    
    def calculate_rake(self, rate: float = 0.05, cap: float = 25.0) -> float:
        """
        Calculate rake for cash games.
        
        Args:
            rate: Rake percentage (default 5%)
            cap: Maximum rake amount
            
        Returns:
            The rake amount
        """
        rake = self.total * rate
        return min(rake, cap)
    
    def reset(self):
        """Reset the pot for a new hand."""
        self.total = 0.0
        self.main_pot = 0.0
        self.side_pots = []
        self.player_contributions.clear()
        self.eligible_players = []
    
    def __str__(self) -> str:
        """Return string representation of pot."""
        return f"Pot: ${self.total:.2f}"
    
    def __repr__(self) -> str:
        """Return repr representation of pot."""
        return f"Pot(total={self.total}, side_pots={len(self.side_pots)})"
