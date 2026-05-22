"""
Statistics Calculator module for PyHoldem Pro.
Implements poker statistics calculations including pot odds, hand odds, and equity.
"""
import math
import random as _random
from typing import List, Tuple, Dict, Optional
from collections import Counter
from itertools import combinations
from functools import lru_cache
from game.card import Card, Rank, Suit
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
        Calculate the *required equity* to call profitably when we expect to
        extract additional bets on later streets when we hit our draw.

        Definition (pinned):
            required_equity = bet / (pot + bet + future_winnings)

        - `pot_size`: chips already in the pot *before* the current bet.
        - `bet_to_call`: amount the player must put in to continue.
        - `expected_future_bets`: chips we expect to win on future streets *in
          addition to the current pot* on the branch where the draw hits.
          (Does NOT include the current bet.)

        Worked example (textbook):
            pot 100, call 25, future_winnings 50
            -> required equity = 25 / (100 + 25 + 50) = 25 / 175
            -> 0.1429 (~14.3%)

        Compare to raw pot odds without implied:
            25 / (100 + 25) = 0.20 (20%)
        Implied odds lower the required equity threshold to call.
        """
        if bet_to_call <= 0:
            return 0.0
        denominator = float(pot_size) + float(bet_to_call) + float(expected_future_bets)
        if denominator <= 0:
            return 0.0
        return float(bet_to_call) / denominator
    
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


def _full_deck() -> List[Card]:
    return [Card(suit, rank) for suit in Suit for rank in Rank]


class EquityCalculator:
    """Calculator for hand equity against opponents.

    Uses Monte Carlo simulation: deal out the remaining board cards (river
    only / turn + river / full runout from preflop) repeatedly and tally
    showdowns. With 1,000 trials the standard error is ~1.5%, which is
    accurate enough for training feedback without burning CPU.
    """

    DEFAULT_TRIALS = 1000
    EXACT_ENUMERATION_LIMIT = 60000
    MULTIWAY_MIN_TRIALS = 6000

    @staticmethod
    def _card_identity(card: Card) -> str:
        """Stable, process-independent card identity for deterministic seeds."""
        return f"{card.rank.name}:{card.suit.name}"

    @classmethod
    def _seed_for(cls, hole_groups: List[List[Card]], board: List[Card]) -> int:
        parts = []
        for group in hole_groups:
            parts.append(",".join(cls._card_identity(card) for card in group))
        board_part = ",".join(cls._card_identity(card) for card in board)
        payload = "|".join(parts) + f"||{board_part}"
        import hashlib

        return int.from_bytes(hashlib.sha256(payload.encode("utf-8")).digest()[:8], "big")

    @staticmethod
    def _showdown_winners(
        hole_groups: List[List[Card]], board: List[Card]
    ) -> List[int]:
        """Return indices of the player(s) tied for the best 5-card hand."""
        best_hand = None
        best_indices: List[int] = []
        for idx, hole_cards in enumerate(hole_groups):
            all_cards = list(hole_cards) + list(board)
            if len(all_cards) < 5:
                # Defensive: shouldn't happen post-river
                continue
            hand = Hand.best_hand_from_cards(all_cards)
            if best_hand is None or hand > best_hand:
                best_hand = hand
                best_indices = [idx]
            elif hand == best_hand:
                best_indices.append(idx)
        return best_indices

    @classmethod
    def _simulate(
        cls,
        hole_groups: List[List[Card]],
        board: List[Card],
        trials: int,
        rng: Optional[_random.Random] = None,
    ) -> List[float]:
        """Monte Carlo simulate equity for each hole_group given a board.

        Wins count for 1.0, ties split (1/N). Returns equities summing to 1.0.
        """
        if not hole_groups:
            return []
        rng = rng or _random.Random(cls._seed_for(hole_groups, board))
        deck = _full_deck()
        # Remove dead cards (the players' hole cards and known board cards).
        dead = {(c.suit, c.rank) for group in hole_groups for c in group}
        dead.update((c.suit, c.rank) for c in board)
        remaining = [c for c in deck if (c.suit, c.rank) not in dead]

        cards_to_come = 5 - len(board)
        if cards_to_come < 0:
            cards_to_come = 0

        if cards_to_come == 0:
            # River already dealt -> deterministic showdown, no need to loop.
            winners = cls._showdown_winners(hole_groups, board)
            if not winners:
                return [1.0 / len(hole_groups)] * len(hole_groups)
            equities = [0.0] * len(hole_groups)
            for i in winners:
                equities[i] = 1.0 / len(winners)
            return equities

        total_runouts = math.comb(len(remaining), cards_to_come)
        if total_runouts <= cls.EXACT_ENUMERATION_LIMIT:
            equities = [0.0] * len(hole_groups)
            for runout_tuple in combinations(remaining, cards_to_come):
                winners = cls._showdown_winners(hole_groups, board + list(runout_tuple))
                if not winners:
                    continue
                share = 1.0 / len(winners)
                for i in winners:
                    equities[i] += share
            return [e / total_runouts for e in equities]

        sample_count = max(1, int(trials))
        equities = [0.0] * len(hole_groups)
        for _ in range(sample_count):
            runout = rng.sample(remaining, cards_to_come)
            winners = cls._showdown_winners(hole_groups, board + runout)
            if not winners:
                continue
            share = 1.0 / len(winners)
            for i in winners:
                equities[i] += share

        return [e / sample_count for e in equities]

    @classmethod
    def calculate_heads_up_equity(
        cls,
        hand1: List[Card],
        hand2: List[Card],
        board: Optional[List[Card]] = None,
        trials: int = DEFAULT_TRIALS,
        rng: Optional[_random.Random] = None,
    ) -> Tuple[float, float]:
        """Calculate heads-up equity via Monte Carlo.

        Args:
            hand1, hand2: each player's two hole cards.
            board: 0/3/4/5 community cards already on the table.
            trials: number of simulated runouts. Default 1000 -> ~1.5% SE.
            rng: optional Random instance for deterministic results.

        Returns:
            (equity1, equity2) summing to 1.0.
        """
        board = list(board or [])
        if len(hand1) != 2 or len(hand2) != 2:
            return (0.5, 0.5)
        equities = cls._simulate([hand1, hand2], board, trials=trials, rng=rng)
        if not equities:
            return (0.5, 0.5)
        return equities[0], equities[1]

    @classmethod
    def calculate_multiway_equity(
        cls,
        hands: List[List[Card]],
        board: Optional[List[Card]] = None,
        trials: int = DEFAULT_TRIALS,
        rng: Optional[_random.Random] = None,
    ) -> List[float]:
        """Calculate equity for N players via Monte Carlo."""
        if not hands:
            return []
        board = list(board or [])
        if rng is None and len(hands) > 2 and len(board) < 5:
            trials = max(int(trials), cls.MULTIWAY_MIN_TRIALS)
        return cls._simulate(hands, board, trials=trials, rng=rng)
    
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
