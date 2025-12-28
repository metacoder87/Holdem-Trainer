"""
Test suite for Card class.
Tests the fundamental card representation and comparison logic.
"""
import pytest
from game.card import Card, Suit, Rank


class TestCard:
    """Test cases for the Card class."""
    
    def test_card_creation_valid_inputs(self):
        """Test creating cards with valid suit and rank."""
        card = Card(Suit.HEARTS, Rank.ACE)
        assert card.suit == Suit.HEARTS
        assert card.rank == Rank.ACE
        
    def test_card_creation_all_suits(self):
        """Test creating cards with all valid suits."""
        suits = [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]
        for suit in suits:
            card = Card(suit, Rank.KING)
            assert card.suit == suit
            
    def test_card_creation_all_ranks(self):
        """Test creating cards with all valid ranks."""
        ranks = [Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX,
                Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN, Rank.JACK,
                Rank.QUEEN, Rank.KING, Rank.ACE]
        for rank in ranks:
            card = Card(Suit.HEARTS, rank)
            assert card.rank == rank
            
    def test_card_value_property(self):
        """Test card value property for ordering."""
        two = Card(Suit.HEARTS, Rank.TWO)
        ace = Card(Suit.HEARTS, Rank.ACE)
        king = Card(Suit.HEARTS, Rank.KING)
        
        assert two.value == 2
        assert ace.value == 14  # High ace by default
        assert king.value == 13
        
    def test_card_value_low_ace(self):
        """Test card value when ace is low."""
        ace = Card(Suit.HEARTS, Rank.ACE)
        assert ace.low_ace_value == 1
        
    def test_card_equality(self):
        """Test card equality comparison."""
        card1 = Card(Suit.HEARTS, Rank.ACE)
        card2 = Card(Suit.HEARTS, Rank.ACE)
        card3 = Card(Suit.SPADES, Rank.ACE)
        card4 = Card(Suit.HEARTS, Rank.KING)
        
        assert card1 == card2
        assert card1 != card3  # Different suit
        assert card1 != card4  # Different rank
        
    def test_card_comparison(self):
        """Test card comparison operators."""
        two = Card(Suit.HEARTS, Rank.TWO)
        king = Card(Suit.HEARTS, Rank.KING)
        ace = Card(Suit.HEARTS, Rank.ACE)
        
        assert two < king < ace
        assert ace > king > two
        assert two <= king <= ace
        assert ace >= king >= two
        
    def test_card_string_representation(self):
        """Test string representation of cards."""
        card = Card(Suit.HEARTS, Rank.ACE)
        assert str(card) == "A♥"
        
        card = Card(Suit.SPADES, Rank.TEN)
        assert str(card) == "10♠"
        
        card = Card(Suit.DIAMONDS, Rank.JACK)
        assert str(card) == "J♦"
        
    def test_card_repr(self):
        """Test repr representation of cards."""
        card = Card(Suit.HEARTS, Rank.ACE)
        assert repr(card) == "Card(HEARTS, ACE)"
        
    def test_card_is_red(self):
        """Test red card identification."""
        heart_card = Card(Suit.HEARTS, Rank.ACE)
        diamond_card = Card(Suit.DIAMONDS, Rank.ACE)
        club_card = Card(Suit.CLUBS, Rank.ACE)
        spade_card = Card(Suit.SPADES, Rank.ACE)
        
        assert heart_card.is_red
        assert diamond_card.is_red
        assert not club_card.is_red
        assert not spade_card.is_red
        
    def test_card_is_black(self):
        """Test black card identification."""
        heart_card = Card(Suit.HEARTS, Rank.ACE)
        diamond_card = Card(Suit.DIAMONDS, Rank.ACE)
        club_card = Card(Suit.CLUBS, Rank.ACE)
        spade_card = Card(Suit.SPADES, Rank.ACE)
        
        assert not heart_card.is_black
        assert not diamond_card.is_black
        assert club_card.is_black
        assert spade_card.is_black
        
    def test_card_hash(self):
        """Test card hashing for use in sets/dicts."""
        card1 = Card(Suit.HEARTS, Rank.ACE)
        card2 = Card(Suit.HEARTS, Rank.ACE)
        card3 = Card(Suit.SPADES, Rank.ACE)
        
        card_set = {card1, card2, card3}
        assert len(card_set) == 2  # card1 and card2 should be the same
        
    def test_card_face_card_properties(self):
        """Test face card identification."""
        jack = Card(Suit.HEARTS, Rank.JACK)
        queen = Card(Suit.HEARTS, Rank.QUEEN)
        king = Card(Suit.HEARTS, Rank.KING)
        ace = Card(Suit.HEARTS, Rank.ACE)
        ten = Card(Suit.HEARTS, Rank.TEN)
        
        assert jack.is_face_card
        assert queen.is_face_card
        assert king.is_face_card
        assert ace.is_face_card
        assert not ten.is_face_card


class TestSuit:
    """Test cases for the Suit enum."""
    
    def test_suit_values(self):
        """Test suit enum values."""
        assert Suit.HEARTS.value == "♥"
        assert Suit.DIAMONDS.value == "♦"
        assert Suit.CLUBS.value == "♣"
        assert Suit.SPADES.value == "♠"
        
    def test_suit_string_representation(self):
        """Test suit string representation."""
        assert str(Suit.HEARTS) == "♥"
        assert str(Suit.DIAMONDS) == "♦"
        assert str(Suit.CLUBS) == "♣"
        assert str(Suit.SPADES) == "♠"


class TestRank:
    """Test cases for the Rank enum."""
    
    def test_rank_values(self):
        """Test rank enum values."""
        assert Rank.TWO.value == 2
        assert Rank.THREE.value == 3
        assert Rank.TEN.value == 10
        assert Rank.JACK.value == 11
        assert Rank.QUEEN.value == 12
        assert Rank.KING.value == 13
        assert Rank.ACE.value == 14
        
    def test_rank_string_representation(self):
        """Test rank string representation."""
        assert str(Rank.TWO) == "2"
        assert str(Rank.TEN) == "10"
        assert str(Rank.JACK) == "J"
        assert str(Rank.QUEEN) == "Q"
        assert str(Rank.KING) == "K"
        assert str(Rank.ACE) == "A"
        
    def test_rank_ordering(self):
        """Test rank comparison."""
        assert Rank.TWO < Rank.THREE < Rank.ACE
        assert Rank.ACE > Rank.KING > Rank.QUEEN
