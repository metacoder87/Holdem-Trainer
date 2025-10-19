"""
Deck module for PyHoldem Pro.
Implements Deck class for managing a 52-card deck.
"""
import random
from typing import List, Optional
from src.game.card import Card, Suit, Rank


class Deck:
    """Represents a standard 52-card deck."""
    
    def __init__(self):
        """Initialize a new deck with 52 cards in standard order."""
        self.cards = self._create_standard_deck()
        self._original_order = self.cards.copy()
    
    def _create_standard_deck(self) -> List[Card]:
        """Create a standard 52-card deck."""
        cards = []
        for suit in Suit:
            for rank in Rank:
                cards.append(Card(suit, rank))
        return cards
    
    @property
    def cards_remaining(self) -> int:
        """Return the number of cards remaining in the deck."""
        return len(self.cards)
    
    @property
    def is_empty(self) -> bool:
        """Check if the deck is empty."""
        return len(self.cards) == 0
    
    def shuffle(self, seed: Optional[int] = None):
        """
        Shuffle the deck.
        
        Args:
            seed: Optional random seed for reproducible shuffling
        """
        if seed is not None:
            random.seed(seed)
        random.shuffle(self.cards)
    
    def deal_card(self) -> Card:
        """
        Deal a single card from the top of the deck.
        
        Returns:
            The dealt card
            
        Raises:
            ValueError: If the deck is empty
        """
        if self.is_empty:
            raise ValueError("Cannot deal from empty deck")
        return self.cards.pop(0)
    
    def deal_cards(self, count: int) -> List[Card]:
        """
        Deal multiple cards from the deck.
        
        Args:
            count: Number of cards to deal
            
        Returns:
            List of dealt cards
            
        Raises:
            ValueError: If trying to deal more cards than available
        """
        if count > len(self.cards):
            raise ValueError(f"Cannot deal {count} cards, only {len(self.cards)} remaining")
        
        dealt_cards = []
        for _ in range(count):
            dealt_cards.append(self.deal_card())
        return dealt_cards
    
    def burn_card(self) -> Card:
        """
        Burn (discard) a card from the top of the deck.
        
        Returns:
            The burned card
            
        Raises:
            ValueError: If the deck is empty
        """
        return self.deal_card()
    
    def peek_top_card(self) -> Optional[Card]:
        """
        Peek at the top card without removing it.
        
        Returns:
            The top card or None if deck is empty
        """
        if self.is_empty:
            return None
        return self.cards[0]
    
    def reset(self):
        """Reset the deck to its original unshuffled state."""
        self.cards = self._original_order.copy()
    
    def __len__(self) -> int:
        """Return the number of cards in the deck."""
        return len(self.cards)
    
    def __iter__(self):
        """Iterate over cards in the deck."""
        return iter(self.cards)
    
    def __getitem__(self, key):
        """Get card(s) by index or slice."""
        return self.cards[key]
    
    def __contains__(self, card: Card) -> bool:
        """Check if a card is in the deck."""
        return card in self.cards
    
    def __str__(self) -> str:
        """Return string representation of the deck."""
        return f"Deck with {self.cards_remaining} cards remaining"
    
    def __repr__(self) -> str:
        """Return repr representation of the deck."""
        return f"Deck(cards_remaining={self.cards_remaining})"
