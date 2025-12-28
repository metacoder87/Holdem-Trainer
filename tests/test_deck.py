"""
Test suite for Deck class.
Tests deck creation, shuffling, and card dealing functionality.
"""
import pytest
from game.deck import Deck
from game.card import Card, Suit, Rank


class TestDeck:
    """Test cases for the Deck class."""
    
    def test_deck_creation(self):
        """Test creating a new deck."""
        deck = Deck()
        assert len(deck.cards) == 52
        assert deck.cards_remaining == 52
        
    def test_deck_contains_all_cards(self):
        """Test that deck contains all 52 unique cards."""
        deck = Deck()
        card_set = set(deck.cards)
        assert len(card_set) == 52
        
        # Verify all suits and ranks are present
        suits = {card.suit for card in deck.cards}
        ranks = {card.rank for card in deck.cards}
        
        assert len(suits) == 4
        assert len(ranks) == 13
        assert suits == {Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES}
        
    def test_deck_shuffle(self):
        """Test deck shuffling functionality."""
        deck1 = Deck()
        deck2 = Deck()
        
        # Get original order
        original_order1 = deck1.cards.copy()
        original_order2 = deck2.cards.copy()
        
        # They should start in same order
        assert original_order1 == original_order2
        
        # Shuffle and compare
        deck1.shuffle()
        
        # After shuffle, order should be different (with very high probability)
        # Note: There's a tiny chance they could be the same, but extremely unlikely
        assert deck1.cards != original_order1
        
    def test_deck_multiple_shuffles(self):
        """Test multiple shuffles produce different results."""
        deck = Deck()
        original_order = deck.cards.copy()
        
        shuffled_orders = []
        for _ in range(5):
            deck.shuffle()
            shuffled_orders.append(deck.cards.copy())
            
        # All shuffled orders should be different from original
        for order in shuffled_orders:
            assert order != original_order
            
    def test_deal_card(self):
        """Test dealing a single card."""
        deck = Deck()
        original_count = len(deck.cards)
        top_card = deck.cards[0]
        
        dealt_card = deck.deal_card()
        
        assert dealt_card == top_card
        assert len(deck.cards) == original_count - 1
        assert deck.cards_remaining == original_count - 1
        assert dealt_card not in deck.cards
        
    def test_deal_multiple_cards(self):
        """Test dealing multiple cards."""
        deck = Deck()
        original_count = len(deck.cards)
        
        dealt_cards = deck.deal_cards(5)
        
        assert len(dealt_cards) == 5
        assert len(deck.cards) == original_count - 5
        assert deck.cards_remaining == original_count - 5
        
        # All dealt cards should be unique
        assert len(set(dealt_cards)) == 5
        
        # No dealt cards should remain in deck
        for card in dealt_cards:
            assert card not in deck.cards
            
    def test_deal_cards_invalid_count(self):
        """Test dealing more cards than available."""
        deck = Deck()
        
        with pytest.raises(ValueError, match="Cannot deal 53 cards"):
            deck.deal_cards(53)
            
    def test_deal_card_from_empty_deck(self):
        """Test dealing from empty deck raises error."""
        deck = Deck()
        
        # Deal all cards
        deck.deal_cards(52)
        
        with pytest.raises(ValueError, match="Cannot deal from empty deck"):
            deck.deal_card()
            
    def test_deck_reset(self):
        """Test resetting deck to full state."""
        deck = Deck()
        original_cards = deck.cards.copy()
        
        # Deal some cards
        deck.deal_cards(10)
        assert len(deck.cards) == 42
        
        # Reset deck
        deck.reset()
        assert len(deck.cards) == 52
        assert deck.cards_remaining == 52
        
        # Cards should be in original order after reset
        assert deck.cards == original_cards
        
    def test_deck_is_empty(self):
        """Test empty deck detection."""
        deck = Deck()
        
        assert not deck.is_empty
        
        deck.deal_cards(52)
        assert deck.is_empty
        
    def test_deck_peek_top_card(self):
        """Test peeking at top card without dealing."""
        deck = Deck()
        original_count = len(deck.cards)
        
        top_card = deck.peek_top_card()
        
        assert top_card == deck.cards[0]
        assert len(deck.cards) == original_count  # No cards removed
        
    def test_peek_empty_deck(self):
        """Test peeking at empty deck."""
        deck = Deck()
        deck.deal_cards(52)
        
        assert deck.peek_top_card() is None
        
    def test_deck_burn_card(self):
        """Test burning (discarding) a card."""
        deck = Deck()
        original_count = len(deck.cards)
        top_card = deck.cards[0]
        
        burned_card = deck.burn_card()
        
        assert burned_card == top_card
        assert len(deck.cards) == original_count - 1
        assert burned_card not in deck.cards
        
    def test_deck_remaining_count(self):
        """Test cards_remaining property accuracy."""
        deck = Deck()
        
        for i in range(10):
            assert deck.cards_remaining == 52 - i
            deck.deal_card()
            
        assert deck.cards_remaining == 42
        
    def test_deck_string_representation(self):
        """Test string representation of deck."""
        deck = Deck()
        deck_str = str(deck)
        
        assert "52 cards remaining" in deck_str
        
        deck.deal_cards(10)
        deck_str = str(deck)
        assert "42 cards remaining" in deck_str
        
    def test_deck_custom_seed_shuffle(self):
        """Test shuffling with custom seed for reproducibility."""
        deck1 = Deck()
        deck2 = Deck()
        
        deck1.shuffle(seed=12345)
        deck2.shuffle(seed=12345)
        
        assert deck1.cards == deck2.cards
        
    def test_deck_iterator(self):
        """Test deck iteration functionality."""
        deck = Deck()
        cards = list(deck)
        
        assert len(cards) == 52
        assert cards == deck.cards
        
    def test_deck_indexing(self):
        """Test deck indexing functionality."""
        deck = Deck()
        
        assert deck[0] == deck.cards[0]
        assert deck[-1] == deck.cards[-1]
        assert deck[10:15] == deck.cards[10:15]
        
    def test_deck_contains(self):
        """Test 'in' operator with deck."""
        deck = Deck()
        card = deck.cards[0]
        
        assert card in deck
        
        deck.deal_card()  # Remove the card
        assert card not in deck
