"""
Pot module for PyHoldem Pro.
Implements pot management including side pots.
"""
from typing import List, Dict, Optional
from collections import defaultdict
from game.player import Player


class SidePot:
    """Represents a side pot in a poker game."""
    
    def __init__(self, amount: int, eligible_players: List[Player]):
        """
        Initialize a side pot.
        
        Args:
            amount: The pot amount
            eligible_players: Players eligible to win this pot
        """
        self.amount = amount
        self.eligible_players = eligible_players.copy()
    
    def distribute(self, winners: List[Player]) -> Dict[Player, int]:
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
        num_winners = len(eligible_winners)
        amount_per_winner = self.amount // num_winners
        remainder = self.amount % num_winners
        
        winnings = {winner: amount_per_winner for winner in eligible_winners}
        
        # Distribute remainder
        for i in range(remainder):
            winnings[eligible_winners[i]] += 1
        
        return winnings
    
    def __str__(self) -> str:
        """Return string representation of side pot."""
        return f"SidePot: ${self.amount:.0f} ({len(self.eligible_players)} players eligible)"


class Pot:
    """Manages the main pot and side pots in a poker game."""
    
    def __init__(self):
        """Initialize an empty pot."""
        self.total = 0
        self.main_pot = 0
        self.side_pots: List[SidePot] = []
        self.player_contributions: Dict[Player, int] = defaultdict(int)
        self.eligible_players: List[Player] = []
    
    def add_bet(self, player: Player, amount: int):
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
    
    def get_player_contribution(self, player: Player) -> int:
        """
        Get a player's total contribution to the pot.
        
        Args:
            player: The player to check
            
        Returns:
            The player's total contribution
        """
        return self.player_contributions.get(player, 0)
    
    def create_side_pots(self):
        """Create side pots when players are all-in for different amounts."""
        if not self.player_contributions:
            return
        
        # Reset side pots
        self.side_pots = []

        # Build sorted unique contribution levels (ascending)
        levels = sorted(set(self.player_contributions.values()))

        # We'll compute pots by taking the delta between contribution levels
        last_level = 0
        main_pot = 0
        side_pots: List[SidePot] = []

        for level in levels:
            # Players who have contributed at least this level
            eligible = [p for p, amt in self.player_contributions.items() if amt >= level]
            if not eligible:
                continue

            delta = level - last_level
            pot_amount = delta * len(eligible)

            if last_level == 0:
                # first chunk is main pot
                main_pot = pot_amount
            else:
                side_pots.append(SidePot(pot_amount, eligible))

            last_level = level

        self.main_pot = main_pot
        self.side_pots = side_pots

        # Recalculate total
        self.total = int(self.main_pot + sum(sp.amount for sp in self.side_pots))
    
    def distribute(self, winners: List[Player]) -> Dict[Player, int]:
        """
        Distribute the pot to winners.
        
        Args:
            winners: List of winning players
            
        Returns:
            Dictionary of player -> winnings
        """
        if not winners:
            return {}
        
        all_winnings = defaultdict(int)

        # Distribute main pot: winners eligible for main pot split it
        eligible_main_winners = [w for w in winners if w in self.eligible_players]
        if self.main_pot > 0 and eligible_main_winners:
            num_winners = len(eligible_main_winners)
            amount_per = self.main_pot // num_winners
            remainder = self.main_pot % num_winners
            for i, w in enumerate(eligible_main_winners):
                win_amount = amount_per + (1 if i < remainder else 0)
                all_winnings[w] += win_amount
            self.main_pot = 0

        # Distribute each side pot separately considering eligible players
        for side_pot in self.side_pots:
            # Find winners eligible for this side pot
            eligible = [w for w in winners if w in side_pot.eligible_players]
            if not eligible:
                continue
            num_winners = len(eligible)
            amount_per = side_pot.amount // num_winners
            remainder = side_pot.amount % num_winners
            for i, w in enumerate(eligible):
                win_amount = amount_per + (1 if i < remainder else 0)
                all_winnings[w] += win_amount

        # Clear the pot
        self.total = 0
        self.side_pots = []
        self.player_contributions.clear()
        self.eligible_players = []

        return dict(all_winnings)

    def distribute_to_winners(self, player_best_hands: Dict[Player, object]) -> Dict[Player, int]:
        """
        Distribute main pot and side pots to winners determined per-pot using
        the provided best-hand objects for each player.

        Args:
            player_best_hands: Mapping of Player -> Hand (best 5-card hand)

        Returns:
            Dictionary mapping Player -> winnings amount
        """
        if not player_best_hands:
            return {}

        all_winnings = defaultdict(int)

        # Distribute main pot
        main_eligible = [p for p in self.eligible_players if p in player_best_hands]
        if self.main_pot > 0 and main_eligible:
            # Determine best hand among eligible players
            best_hand = None
            best_players = []
            for p in main_eligible:
                ph = player_best_hands[p]
                if best_hand is None or ph > best_hand:
                    best_hand = ph
                    best_players = [p]
                elif ph == best_hand:
                    best_players.append(p)

            num_winners = len(best_players)
            amount_per = self.main_pot // num_winners
            remainder = self.main_pot % num_winners
            for i, w in enumerate(best_players):
                win_amount = amount_per + (1 if i < remainder else 0)
                all_winnings[w] += win_amount
            self.main_pot = 0

        # Distribute side pots
        for side_pot in self.side_pots:
            eligible = [p for p in side_pot.eligible_players if p in player_best_hands]
            if not eligible:
                continue

            best_hand = None
            best_players = []
            for p in eligible:
                ph = player_best_hands[p]
                if best_hand is None or ph > best_hand:
                    best_hand = ph
                    best_players = [p]
                elif ph == best_hand:
                    best_players.append(p)

            num_winners = len(best_players)
            amount_per = side_pot.amount // num_winners
            remainder = side_pot.amount % num_winners
            for i, w in enumerate(best_players):
                win_amount = amount_per + (1 if i < remainder else 0)
                all_winnings[w] += win_amount

        # Clear the pot
        self.total = 0
        self.side_pots = []
        self.player_contributions.clear()
        self.eligible_players = []

        return dict(all_winnings)
    
    def get_pot_odds(self, bet_amount: int) -> float:
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
    
    def calculate_rake(self, rate: float = 0.05, cap: int = 25) -> int:
        """
        Calculate rake for cash games.
        
        Args:
            rate: Rake percentage (default 5%)
            cap: Maximum rake amount
            
        Returns:
            The rake amount
        """
        rake = self.total * rate
        return min(int(rake), cap)
    
    def reset(self):
        """Reset the pot for a new hand."""
        self.total = 0
        self.main_pot = 0
        self.side_pots = []
        self.player_contributions.clear()
        self.eligible_players = []
    
    def __str__(self) -> str:
        """Return string representation of pot."""
        return f"Pot: ${self.total:.0f}"
    
    def __repr__(self) -> str:
        """Return repr representation of pot."""
        return f"Pot(total={self.total}, side_pots={len(self.side_pots)})"
