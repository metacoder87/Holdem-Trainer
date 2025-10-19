"""
Hand module for PyHoldem Pro.
Implements hand evaluation and ranking logic for poker hands.
"""
from enum import Enum
from typing import List, Tuple, Optional
from collections import Counter
from itertools import combinations
from src.game.card import Card, Rank


class HandRank(Enum):
    """Enumeration for poker hand rankings."""
    HIGH_CARD = 1
    PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10
    
    def __lt__(self, other):
        """Compare hand ranks."""
        if not isinstance(other, HandRank):
            return NotImplemented
        return self.value < other.value
    
    def __str__(self):
        """Return readable hand rank name."""
        return self.name.replace('_', ' ').title()


class Hand:
    """Represents a 5-card poker hand."""
    
    def __init__(self, cards: List[Card]):
        """
        Initialize a poker hand.
        
        Args:
            cards: List of exactly 5 cards
            
        Raises:
            ValueError: If not exactly 5 cards provided
        """
        if len(cards) != 5:
            raise ValueError(f"Hand must contain exactly 5 cards, got {len(cards)}")
        
        self.cards = sorted(cards, key=lambda c: c.value, reverse=True)
        self._rank = None
        self._high_card = None
        self._kickers = []
        self._evaluate()
    
    def _evaluate(self):
        """Evaluate the hand and determine its rank."""
        # Get rank and suit frequencies
        rank_counts = Counter(card.rank for card in self.cards)
        suit_counts = Counter(card.suit for card in self.cards)
        
        # Check for flush
        is_flush = len(suit_counts) == 1
        
        # Check for straight
        is_straight, straight_high = self._check_straight()
        
        # Get rank groups
        rank_freq = sorted(rank_counts.values(), reverse=True)
        unique_ranks = sorted(rank_counts.keys(), key=lambda r: r.value, reverse=True)
        
        # Determine hand rank
        if is_straight and is_flush:
            if straight_high.value == 14:  # Ace high straight
                self._rank = HandRank.ROYAL_FLUSH
            else:
                self._rank = HandRank.STRAIGHT_FLUSH
            self._high_card = straight_high
            
        elif rank_freq == [4, 1]:
            self._rank = HandRank.FOUR_OF_A_KIND
            self._set_kickers_for_n_of_kind(rank_counts, 4)
            
        elif rank_freq == [3, 2]:
            self._rank = HandRank.FULL_HOUSE
            self._set_full_house_ranks(rank_counts)
            
        elif is_flush:
            self._rank = HandRank.FLUSH
            self._high_card = self.cards[0]
            self._kickers = self.cards[1:]
            
        elif is_straight:
            self._rank = HandRank.STRAIGHT
            self._high_card = straight_high
            
        elif rank_freq == [3, 1, 1]:
            self._rank = HandRank.THREE_OF_A_KIND
            self._set_kickers_for_n_of_kind(rank_counts, 3)
            
        elif rank_freq == [2, 2, 1]:
            self._rank = HandRank.TWO_PAIR
            self._set_two_pair_ranks(rank_counts)
            
        elif rank_freq == [2, 1, 1, 1]:
            self._rank = HandRank.PAIR
            self._set_kickers_for_n_of_kind(rank_counts, 2)
            
        else:
            self._rank = HandRank.HIGH_CARD
            self._high_card = self.cards[0]
            self._kickers = self.cards
    
    def _check_straight(self) -> Tuple[bool, Optional[Card]]:
        """
        Check if hand is a straight.
        
        Returns:
            Tuple of (is_straight, high_card)
        """
        values = [card.value for card in self.cards]
        
        # Check regular straight
        if values == list(range(values[0], values[0] - 5, -1)):
            return True, self.cards[0]
        
        # Check for ace-low straight (A-2-3-4-5)
        if set(values) == {14, 5, 4, 3, 2}:
            # In ace-low straight, 5 is the high card
            return True, next(card for card in self.cards if card.rank == Rank.FIVE)
        
        return False, None
    
    def _set_kickers_for_n_of_kind(self, rank_counts: Counter, n: int):
        """Set kickers for n-of-a-kind hands."""
        for rank, count in rank_counts.items():
            if count == n:
                if n == 4:
                    self.four_of_a_kind_rank = rank
                elif n == 3:
                    self.three_of_a_kind_rank = rank
                elif n == 2:
                    self.pair_rank = rank
                
                # Set kickers as cards not part of the n-of-a-kind
                self._kickers = [card for card in self.cards if card.rank != rank]
                self._high_card = next(card for card in self.cards if card.rank == rank)
                break
    
    def _set_two_pair_ranks(self, rank_counts: Counter):
        """Set ranks for two pair hands."""
        pairs = []
        kicker = None
        
        for rank, count in rank_counts.items():
            if count == 2:
                pairs.append(rank)
            elif count == 1:
                kicker = rank
        
        pairs.sort(key=lambda r: r.value, reverse=True)
        self.high_pair_rank = pairs[0]
        self.low_pair_rank = pairs[1]
        self._high_card = next(card for card in self.cards if card.rank == self.high_pair_rank)
        self._kickers = [card for card in self.cards if card.rank == kicker]
    
    def _set_full_house_ranks(self, rank_counts: Counter):
        """Set ranks for full house."""
        for rank, count in rank_counts.items():
            if count == 3:
                self.three_of_a_kind_rank = rank
                self._high_card = next(card for card in self.cards if card.rank == rank)
            elif count == 2:
                self.pair_rank = rank
    
    @property
    def rank(self) -> HandRank:
        """Get the hand rank."""
        return self._rank
    
    @property
    def high_card(self) -> Card:
        """Get the highest card in the hand."""
        return self._high_card
    
    @property
    def kickers(self) -> List[Card]:
        """Get kicker cards for tie-breaking."""
        return self._kickers
    
    def __eq__(self, other):
        """Check if two hands are equal."""
        if not isinstance(other, Hand):
            return NotImplemented
        
        if self.rank != other.rank:
            return False
        
        # Compare based on hand rank
        if self.rank == HandRank.STRAIGHT_FLUSH or self.rank == HandRank.STRAIGHT:
            return self.high_card.value == other.high_card.value
        
        elif self.rank == HandRank.FOUR_OF_A_KIND:
            if self.four_of_a_kind_rank != other.four_of_a_kind_rank:
                return False
            return self.kickers[0].value == other.kickers[0].value
        
        elif self.rank == HandRank.FULL_HOUSE:
            return (self.three_of_a_kind_rank == other.three_of_a_kind_rank and
                    self.pair_rank == other.pair_rank)
        
        elif self.rank == HandRank.FLUSH or self.rank == HandRank.HIGH_CARD:
            for c1, c2 in zip(self.cards, other.cards):
                if c1.value != c2.value:
                    return False
            return True
        
        elif self.rank == HandRank.THREE_OF_A_KIND:
            if self.three_of_a_kind_rank != other.three_of_a_kind_rank:
                return False
            return all(k1.value == k2.value for k1, k2 in zip(self.kickers, other.kickers))
        
        elif self.rank == HandRank.TWO_PAIR:
            if self.high_pair_rank != other.high_pair_rank:
                return False
            if self.low_pair_rank != other.low_pair_rank:
                return False
            return self.kickers[0].value == other.kickers[0].value
        
        elif self.rank == HandRank.PAIR:
            if self.pair_rank != other.pair_rank:
                return False
            return all(k1.value == k2.value for k1, k2 in zip(self.kickers, other.kickers))
        
        return True
    
    def __lt__(self, other):
        """Compare hands for ordering."""
        if not isinstance(other, Hand):
            return NotImplemented
        
        if self.rank != other.rank:
            return self.rank < other.rank
        
        # Compare based on hand rank specifics
        if self.rank == HandRank.STRAIGHT_FLUSH or self.rank == HandRank.STRAIGHT:
            return self.high_card.value < other.high_card.value
        
        elif self.rank == HandRank.FOUR_OF_A_KIND:
            if self.four_of_a_kind_rank != other.four_of_a_kind_rank:
                return self.four_of_a_kind_rank.value < other.four_of_a_kind_rank.value
            return self.kickers[0].value < other.kickers[0].value
        
        elif self.rank == HandRank.FULL_HOUSE:
            if self.three_of_a_kind_rank != other.three_of_a_kind_rank:
                return self.three_of_a_kind_rank.value < other.three_of_a_kind_rank.value
            return self.pair_rank.value < other.pair_rank.value
        
        elif self.rank == HandRank.FLUSH or self.rank == HandRank.HIGH_CARD:
            for c1, c2 in zip(self.cards, other.cards):
                if c1.value != c2.value:
                    return c1.value < c2.value
            return False
        
        elif self.rank == HandRank.THREE_OF_A_KIND:
            if self.three_of_a_kind_rank != other.three_of_a_kind_rank:
                return self.three_of_a_kind_rank.value < other.three_of_a_kind_rank.value
            for k1, k2 in zip(self.kickers, other.kickers):
                if k1.value != k2.value:
                    return k1.value < k2.value
            return False
        
        elif self.rank == HandRank.TWO_PAIR:
            if self.high_pair_rank != other.high_pair_rank:
                return self.high_pair_rank.value < other.high_pair_rank.value
            if self.low_pair_rank != other.low_pair_rank:
                return self.low_pair_rank.value < other.low_pair_rank.value
            return self.kickers[0].value < other.kickers[0].value
        
        elif self.rank == HandRank.PAIR:
            if self.pair_rank != other.pair_rank:
                return self.pair_rank.value < other.pair_rank.value
            for k1, k2 in zip(self.kickers, other.kickers):
                if k1.value != k2.value:
                    return k1.value < k2.value
            return False
        
        return False
    
    def __str__(self):
        """Return string representation of the hand."""
        cards_str = ' '.join(str(card) for card in self.cards)
        return f"{str(self.rank)}: {cards_str}"
    
    @staticmethod
    def best_hand_from_cards(cards: List[Card]) -> 'Hand':
        """
        Find the best 5-card hand from a list of cards.
        
        Args:
            cards: List of 5 or more cards
            
        Returns:
            The best possible 5-card hand
            
        Raises:
            ValueError: If fewer than 5 cards provided
        """
        if len(cards) < 5:
            raise ValueError(f"Need at least 5 cards to make a hand, got {len(cards)}")
        
        best_hand = None
        
        # Try all possible 5-card combinations
        for five_cards in combinations(cards, 5):
            hand = Hand(list(five_cards))
            if best_hand is None or hand > best_hand:
                best_hand = hand
        
        return best_hand
