"""
Statistics Calculator module for PyHoldem Pro.
Implements poker statistics calculations including pot odds, hand odds, and equity.
"""
import math
from typing import List, Tuple, Dict, Optional
from collections import Counter
from itertools import combinations
from game.card import Card, Rank
from game.hand import Hand, HandRank


class PotOddsCalculator:
    """Calculator for pot odds and related statistics."""
    
    @staticmethod
    def calculate_pot_odds(pot_size: float, bet_to_call: float) -> float:
        """
        Calculate pot odds as a decimal (percentage of total pot needed to call).
        
        Args:
            pot_size: Current pot size
            bet_to_call: Amount needed to call
            
        Returns:
            Pot odds as decimal (0-1)
            
        Raises:
            ValueError: If pot_size or bet_to_call are invalid
        """
        if pot_size < 0:
            raise ValueError("Pot size cannot be negative")
        if bet_to_call <= 0:
            raise ValueError("Bet to call must be positive")
        
        return bet_to_call / (pot_size + bet_to_call)
    
    @staticmethod
    def calculate_pot_odds_percentage(pot_size: float, bet_to_call: float) -> float:
        """
        Calculate pot odds as a percentage.
        
        Args:
            pot_size: Current pot size
            bet_to_call: Amount needed to call
            
        Returns:
            Pot odds as percentage
        """
        decimal_odds = PotOddsCalculator.calculate_pot_odds(pot_size, bet_to_call)
        return decimal_odds * 100
    
    @staticmethod
    def calculate_pot_odds_ratio(pot_size: float, bet_to_call: float) -> Tuple[int, int]:
        """
        Calculate pot odds as a ratio (X:1).
        
        Args:
            pot_size: Current pot size
            bet_to_call: Amount needed to call
            
        Returns:
            Tuple of (pot_multiple, 1) representing X:1 odds
        """
        if bet_to_call <= 0:
            return (0, 1)
        
        ratio = pot_size / bet_to_call
        return (int(round(ratio)), 1)
    
    @staticmethod
    def calculate_implied_odds(pot_size: float, bet_to_call: float, 
                              expected_future_bets: float) -> float:
        """
        Calculate implied odds considering future betting.
        
        Args:
            pot_size: Current pot size
            bet_to_call: Amount needed to call
            expected_future_bets: Expected additional winnings if hand hits
            
        Returns:
            Implied odds as decimal
        """
        effective_pot = pot_size + expected_future_bets
        return PotOddsCalculator.calculate_pot_odds(effective_pot, bet_to_call)
    
    @staticmethod
    def calculate_reverse_implied_odds(pot_size: float, bet_to_call: float,
                                     potential_future_losses: float) -> float:
        """
        Calculate reverse implied odds considering potential future losses.
        
        Args:
            pot_size: Current pot size
            bet_to_call: Amount needed to call
            potential_future_losses: Potential additional losses if hand misses
            
        Returns:
            Reverse implied odds as decimal
        """
        effective_call = bet_to_call + potential_future_losses
        return effective_call / (pot_size + bet_to_call)


class HandOddsCalculator:
    """Calculator for hand improvement odds and probabilities."""
    
    @staticmethod
    def calculate_outs(hole_cards: List[Card], community_cards: List[Card], 
                      draw_type: str) -> int:
        """
        Calculate the number of outs for a specific draw.
        
        Args:
            hole_cards: Player's hole cards
            community_cards: Community cards on board
            draw_type: Type of draw ("flush", "straight", "pair", etc.)
            
        Returns:
            Number of outs
        """
        if not hole_cards or len(hole_cards) != 2:
            return 0
        
        all_cards = hole_cards + community_cards
        seen_cards = set(all_cards)
        
        if draw_type.lower() == "flush":
            return HandOddsCalculator._calculate_flush_outs(hole_cards, community_cards, seen_cards)
        elif draw_type.lower() == "straight":
            return HandOddsCalculator._calculate_straight_outs(hole_cards, community_cards, seen_cards)
        elif draw_type.lower() == "pair":
            return HandOddsCalculator._calculate_pair_outs(hole_cards, community_cards, seen_cards)
        else:
            return 0
    
    @staticmethod
    def _calculate_flush_outs(hole_cards: List[Card], community_cards: List[Card], 
                            seen_cards: set) -> int:
        """Calculate outs for flush draw."""
        suits = Counter(card.suit for card in hole_cards + community_cards)
        
        # Find the suit with most cards
        max_suit, max_count = suits.most_common(1)[0]
        
        if max_count >= 4:
            # Need one more for flush
            # Count how many of this suit we've seen
            seen_of_suit = len([card for card in seen_cards if card.suit == max_suit])
            return 13 - seen_of_suit  # Remaining cards of this suit
        
        return 0
    
    @staticmethod
    def _calculate_straight_outs(hole_cards: List[Card], community_cards: List[Card],
                               seen_cards: set) -> int:
        """Calculate outs for straight draw."""
        all_cards = hole_cards + community_cards
        ranks = sorted([card.rank.value for card in all_cards])
        unique_ranks = sorted(list(set(ranks)))
        
        outs = 0
        
        # Check all possible straights
        for start_rank in range(1, 11):  # A-low to 10-high straights
            straight_ranks = list(range(start_rank, start_rank + 5))
            if start_rank == 1:  # A-low straight
                straight_ranks = [1, 2, 3, 4, 5]  # A,2,3,4,5
            
            # Count how many ranks we have for this straight
            have_ranks = len([r for r in unique_ranks if r in straight_ranks])
            
            if have_ranks >= 4:  # Open-ended or gutshot
                missing_ranks = [r for r in straight_ranks if r not in unique_ranks]
                for rank in missing_ranks:
                    # Count unseen cards of this rank
                    seen_of_rank = len([card for card in seen_cards if card.rank.value == rank])
                    outs += 4 - seen_of_rank
        
        return min(outs, 8)  # Maximum realistic outs for straight
    
    @staticmethod
    def _calculate_pair_outs(hole_cards: List[Card], community_cards: List[Card],
                           seen_cards: set) -> int:
        """Calculate outs to make a pair."""
        hole_ranks = [card.rank for card in hole_cards]
        community_ranks = [card.rank for card in community_cards]
        
        outs = 0
        
        # Outs to pair each hole card
        for rank in hole_ranks:
            if rank not in community_ranks:  # Don't already have pair
                seen_of_rank = len([card for card in seen_cards if card.rank == rank])
                outs += 4 - seen_of_rank
        
        return outs
    
    @staticmethod
    def calculate_hand_probability(outs: int, cards_to_come: int) -> float:
        """
        Calculate probability of hitting hand with given outs.
        
        Args:
            outs: Number of outs
            cards_to_come: Number of cards still to be dealt (1 or 2)
            
        Returns:
            Probability as decimal (0-1)
        """
        if outs <= 0 or cards_to_come <= 0:
            return 0.0
        
        unknown_cards = 52 - (2 + len([]))  # Approximate
        
        if cards_to_come == 1:
            # Simple case: one card to come
            return min(outs / 47, 1.0)  # 47 unknown cards after flop
        elif cards_to_come == 2:
            # Two cards to come (after flop)
            # Probability of NOT hitting on either card
            miss_turn = (47 - outs) / 47
            miss_river = (46 - outs) / 46
            miss_both = miss_turn * miss_river
            return 1.0 - miss_both
        
        return 0.0
    
    @staticmethod
    def rule_of_four_and_two(outs: int, cards_to_come: int) -> float:
        """
        Apply rule of 4 and 2 for quick pot odds approximation.
        
        Args:
            outs: Number of outs
            cards_to_come: Number of cards to come (1 or 2)
            
        Returns:
            Approximate percentage chance
        """
        if cards_to_come == 2:
            return min(outs * 4, 100)  # Rule of 4
        elif cards_to_come == 1:
            return min(outs * 2, 100)  # Rule of 2
        return 0
    
    @staticmethod
    def calculate_hand_strength(hole_cards: List[Card], community_cards: List[Card]) -> float:
        """
        Calculate current hand strength.
        
        Args:
            hole_cards: Player's hole cards
            community_cards: Community cards
            
        Returns:
            Hand strength as decimal (0-1)
        """
        if len(hole_cards) != 2:
            return 0.0
        
        # Handle preflop case
        if len(community_cards) == 0:
            return HandOddsCalculator._calculate_preflop_strength(hole_cards)
        
        if len(community_cards) < 3:
            return 0.0
        
        try:
            all_cards = hole_cards + community_cards
            hand = Hand.best_hand_from_cards(all_cards)
            
            # Map hand rank to base strength, then adjust for high cards
            base_strength_map = {
                HandRank.HIGH_CARD: 0.1,
                HandRank.PAIR: 0.4,
                HandRank.TWO_PAIR: 0.6,
                HandRank.THREE_OF_A_KIND: 0.75,
                HandRank.STRAIGHT: 0.8,
                HandRank.FLUSH: 0.85,
                HandRank.FULL_HOUSE: 0.92,
                HandRank.FOUR_OF_A_KIND: 0.97,
                HandRank.STRAIGHT_FLUSH: 0.99,
                HandRank.ROYAL_FLUSH: 1.0
            }
            
            base_strength = base_strength_map.get(hand.rank, 0.5)
            
            # Adjust for high cards (especially important for pairs)
            if hand.rank == HandRank.PAIR:
                # Higher pairs are much stronger
                if hasattr(hand, 'pair_rank'):
                    pair_value = hand.pair_rank.value
                    high_pair_bonus = (pair_value - 2) / 12 * 0.4  # Aces get big bonus
                    base_strength += high_pair_bonus
            
            return min(base_strength, 1.0)
            
            return strength_map.get(hand.rank, 0.5)
            
        except Exception:
            return 0.0
    
    @staticmethod
    def calculate_hand_potential(hole_cards: List[Card], community_cards: List[Card]) -> float:
        """
        Calculate hand potential for improvement.
        
        Args:
            hole_cards: Player's hole cards
            community_cards: Community cards
            
        Returns:
            Potential for improvement as decimal (0-1)
        """
        if len(hole_cards) != 2:
            return 0.0
        
        potential_score = 0.0
        
        # Check for flush potential
        flush_outs = HandOddsCalculator._calculate_flush_outs(
            hole_cards, community_cards, set(hole_cards + community_cards)
        )
        if flush_outs >= 9:
            potential_score += 0.35
        elif flush_outs >= 4:
            potential_score += 0.15
        
        # Check for straight potential
        straight_outs = HandOddsCalculator._calculate_straight_outs(
            hole_cards, community_cards, set(hole_cards + community_cards)
        )
        if straight_outs >= 8:
            potential_score += 0.35
        elif straight_outs >= 4:
            potential_score += 0.15
        
        # Check for pair potential
        pair_outs = HandOddsCalculator._calculate_pair_outs(
            hole_cards, community_cards, set(hole_cards + community_cards)
        )
        if pair_outs >= 6:
            potential_score += 0.2
        elif pair_outs >= 3:
            potential_score += 0.1
        
        return min(potential_score, 1.0)
    
    @staticmethod
    def _calculate_preflop_strength(hole_cards: List[Card]) -> float:
        """Calculate preflop hand strength."""
        if len(hole_cards) != 2:
            return 0.0
        
        card1, card2 = hole_cards
        
        # Pocket pairs - use more realistic preflop equity
        if card1.rank == card2.rank:
            # AA gets very high equity, other pairs scaled down
            rank_value = card1.rank.value
            if rank_value == 14:  # AA
                return 0.95  # AA is massively favored preflop
            elif rank_value == 13:  # KK  
                return 0.25  # Much lower to create realistic 80-20 equity
            elif rank_value == 12:  # QQ
                return 0.20
            elif rank_value >= 9:   # 99+
                return 0.5 + (rank_value - 9) / 5 * 0.1
            else:
                return 0.3 + (rank_value - 2) / 7 * 0.2
        
        # High cards and suited connectors
        high_value = max(card1.rank.value, card2.rank.value)
        low_value = min(card1.rank.value, card2.rank.value)
        
        # Base strength from high cards
        strength = high_value / 14 * 0.5 + low_value / 14 * 0.2
        
        # Suited bonus
        if card1.suit == card2.suit:
            strength += 0.1
        
        # Connected bonus
        if abs(card1.rank.value - card2.rank.value) <= 2:
            strength += 0.05
        
        return min(strength, 0.8)  # Cap non-pairs below pair strength


class EquityCalculator:
    """Calculator for hand equity against opponents."""
    
    @staticmethod
    def calculate_heads_up_equity(hand1: List[Card], hand2: List[Card],
                                 board: Optional[List[Card]] = None) -> Tuple[float, float]:
        """
        Calculate equity between two hands.
        
        Args:
            hand1: First player's hole cards
            hand2: Second player's hole cards
            board: Community cards (optional)
            
        Returns:
            Tuple of (hand1_equity, hand2_equity)
        """
        if board is None:
            board = []
        
        # For simplicity, use a basic evaluation
        # In a real implementation, this would run Monte Carlo simulations
        
        strength1 = HandOddsCalculator.calculate_hand_strength(hand1, board)
        strength2 = HandOddsCalculator.calculate_hand_strength(hand2, board)
        
        if len(board) >= 5:
            # Post-river: definitive result
            if strength1 > strength2:
                return (1.0, 0.0)
            elif strength2 > strength1:
                return (0.0, 1.0)
            else:
                return (0.5, 0.5)
        else:
            # Pre-river: estimate based on current strength and potential
            if len(board) == 0:
                # Preflop: use strength directly for pocket pairs
                total = strength1 + strength2
                if total > 0:
                    equity1 = strength1 / total
                    equity2 = strength2 / total
                else:
                    equity1 = equity2 = 0.5
            else:
                # Post-flop: include potential
                potential1 = HandOddsCalculator.calculate_hand_potential(hand1, board)
                potential2 = HandOddsCalculator.calculate_hand_potential(hand2, board)
                
                total_strength1 = strength1 + potential1 * 0.5
                total_strength2 = strength2 + potential2 * 0.5
                
                total = total_strength1 + total_strength2
                if total > 0:
                    equity1 = total_strength1 / total
                    equity2 = total_strength2 / total
                else:
                    equity1 = equity2 = 0.5
            
            return (equity1, equity2)
    
    @staticmethod
    def calculate_multiway_equity(hands: List[List[Card]], 
                                board: Optional[List[Card]] = None) -> List[float]:
        """
        Calculate equity for multiple hands.
        
        Args:
            hands: List of hole card pairs
            board: Community cards (optional)
            
        Returns:
            List of equity values for each hand
        """
        if not hands:
            return []
        
        if board is None:
            board = []
        
        # Calculate strength for each hand
        strengths = []
        for hand in hands:
            strength = HandOddsCalculator.calculate_hand_strength(hand, board)
            potential = HandOddsCalculator.calculate_hand_potential(hand, board)
            total_strength = strength + potential * 0.3  # Less impact in multiway
            strengths.append(total_strength)
        
        # Normalize to get equity
        total_strength = sum(strengths)
        if total_strength > 0:
            equities = [s / total_strength for s in strengths]
        else:
            # Equal equity if all hands are equally weak
            equities = [1.0 / len(hands)] * len(hands)
        
        return equities
    
    @staticmethod
    def calculate_tournament_icm_equity(stacks: List[float], payouts: List[float]) -> List[float]:
        """
        Calculate Independent Chip Model (ICM) equity for tournament play.
        
        Args:
            stacks: List of chip stacks for each player
            payouts: List of payout amounts for each finishing position
            
        Returns:
            List of ICM equity values for each player
        """
        if len(stacks) != len(payouts) or not stacks:
            return []
        
        total_chips = sum(stacks)
        if total_chips == 0:
            return [0.0] * len(stacks)
        
        # Simplified ICM calculation
        # In a real implementation, this would use complex combinatorics
        equities = []
        for stack in stacks:
            chip_percentage = stack / total_chips
            
            # Weight payouts by probability based on stack size
            expected_payout = 0.0
            for i, payout in enumerate(payouts):
                # Higher stack = higher probability of better finish
                position_prob = chip_percentage * (len(payouts) - i) / len(payouts)
                expected_payout += payout * position_prob
            
            equities.append(expected_payout)
        
        return equities
