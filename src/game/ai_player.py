"""
AI Player module for PyHoldem Pro.
Implements different AI playing styles and decision-making logic.
"""
import random
from enum import Enum
from typing import Tuple, Dict, List, Optional
from game.player import Player, PlayerAction
from game.card import Card, Rank
from game.hand import Hand


def _round_to_nearest_5(amount):
    return int(round(amount / 5)) * 5


class AIStyle(Enum):
    """Enumeration for AI playing styles."""
    CAUTIOUS = "cautious"
    WILD = "wild"
    BALANCED = "balanced"
    RANDOM = "random"


class AIPlayer(Player):
    """Base class for AI players."""
    
    def __init__(self, name: str, bankroll: int, ai_style: AIStyle):
        """
        Initialize an AI player.
        
        Args:
            name: Player name
            bankroll: Starting bankroll
            ai_style: The AI's playing style
        """
        super().__init__(name, int(bankroll))
        self.ai_style = ai_style
        self.is_ai = True
    
    def make_decision(self, game_state: Dict) -> Tuple[PlayerAction, float]:
        """
        Make a decision based on game state.
        
        Args:
            game_state: Current game information
            
        Returns:
            Tuple of (action, amount)
            
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("AI subclasses must implement make_decision")
    
    def __str__(self) -> str:
        """Return string representation including AI style."""
        base_str = super().__str__()
        return f"{base_str} [AI: {self.ai_style.name}]"


class CautiousAI(AIPlayer):
    """Cautious/tight AI player implementation."""
    
    def __init__(self, name: str, bankroll: int):
        """Initialize a cautious AI player."""
        super().__init__(name, bankroll, AIStyle.CAUTIOUS)
        self.fold_threshold = 0.35  # Fold 35% of the time with marginal hands
        self.raise_threshold = 0.85  # Only raise with top 15% of hands
    
    def make_decision(self, game_state: Dict) -> Tuple[PlayerAction, float]:
        """
        Make a cautious decision based on game state.
        
        Cautious players:
        - Fold often with weak hands
        - Rarely bluff
        - Only raise with strong hands
        - Consider position heavily
        """
        pot_size = game_state.get('pot_size', 0)
        current_bet = game_state.get('current_bet', 0)
        min_raise = game_state.get('min_raise', 0)
        players_in_hand = game_state.get('players_in_hand', 2)
        community_cards = game_state.get('community_cards', [])
        betting_round = game_state.get('betting_round', 'preflop')
        
        # Evaluate hand strength
        hand_strength = self._evaluate_hand_strength(community_cards)
        
        # Position adjustment (late position is stronger)
        position_bonus = 0.05 * (self.position / 9)  # 0-5% bonus for position
        adjusted_strength = hand_strength + position_bonus

        # All-in with very strong hand
        if adjusted_strength > 0.95 and self.bankroll > 0:
            return PlayerAction.ALL_IN, self.bankroll
        
        # Cautious preflop play
        if betting_round == 'preflop':
            if adjusted_strength < 0.4:
                return PlayerAction.FOLD, 0
            elif adjusted_strength < 0.7:
                if current_bet <= self.bankroll * 0.05:  # Call small bets
                    return PlayerAction.CALL, current_bet
                else:
                    return PlayerAction.FOLD, 0
            else:
                # Strong hand
                if random.random() < 0.3:  # Occasionally raise with strong hands
                    raise_amount = min(current_bet + min_raise, self.bankroll * 0.1)
                    raise_amount = _round_to_nearest_5(raise_amount)
                    if raise_amount > current_bet:
                        return PlayerAction.RAISE, raise_amount
                return PlayerAction.CALL, current_bet
        
        # Post-flop play
        else:
            # Check if we can check
            if current_bet == 0:
                if adjusted_strength > 0.6:
                    # Sometimes bet with good hands
                    if random.random() < 0.4:
                        bet_amount = min(pot_size * 0.3, self.bankroll * 0.05)
                        if bet_amount == 0 and pot_size == 0:
                            bet_amount = game_state.get('big_blind', 10)
                        
                        bet_amount = _round_to_nearest_5(bet_amount)
                        if bet_amount > 0:
                            return PlayerAction.RAISE, bet_amount
                return PlayerAction.CHECK, 0
            
            # Facing a bet
            pot_odds = current_bet / (pot_size + current_bet) if (pot_size + current_bet) > 0 else 0
            
            if adjusted_strength < pot_odds:
                return PlayerAction.FOLD, 0
            elif adjusted_strength > 0.8:
                # Very strong hand, consider raising
                if random.random() < 0.25:
                    raise_amount = min(current_bet + min_raise, self.bankroll * 0.1)
                    raise_amount = _round_to_nearest_5(raise_amount)
                    if raise_amount > current_bet:
                        return PlayerAction.RAISE, raise_amount
            
            return PlayerAction.CALL, current_bet
    
    def _evaluate_hand_strength(self, community_cards: List[Card]) -> float:
        """
        Evaluate hand strength (0-1 scale).
        
        Args:
            community_cards: Community cards on the table
            
        Returns:
            Strength value between 0 and 1
        """
        if not self.hole_cards:
            return 0.5
        
        # Preflop hand strength based on hole cards
        if not community_cards:
            return self._evaluate_preflop_strength()
        
        # Post-flop: evaluate actual hand
        all_cards = self.hole_cards + community_cards
        if len(all_cards) >= 5:
            hand = Hand.best_hand_from_cards(all_cards)
            # Map hand rank to strength (simplified)
            rank_strength = {
                1: 0.1,   # High card
                2: 0.3,   # Pair
                3: 0.45,  # Two pair
                4: 0.6,   # Three of a kind
                5: 0.7,   # Straight
                6: 0.75,  # Flush
                7: 0.85,  # Full house
                8: 0.95,  # Four of a kind
                9: 0.98,  # Straight flush
                10: 1.0   # Royal flush
            }
            return rank_strength.get(hand.rank.value, 0.5)
        
        return 0.5
    
    def _evaluate_preflop_strength(self) -> float:
        """Evaluate preflop hand strength based on hole cards."""
        if len(self.hole_cards) != 2:
            return 0.5
        
        card1, card2 = self.hole_cards
        
        # Pocket pairs
        if card1.rank == card2.rank:
            # Higher pairs are stronger
            return 0.6 + (card1.rank.value / 14) * 0.3
        
        # Suited cards
        suited = card1.suit == card2.suit
        suited_bonus = 0.05 if suited else 0
        
        # High cards
        high_card_value = max(card1.rank.value, card2.rank.value) / 14
        low_card_value = min(card1.rank.value, card2.rank.value) / 14
        
        # Connected cards (for straight potential)
        gap = abs(card1.rank.value - card2.rank.value)
        connected_bonus = 0.05 if gap == 1 else 0.03 if gap == 2 else 0
        
        # Calculate overall strength
        strength = (high_card_value * 0.6 + low_card_value * 0.2 + 
                   suited_bonus + connected_bonus)
        
        return min(strength, 1.0)


class WildAI(AIPlayer):
    """Wild/aggressive AI player implementation."""
    
    def __init__(self, name: str, bankroll: int):
        """Initialize a wild AI player."""
        super().__init__(name, bankroll, AIStyle.WILD)
        self.bluff_frequency = 0.25  # Bluff 25% of the time
        self.aggression_factor = 2.0  # Bet/raise twice as often as call
    
    def make_decision(self, game_state: Dict) -> Tuple[PlayerAction, float]:
        """
        Make an aggressive decision based on game state.
        
        Wild players:
        - Bluff frequently
        - Raise aggressively
        - Rarely fold with any potential
        - Try to intimidate opponents
        """
        pot_size = game_state.get('pot_size', 0)
        current_bet = game_state.get('current_bet', 0)
        min_raise = game_state.get('min_raise', 0)
        players_in_hand = game_state.get('players_in_hand', 2)
        
        # Wild players are less concerned with hand strength
        aggression_roll = random.random()

        # Chance to go all-in
        if aggression_roll < 0.05 and self.bankroll > 0: # 5% chance to just shove it all in
            return PlayerAction.ALL_IN, self.bankroll
        
        # Check if we can be aggressive
        if current_bet == 0:
            # No bet to face - bet/raise aggressively
            if aggression_roll < 0.6:  # 60% of the time, bet
                bet_amount = min(pot_size * random.uniform(0.5, 1.2), self.bankroll * 0.2)
                if bet_amount == 0 and pot_size == 0:
                    bet_amount = game_state.get('big_blind', 10)
                
                bet_amount = _round_to_nearest_5(bet_amount)
                if bet_amount > 0:
                    return PlayerAction.RAISE, bet_amount
            return PlayerAction.CHECK, 0
        
        # Facing a bet
        if aggression_roll < 0.3:  # 30% raise/re-raise
            raise_amount = min(current_bet * random.uniform(2, 3), self.bankroll * 0.3)
            raise_amount = _round_to_nearest_5(raise_amount)
            if raise_amount > current_bet + min_raise:
                return PlayerAction.RAISE, raise_amount
        
        if aggression_roll < 0.7:  # 40% call (total 70%)
            return PlayerAction.CALL, current_bet
        
        # Only fold 30% of the time with terrible hands
        if self._has_any_potential():
            return PlayerAction.CALL, current_bet
        
        return PlayerAction.FOLD, 0
    
    def _has_any_potential(self) -> bool:
        """Check if hand has any potential (wild players see potential everywhere)."""
        if not self.hole_cards:
            return False
        
        # Wild players think any face card or pair has potential
        for card in self.hole_cards:
            if card.rank.value >= 11:  # J, Q, K, A
                return True
        
        # Or if cards are suited/connected
        if len(self.hole_cards) == 2:
            if self.hole_cards[0].suit == self.hole_cards[1].suit:
                return True
            if abs(self.hole_cards[0].rank.value - self.hole_cards[1].rank.value) <= 3:
                return True
        
        return random.random() < 0.4  # 40% chance to play anyway


class BalancedAI(AIPlayer):
    """Balanced/mathematical AI player implementation."""
    
    def __init__(self, name: str, bankroll: int):
        """Initialize a balanced AI player."""
        super().__init__(name, bankroll, AIStyle.BALANCED)
        self.pot_odds_threshold = 0.0
        self.equity_calculator = None  # Would implement equity calculation
    
    def make_decision(self, game_state: Dict) -> Tuple[PlayerAction, float]:
        """
        Make a balanced decision based on game state and mathematics.
        
        Balanced players:
        - Use pot odds and equity calculations
        - Mix aggression with caution
        - Adapt to opponents
        - Play position well
        """
        pot_size = game_state.get('pot_size', 0)
        current_bet = game_state.get('current_bet', 0)
        min_raise = game_state.get('min_raise', 0)
        call_amount = game_state.get('call_amount', current_bet)
        
        # Calculate pot odds
        pot_odds = self.calculate_pot_odds(game_state)
        
        # Estimate hand equity (simplified)
        hand_equity = self._estimate_equity(game_state)
        
        # Position factor
        position_factor = self.position / 9

        # Consider all-in with very high equity
        if hand_equity > 0.9 and pot_odds < 0.5 and self.bankroll > 0:
            return PlayerAction.ALL_IN, self.bankroll
        
        # Decision based on pot odds vs equity
        if current_bet == 0:
            # Can check or bet
            if hand_equity > 0.6:
                # Good hand, value bet
                bet_size = pot_size * (0.5 + hand_equity * 0.5)
                if bet_size == 0 and pot_size == 0:
                    bet_size = game_state.get('big_blind', 10)
                
                bet_size = _round_to_nearest_5(min(bet_size, self.bankroll * 0.15))
                if bet_size > 0:
                    return PlayerAction.RAISE, bet_size
            elif hand_equity > 0.4 and position_factor > 0.6:
                # Decent hand in position, sometimes bet
                if random.random() < 0.3:
                    bet_size = pot_size * 0.3
                    if bet_size == 0 and pot_size == 0:
                        bet_size = game_state.get('big_blind', 10)
                    
                    bet_size = _round_to_nearest_5(min(bet_size, self.bankroll * 0.1))
                    if bet_size > 0:
                        return PlayerAction.RAISE, bet_size
            return PlayerAction.CHECK, 0
        
        # Facing a bet - compare pot odds to equity
        if hand_equity > pot_odds + 0.1:
            # Strong equity advantage, consider raising
            if random.random() < hand_equity * 0.5:
                raise_amount = current_bet + min_raise * (1 + hand_equity)
                raise_amount = _round_to_nearest_5(min(raise_amount, self.bankroll * 0.2))
                if raise_amount > current_bet:
                    return PlayerAction.RAISE, raise_amount
            return PlayerAction.CALL, current_bet
        elif hand_equity > pot_odds - 0.05:
            # Close decision, usually call
            return PlayerAction.CALL, current_bet
        else:
            # Poor pot odds
            return PlayerAction.FOLD, 0
    
    def calculate_pot_odds(self, game_state: Dict) -> float:
        """Calculate pot odds for current decision."""
        pot_size = game_state.get('pot_size', 0)
        call_amount = game_state.get('call_amount', game_state.get('current_bet', 0))
        
        if call_amount == 0:
            return 0.0
        
        return call_amount / (pot_size + call_amount)
    
    def _estimate_equity(self, game_state: Dict) -> float:
        """
        Estimate hand equity (simplified version).
        
        In a real implementation, this would run Monte Carlo simulations.
        """
        community_cards = game_state.get('community_cards', [])
        players_in_hand = game_state.get('players_in_hand', 2)
        
        if not self.hole_cards:
            return 0.5
        
        # Simplified equity based on hand strength
        base_strength = self._evaluate_hand_strength(community_cards)
        
        # Adjust for number of opponents
        adjusted_equity = base_strength ** (players_in_hand - 1)
        
        return adjusted_equity
    
    def _evaluate_hand_strength(self, community_cards: List[Card]) -> float:
        """Evaluate hand strength for equity calculation."""
        if not community_cards:
            # Preflop - use starting hand strength
            return self._preflop_hand_strength()
        
        # Post-flop - evaluate made hand
        all_cards = self.hole_cards + community_cards
        if len(all_cards) >= 5:
            hand = Hand.best_hand_from_cards(all_cards)
            # Convert hand rank to equity estimate - better mapping
            rank_to_strength = {
                1: 0.15,  # High card
                2: 0.40,  # Pair
                3: 0.55,  # Two pair
                4: 0.70,  # Three of a kind
                5: 0.75,  # Straight
                6: 0.80,  # Flush
                7: 0.88,  # Full house
                8: 0.95,  # Four of a kind
                9: 0.98,  # Straight flush
                10: 1.0   # Royal flush
            }
            return rank_to_strength.get(hand.rank.value, 0.5)
        
        return 0.5
    
    def _preflop_hand_strength(self) -> float:
        """Calculate preflop hand strength."""
        if len(self.hole_cards) != 2:
            return 0.5
        
        card1, card2 = self.hole_cards
        
        # Pocket pairs
        if card1.rank == card2.rank:
            return 0.5 + card1.rank.value * 0.03
        
        # High cards
        high_value = max(card1.rank.value, card2.rank.value)
        low_value = min(card1.rank.value, card2.rank.value)
        
        # Suited bonus
        suited = 0.1 if card1.suit == card2.suit else 0
        
        # Connected bonus
        gap = abs(card1.rank.value - card2.rank.value)
        connected = 0.05 if gap <= 2 else 0
        
        return (high_value * 0.04 + low_value * 0.02 + suited + connected)


class RandomAI(AIPlayer):
    """Random/unpredictable AI player implementation."""
    
    def __init__(self, name: str, bankroll: int):
        """Initialize a random AI player."""
        super().__init__(name, bankroll, AIStyle.RANDOM)
        self.randomness_factor = 0.8  # 80% random decisions
    
    def make_decision(self, game_state: Dict) -> Tuple[PlayerAction, float]:
        """
        Make a random decision with minimal logic.
        
        Random players:
        - Make unpredictable decisions
        - Simulate beginners who don't know strategy
        - Sometimes make brilliant plays by accident
        - Sometimes make terrible plays
        """
        current_bet = game_state.get('current_bet', 0)
        pot_size = game_state.get('pot_size', 0)
        min_raise = game_state.get('min_raise', 0)
        
        # Random decision
        decision_roll = random.random()

        # Chance to go all-in
        if decision_roll < 0.02 and self.bankroll > 0: # 2% chance to just shove it all in
            return PlayerAction.ALL_IN, self.bankroll
        
        if current_bet == 0:
            # Can check or bet
            if decision_roll < 0.6:
                return PlayerAction.CHECK, 0
            else:
                # Random bet size
                bet_size = random.uniform(0.1, 0.5) * pot_size if pot_size > 0 else 10
                bet_size = _round_to_nearest_5(min(bet_size, self.bankroll * 0.2))
                return PlayerAction.RAISE, bet_size
        else:
            # Facing a bet
            if decision_roll < 0.25:
                return PlayerAction.FOLD, 0
            elif decision_roll < 0.6:
                return PlayerAction.CALL, current_bet
            else:
                # Random raise
                raise_multiplier = random.uniform(1.5, 3)
                raise_amount = current_bet * raise_multiplier
                raise_amount = _round_to_nearest_5(min(raise_amount, self.bankroll * 0.3))
                if raise_amount > current_bet + min_raise:
                    return PlayerAction.RAISE, raise_amount
                return PlayerAction.CALL, current_bet


def create_ai_player(name: str, bankroll: int, style: AIStyle) -> AIPlayer:
    """
    Factory function to create AI players.
    
    Args:
        name: Player name
        bankroll: Starting bankroll
        style: AI playing style
        
    Returns:
        AI player instance
    """
    if style == AIStyle.CAUTIOUS:
        return CautiousAI(name, bankroll)
    elif style == AIStyle.WILD:
        return WildAI(name, bankroll)
    elif style == AIStyle.BALANCED:
        return BalancedAI(name, bankroll)
    elif style == AIStyle.RANDOM:
        return RandomAI(name, bankroll)
    else:
        raise ValueError(f"Unknown AI style: {style}")


def create_ai_players_for_table(count: int, bankroll: int) -> List[AIPlayer]:
    """
    Create multiple AI players with mixed styles.
    
    Args:
        count: Number of AI players to create
        bankroll: Starting bankroll for each player
        
    Returns:
        List of AI players
    """
    ai_players = []
    styles = list(AIStyle)
    
    for i in range(count):
        # Mix of styles with some randomness
        if i < len(styles):
            style = styles[i]
        else:
            style = random.choice(styles)
        
        name = f"AI_{style.value.capitalize()}_{i+1}"
        ai_player = create_ai_player(name, bankroll, style)
        ai_players.append(ai_player)
    
    # Shuffle to randomize seating
    random.shuffle(ai_players)
    
    return ai_players
