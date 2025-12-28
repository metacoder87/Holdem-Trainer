"""
Test suite for Hand evaluation and ranking.
Tests poker hand detection, comparison, and ranking logic.
"""
import pytest
from game.hand import Hand, HandRank
from game.card import Card, Suit, Rank


class TestHandRank:
    """Test cases for HandRank enum."""
    
    def test_hand_rank_values(self):
        """Test hand rank enum values are correctly ordered."""
        assert HandRank.HIGH_CARD.value == 1
        assert HandRank.PAIR.value == 2
        assert HandRank.TWO_PAIR.value == 3
        assert HandRank.THREE_OF_A_KIND.value == 4
        assert HandRank.STRAIGHT.value == 5
        assert HandRank.FLUSH.value == 6
        assert HandRank.FULL_HOUSE.value == 7
        assert HandRank.FOUR_OF_A_KIND.value == 8
        assert HandRank.STRAIGHT_FLUSH.value == 9
        assert HandRank.ROYAL_FLUSH.value == 10
        
    def test_hand_rank_comparison(self):
        """Test hand rank comparison operators."""
        assert HandRank.HIGH_CARD < HandRank.PAIR
        assert HandRank.PAIR < HandRank.FLUSH
        assert HandRank.FLUSH < HandRank.FULL_HOUSE
        assert HandRank.STRAIGHT_FLUSH < HandRank.ROYAL_FLUSH


class TestHand:
    """Test cases for Hand class."""
    
    def test_hand_creation(self):
        """Test creating a hand with cards."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.HEARTS, Rank.KING),
            Card(Suit.HEARTS, Rank.QUEEN),
            Card(Suit.HEARTS, Rank.JACK),
            Card(Suit.HEARTS, Rank.TEN)
        ]
        hand = Hand(cards)
        assert len(hand.cards) == 5
        assert hand.cards == cards
        
    def test_hand_invalid_size(self):
        """Test creating hand with invalid number of cards."""
        cards = [Card(Suit.HEARTS, Rank.ACE)]
        
        with pytest.raises(ValueError, match="Hand must contain exactly 5 cards"):
            Hand(cards)
            
    def test_royal_flush_detection(self):
        """Test royal flush detection."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.HEARTS, Rank.KING),
            Card(Suit.HEARTS, Rank.QUEEN),
            Card(Suit.HEARTS, Rank.JACK),
            Card(Suit.HEARTS, Rank.TEN)
        ]
        hand = Hand(cards)
        assert hand.rank == HandRank.ROYAL_FLUSH
        assert hand.high_card.rank == Rank.ACE
        
    def test_straight_flush_detection(self):
        """Test straight flush detection."""
        cards = [
            Card(Suit.SPADES, Rank.NINE),
            Card(Suit.SPADES, Rank.EIGHT),
            Card(Suit.SPADES, Rank.SEVEN),
            Card(Suit.SPADES, Rank.SIX),
            Card(Suit.SPADES, Rank.FIVE)
        ]
        hand = Hand(cards)
        assert hand.rank == HandRank.STRAIGHT_FLUSH
        assert hand.high_card.rank == Rank.NINE
        
    def test_four_of_a_kind_detection(self):
        """Test four of a kind detection."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.ACE),
            Card(Suit.CLUBS, Rank.ACE),
            Card(Suit.SPADES, Rank.ACE),
            Card(Suit.HEARTS, Rank.KING)
        ]
        hand = Hand(cards)
        assert hand.rank == HandRank.FOUR_OF_A_KIND
        assert hand.four_of_a_kind_rank == Rank.ACE
        
    def test_full_house_detection(self):
        """Test full house detection."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.ACE),
            Card(Suit.CLUBS, Rank.ACE),
            Card(Suit.SPADES, Rank.KING),
            Card(Suit.HEARTS, Rank.KING)
        ]
        hand = Hand(cards)
        assert hand.rank == HandRank.FULL_HOUSE
        assert hand.three_of_a_kind_rank == Rank.ACE
        assert hand.pair_rank == Rank.KING
        
    def test_flush_detection(self):
        """Test flush detection."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.HEARTS, Rank.JACK),
            Card(Suit.HEARTS, Rank.NINE),
            Card(Suit.HEARTS, Rank.SEVEN),
            Card(Suit.HEARTS, Rank.FIVE)
        ]
        hand = Hand(cards)
        assert hand.rank == HandRank.FLUSH
        assert hand.high_card.rank == Rank.ACE
        
    def test_straight_detection(self):
        """Test straight detection."""
        cards = [
            Card(Suit.HEARTS, Rank.TEN),
            Card(Suit.DIAMONDS, Rank.NINE),
            Card(Suit.CLUBS, Rank.EIGHT),
            Card(Suit.SPADES, Rank.SEVEN),
            Card(Suit.HEARTS, Rank.SIX)
        ]
        hand = Hand(cards)
        assert hand.rank == HandRank.STRAIGHT
        assert hand.high_card.rank == Rank.TEN
        
    def test_ace_low_straight_detection(self):
        """Test ace-low straight (A-2-3-4-5) detection."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.TWO),
            Card(Suit.CLUBS, Rank.THREE),
            Card(Suit.SPADES, Rank.FOUR),
            Card(Suit.HEARTS, Rank.FIVE)
        ]
        hand = Hand(cards)
        assert hand.rank == HandRank.STRAIGHT
        assert hand.high_card.rank == Rank.FIVE  # In ace-low straight, 5 is high
        
    def test_three_of_a_kind_detection(self):
        """Test three of a kind detection."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.ACE),
            Card(Suit.CLUBS, Rank.ACE),
            Card(Suit.SPADES, Rank.KING),
            Card(Suit.HEARTS, Rank.QUEEN)
        ]
        hand = Hand(cards)
        assert hand.rank == HandRank.THREE_OF_A_KIND
        assert hand.three_of_a_kind_rank == Rank.ACE
        
    def test_two_pair_detection(self):
        """Test two pair detection."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.ACE),
            Card(Suit.CLUBS, Rank.KING),
            Card(Suit.SPADES, Rank.KING),
            Card(Suit.HEARTS, Rank.QUEEN)
        ]
        hand = Hand(cards)
        assert hand.rank == HandRank.TWO_PAIR
        assert hand.high_pair_rank == Rank.ACE
        assert hand.low_pair_rank == Rank.KING
        
    def test_pair_detection(self):
        """Test pair detection."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.ACE),
            Card(Suit.CLUBS, Rank.KING),
            Card(Suit.SPADES, Rank.QUEEN),
            Card(Suit.HEARTS, Rank.JACK)
        ]
        hand = Hand(cards)
        assert hand.rank == HandRank.PAIR
        assert hand.pair_rank == Rank.ACE
        
    def test_high_card_detection(self):
        """Test high card detection."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.KING),
            Card(Suit.CLUBS, Rank.QUEEN),
            Card(Suit.SPADES, Rank.TEN),
            Card(Suit.HEARTS, Rank.EIGHT)
        ]
        hand = Hand(cards)
        assert hand.rank == HandRank.HIGH_CARD
        assert hand.high_card.rank == Rank.ACE
        
    def test_hand_comparison_different_ranks(self):
        """Test comparing hands with different ranks."""
        # Royal flush vs straight flush
        royal = Hand([
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.HEARTS, Rank.KING),
            Card(Suit.HEARTS, Rank.QUEEN),
            Card(Suit.HEARTS, Rank.JACK),
            Card(Suit.HEARTS, Rank.TEN)
        ])
        
        straight_flush = Hand([
            Card(Suit.SPADES, Rank.NINE),
            Card(Suit.SPADES, Rank.EIGHT),
            Card(Suit.SPADES, Rank.SEVEN),
            Card(Suit.SPADES, Rank.SIX),
            Card(Suit.SPADES, Rank.FIVE)
        ])
        
        assert royal > straight_flush
        assert straight_flush < royal
        
    def test_hand_comparison_same_rank(self):
        """Test comparing hands with same rank."""
        # Two flushes
        flush1 = Hand([
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.HEARTS, Rank.JACK),
            Card(Suit.HEARTS, Rank.NINE),
            Card(Suit.HEARTS, Rank.SEVEN),
            Card(Suit.HEARTS, Rank.FIVE)
        ])
        
        flush2 = Hand([
            Card(Suit.SPADES, Rank.KING),
            Card(Suit.SPADES, Rank.JACK),
            Card(Suit.SPADES, Rank.NINE),
            Card(Suit.SPADES, Rank.SEVEN),
            Card(Suit.SPADES, Rank.FIVE)
        ])
        
        assert flush1 > flush2  # Ace high beats King high
        
    def test_hand_tie(self):
        """Test tied hands."""
        hand1 = Hand([
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.HEARTS, Rank.KING),
            Card(Suit.HEARTS, Rank.QUEEN),
            Card(Suit.HEARTS, Rank.JACK),
            Card(Suit.HEARTS, Rank.TEN)
        ])
        
        hand2 = Hand([
            Card(Suit.SPADES, Rank.ACE),
            Card(Suit.SPADES, Rank.KING),
            Card(Suit.SPADES, Rank.QUEEN),
            Card(Suit.SPADES, Rank.JACK),
            Card(Suit.SPADES, Rank.TEN)
        ])
        
        assert hand1 == hand2
        
    def test_best_hand_from_seven_cards(self):
        """Test finding best 5-card hand from 7 cards."""
        seven_cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.HEARTS, Rank.KING),
            Card(Suit.HEARTS, Rank.QUEEN),
            Card(Suit.HEARTS, Rank.JACK),
            Card(Suit.HEARTS, Rank.TEN),
            Card(Suit.SPADES, Rank.TWO),
            Card(Suit.CLUBS, Rank.THREE)
        ]
        
        best_hand = Hand.best_hand_from_cards(seven_cards)
        assert best_hand.rank == HandRank.ROYAL_FLUSH
        
    def test_best_hand_from_insufficient_cards(self):
        """Test error when trying to find best hand from < 5 cards."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.HEARTS, Rank.KING)
        ]
        
        with pytest.raises(ValueError, match="Need at least 5 cards"):
            Hand.best_hand_from_cards(cards)
            
    def test_hand_string_representation(self):
        """Test string representation of hands."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.HEARTS, Rank.KING),
            Card(Suit.HEARTS, Rank.QUEEN),
            Card(Suit.HEARTS, Rank.JACK),
            Card(Suit.HEARTS, Rank.TEN)
        ]
        hand = Hand(cards)
        hand_str = str(hand)
        
        assert "Royal Flush" in hand_str
        assert "A♥" in hand_str
        
    def test_kickers_high_card(self):
        """Test kicker cards for high card hands."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.KING),
            Card(Suit.CLUBS, Rank.QUEEN),
            Card(Suit.SPADES, Rank.TEN),
            Card(Suit.HEARTS, Rank.EIGHT)
        ]
        hand = Hand(cards)
        
        assert len(hand.kickers) == 5  # All cards are kickers in high card
        assert hand.kickers[0].rank == Rank.ACE
        assert hand.kickers[1].rank == Rank.KING
        
    def test_kickers_pair(self):
        """Test kicker cards for pair hands."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.ACE),
            Card(Suit.CLUBS, Rank.KING),
            Card(Suit.SPADES, Rank.QUEEN),
            Card(Suit.HEARTS, Rank.JACK)
        ]
        hand = Hand(cards)
        
        assert len(hand.kickers) == 3  # 3 kickers after the pair
        assert hand.kickers[0].rank == Rank.KING
        assert hand.kickers[1].rank == Rank.QUEEN
        assert hand.kickers[2].rank == Rank.JACK
