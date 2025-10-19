"""
Card module for PyHoldem Pro.
Implements Card class and related enums for suit and rank.
"""
from enum import Enum
from functools import total_ordering


class Suit(Enum):
    """Enumeration for card suits."""
    HEARTS = "♥"
    DIAMONDS = "♦"
    CLUBS = "♣"
    SPADES = "♠"
    
    def __str__(self):
        """Return the suit symbol."""
        return self.value
    
    def __repr__(self):
        """Return the suit name."""
        return f"Suit.{self.name}"


@total_ordering
class Rank(Enum):
    """Enumeration for card ranks."""
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14
    
    def __hash__(self):
        """Return hash for use in sets/dicts."""
        return hash(self.value)
    
    def __str__(self):
        """Return the rank display string."""
        rank_symbols = {
            Rank.JACK: "J",
            Rank.QUEEN: "Q", 
            Rank.KING: "K",
            Rank.ACE: "A"
        }
        return rank_symbols.get(self, str(self.value))
    
    def __repr__(self):
        """Return the rank name."""
        return f"Rank.{self.name}"
    
    def __lt__(self, other):
        """Compare ranks by value."""
        if not isinstance(other, Rank):
            return NotImplemented
        return self.value < other.value
    
    def __eq__(self, other):
        """Check rank equality."""
        if not isinstance(other, Rank):
            return NotImplemented
        return self.value == other.value


@total_ordering
class Card:
    """Represents a playing card with suit and rank."""
    
    def __init__(self, suit: Suit, rank: Rank):
        """
        Initialize a card with suit and rank.
        
        Args:
            suit: Card suit (Hearts, Diamonds, Clubs, Spades)
            rank: Card rank (2-10, J, Q, K, A)
        """
        if not isinstance(suit, Suit):
            raise TypeError(f"suit must be a Suit enum, got {type(suit)}")
        if not isinstance(rank, Rank):
            raise TypeError(f"rank must be a Rank enum, got {type(rank)}")
            
        self.suit = suit
        self.rank = rank
    
    @property
    def value(self) -> int:
        """Return the card value (2-14, with Ace as 14)."""
        return self.rank.value
    
    @property
    def low_ace_value(self) -> int:
        """Return the card value with Ace as 1."""
        if self.rank == Rank.ACE:
            return 1
        return self.rank.value
    
    @property
    def is_red(self) -> bool:
        """Check if card is red (Hearts or Diamonds)."""
        return self.suit in (Suit.HEARTS, Suit.DIAMONDS)
    
    @property
    def is_black(self) -> bool:
        """Check if card is black (Clubs or Spades)."""
        return self.suit in (Suit.CLUBS, Suit.SPADES)
    
    @property
    def is_face_card(self) -> bool:
        """Check if card is a face card (J, Q, K, A)."""
        return self.rank in (Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE)
    
    def __str__(self):
        """Return string representation of card (e.g., 'A♠')."""
        return f"{self.rank}{self.suit}"
    
    def __repr__(self):
        """Return repr representation of card."""
        return f"Card({self.suit.name}, {self.rank.name})"
    
    def __eq__(self, other):
        """Check if two cards are equal (same suit and rank)."""
        if not isinstance(other, Card):
            return NotImplemented
        return self.suit == other.suit and self.rank == other.rank
    
    def __lt__(self, other):
        """Compare cards by rank value."""
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank < other.rank
    
    def __hash__(self):
        """Return hash for use in sets/dicts."""
        return hash((self.suit.value, self.rank.value))
