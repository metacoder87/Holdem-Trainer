"""
Test suite for AI Player classes.
Tests AI decision making, different playing styles, and behavior patterns.
"""
import pytest
from unittest.mock import Mock, patch
from src.game.ai_player import AIPlayer, AIStyle, CautiousAI, WildAI, BalancedAI, RandomAI
from src.game.player import PlayerAction
from src.game.card import Card, Suit, Rank
from src.game.hand import Hand, HandRank


class TestAIStyle:
    """Test cases for AIStyle enum."""
    
    def test_ai_style_values(self):
        """Test AI style enum values."""
        assert AIStyle.CAUTIOUS.value == "cautious"
        assert AIStyle.WILD.value == "wild"
        assert AIStyle.BALANCED.value == "balanced"
        assert AIStyle.RANDOM.value == "random"


class TestAIPlayer:
    """Test cases for base AIPlayer class."""
    
    def test_ai_player_creation(self):
        """Test creating an AI player."""
        ai_player = AIPlayer("AI_Test", 1000, AIStyle.CAUTIOUS)
        
        assert ai_player.name == "AI_Test"
        assert ai_player.bankroll == 1000
        assert ai_player.ai_style == AIStyle.CAUTIOUS
        assert ai_player.is_ai
        
    def test_ai_player_decision_interface(self):
        """Test AI player decision interface."""
        ai_player = AIPlayer("AI_Test", 1000, AIStyle.CAUTIOUS)
        
        # Mock game state
        game_state = {
            'pot_size': 100,
            'current_bet': 50,
            'min_raise': 50,
            'players_in_hand': 3,
            'community_cards': [],
            'betting_round': 'preflop'
        }
        
        # This should be implemented by subclasses
        with pytest.raises(NotImplementedError):
            ai_player.make_decision(game_state)
            
    def test_ai_player_string_representation(self):
        """Test string representation includes AI indicator."""
        ai_player = AIPlayer("AI_Test", 1000, AIStyle.CAUTIOUS)
        ai_str = str(ai_player)
        
        assert "AI_Test" in ai_str
        assert "AI" in ai_str
        assert "CAUTIOUS" in ai_str


class TestCautiousAI:
    """Test cases for CautiousAI implementation."""
    
    def test_cautious_ai_creation(self):
        """Test creating a cautious AI player."""
        ai = CautiousAI("Cautious_Bot", 1000)
        
        assert ai.ai_style == AIStyle.CAUTIOUS
        assert ai.fold_threshold > 0.3  # Should be conservative
        assert ai.raise_threshold > 0.8  # Should be very selective
        
    def test_cautious_ai_preflop_weak_hand(self):
        """Test cautious AI with weak preflop hand."""
        ai = CautiousAI("Cautious_Bot", 1000)
        
        # Deal weak hand
        weak_cards = [
            Card(Suit.HEARTS, Rank.TWO),
            Card(Suit.SPADES, Rank.SEVEN)
        ]
        ai.deal_hole_cards(weak_cards)
        
        game_state = {
            'pot_size': 30,
            'current_bet': 20,
            'min_raise': 20,
            'players_in_hand': 4,
            'community_cards': [],
            'betting_round': 'preflop'
        }
        
        decision, amount = ai.make_decision(game_state)
        
        # Should likely fold with weak hand
        assert decision in [PlayerAction.FOLD, PlayerAction.CALL]
        if decision == PlayerAction.CALL:
            assert amount <= 20  # Conservative call
            
    def test_cautious_ai_preflop_strong_hand(self):
        """Test cautious AI with strong preflop hand."""
        ai = CautiousAI("Cautious_Bot", 1000)
        
        # Deal strong hand
        strong_cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.SPADES, Rank.ACE)
        ]
        ai.deal_hole_cards(strong_cards)
        
        game_state = {
            'pot_size': 30,
            'current_bet': 20,
            'min_raise': 20,
            'players_in_hand': 4,
            'community_cards': [],
            'betting_round': 'preflop'
        }
        
        decision, amount = ai.make_decision(game_state)
        
        # Should call or raise with strong hand
        assert decision in [PlayerAction.CALL, PlayerAction.RAISE]
        
    def test_cautious_ai_position_consideration(self):
        """Test that cautious AI considers position."""
        ai = CautiousAI("Cautious_Bot", 1000)
        ai.position = 8  # Late position
        
        # Marginal hand that might play in late position
        cards = [
            Card(Suit.HEARTS, Rank.KING),
            Card(Suit.SPADES, Rank.JACK)
        ]
        ai.deal_hole_cards(cards)
        
        game_state = {
            'pot_size': 30,
            'current_bet': 10,
            'min_raise': 10,
            'players_in_hand': 3,
            'community_cards': [],
            'betting_round': 'preflop'
        }
        
        decision, amount = ai.make_decision(game_state)
        
        # In late position with fewer players, might be more willing to play
        assert decision != PlayerAction.FOLD or ai.position < 6


class TestWildAI:
    """Test cases for WildAI implementation."""
    
    def test_wild_ai_creation(self):
        """Test creating a wild AI player."""
        ai = WildAI("Wild_Bot", 1000)
        
        assert ai.ai_style == AIStyle.WILD
        assert ai.bluff_frequency > 0.2  # Should bluff often
        assert ai.aggression_factor > 1.5  # Should be aggressive
        
    def test_wild_ai_aggressive_betting(self):
        """Test wild AI tends to bet aggressively."""
        ai = WildAI("Wild_Bot", 1000)
        
        # Even with mediocre hand
        cards = [
            Card(Suit.HEARTS, Rank.KING),
            Card(Suit.SPADES, Rank.NINE)
        ]
        ai.deal_hole_cards(cards)
        
        game_state = {
            'pot_size': 50,
            'current_bet': 25,
            'min_raise': 25,
            'players_in_hand': 3,
            'community_cards': [],
            'betting_round': 'preflop'
        }
        
        # Run multiple times to test for aggressive tendency
        aggressive_count = 0
        for _ in range(10):
            decision, amount = ai.make_decision(game_state)
            if decision == PlayerAction.RAISE:
                aggressive_count += 1
                
        # Should show aggressive tendency (not 100% but often)
        assert aggressive_count >= 2  # At least some aggression
        
    def test_wild_ai_bluffing(self):
        """Test wild AI bluffs with weak hands."""
        ai = WildAI("Wild_Bot", 1000)
        
        # Very weak hand
        weak_cards = [
            Card(Suit.HEARTS, Rank.TWO),
            Card(Suit.CLUBS, Rank.FIVE)
        ]
        ai.deal_hole_calls(weak_cards)
        
        # Good bluffing situation (few opponents)
        game_state = {
            'pot_size': 100,
            'current_bet': 0,
            'min_raise': 25,
            'players_in_hand': 2,
            'community_cards': [
                Card(Suit.SPADES, Rank.ACE),
                Card(Suit.DIAMONDS, Rank.KING),
                Card(Suit.HEARTS, Rank.QUEEN)
            ],
            'betting_round': 'flop'
        }
        
        # Should sometimes bluff even with weak hand
        bluff_attempts = 0
        for _ in range(10):
            decision, amount = ai.make_decision(game_state)
            if decision in [PlayerAction.RAISE, PlayerAction.ALL_IN]:
                bluff_attempts += 1
                
        assert bluff_attempts >= 1  # Should attempt some bluffs


class TestBalancedAI:
    """Test cases for BalancedAI implementation."""
    
    def test_balanced_ai_creation(self):
        """Test creating a balanced AI player."""
        ai = BalancedAI("Balanced_Bot", 1000)
        
        assert ai.ai_style == AIStyle.BALANCED
        assert hasattr(ai, 'pot_odds_threshold')
        assert hasattr(ai, 'equity_calculator')
        
    def test_balanced_ai_pot_odds_calculation(self):
        """Test balanced AI calculates pot odds correctly."""
        ai = BalancedAI("Balanced_Bot", 1000)
        
        game_state = {
            'pot_size': 200,
            'current_bet': 50,
            'call_amount': 50
        }
        
        pot_odds = ai.calculate_pot_odds(game_state)
        expected_odds = 50 / (200 + 50)  # call / (pot + call)
        
        assert abs(pot_odds - expected_odds) < 0.01
        
    def test_balanced_ai_hand_equity_based_decision(self):
        """Test balanced AI makes decisions based on hand equity."""
        ai = BalancedAI("Balanced_Bot", 1000)
        
        # Strong hand with good equity
        strong_cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.SPADES, Rank.KING)
        ]
        ai.deal_hole_cards(strong_cards)
        
        game_state = {
            'pot_size': 100,
            'current_bet': 25,
            'min_raise': 25,
            'players_in_hand': 3,
            'community_cards': [
                Card(Suit.HEARTS, Rank.KING),
                Card(Suit.DIAMONDS, Rank.QUEEN),
                Card(Suit.CLUBS, Rank.TEN)
            ],
            'betting_round': 'flop'
        }
        
        decision, amount = ai.make_decision(game_state)
        
        # With top pair, top kicker, should be willing to bet/call
        assert decision in [PlayerAction.CALL, PlayerAction.RAISE]
        
    def test_balanced_ai_position_adjustment(self):
        """Test balanced AI adjusts play based on position."""
        ai = BalancedAI("Balanced_Bot", 1000)
        
        # Test same hand in different positions
        cards = [
            Card(Suit.HEARTS, Rank.JACK),
            Card(Suit.SPADES, Rank.TEN)
        ]
        
        base_game_state = {
            'pot_size': 30,
            'current_bet': 10,
            'min_raise': 10,
            'players_in_hand': 4,
            'community_cards': [],
            'betting_round': 'preflop'
        }
        
        # Early position
        ai.position = 1
        ai.deal_hole_cards(cards.copy())
        early_decision, _ = ai.make_decision(base_game_state)
        
        # Late position
        ai.position = 8
        ai.reset_for_new_hand()
        ai.deal_hole_cards(cards.copy())
        late_decision, _ = ai.make_decision(base_game_state)
        
        # May play differently based on position
        # (This is a probabilistic test, might not always differ)


class TestRandomAI:
    """Test cases for RandomAI implementation."""
    
    def test_random_ai_creation(self):
        """Test creating a random AI player."""
        ai = RandomAI("Random_Bot", 1000)
        
        assert ai.ai_style == AIStyle.RANDOM
        assert hasattr(ai, 'randomness_factor')
        
    def test_random_ai_unpredictable_decisions(self):
        """Test random AI makes unpredictable decisions."""
        ai = RandomAI("Random_Bot", 1000)
        
        cards = [
            Card(Suit.HEARTS, Rank.KING),
            Card(Suit.SPADES, Rank.QUEEN)
        ]
        ai.deal_hole_cards(cards)
        
        game_state = {
            'pot_size': 50,
            'current_bet': 20,
            'min_raise': 20,
            'players_in_hand': 3,
            'community_cards': [],
            'betting_round': 'preflop'
        }
        
        # Collect multiple decisions to test randomness
        decisions = []
        for _ in range(20):
            ai.reset_for_new_round()
            decision, amount = ai.make_decision(game_state)
            decisions.append(decision)
            
        # Should have some variety in decisions
        unique_decisions = set(decisions)
        assert len(unique_decisions) >= 2  # At least some variety
        
    def test_random_ai_bet_sizing_variance(self):
        """Test random AI varies bet sizes."""
        ai = RandomAI("Random_Bot", 1000)
        
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.SPADES, Rank.KING)
        ]
        ai.deal_hole_cards(cards)
        
        game_state = {
            'pot_size': 100,
            'current_bet': 0,
            'min_raise': 25,
            'players_in_hand': 3,
            'community_cards': [],
            'betting_round': 'preflop'
        }
        
        # Collect raise amounts
        raise_amounts = []
        for _ in range(20):
            ai.reset_for_new_round()
            decision, amount = ai.make_decision(game_state)
            if decision == PlayerAction.RAISE:
                raise_amounts.append(amount)
                
        # Should have some variety in raise sizes
        if len(raise_amounts) >= 2:
            unique_amounts = set(raise_amounts)
            assert len(unique_amounts) >= 2  # Some variety in sizing


class TestAIPlayerFactory:
    """Test cases for AI player creation factory."""
    
    def test_create_ai_players(self):
        """Test creating different types of AI players."""
        from src.game.ai_player import create_ai_player
        
        cautious = create_ai_player("Cautious_Bot", 1000, AIStyle.CAUTIOUS)
        wild = create_ai_player("Wild_Bot", 1000, AIStyle.WILD)
        balanced = create_ai_player("Balanced_Bot", 1000, AIStyle.BALANCED)
        random = create_ai_player("Random_Bot", 1000, AIStyle.RANDOM)
        
        assert isinstance(cautious, CautiousAI)
        assert isinstance(wild, WildAI)
        assert isinstance(balanced, BalancedAI)
        assert isinstance(random, RandomAI)
        
    def test_create_mixed_ai_table(self):
        """Test creating a table with mixed AI personalities."""
        from src.game.ai_player import create_ai_players_for_table
        
        ai_players = create_ai_players_for_table(6, 1000)
        
        assert len(ai_players) == 6
        
        # Should have variety of AI types
        ai_styles = {player.ai_style for player in ai_players}
        assert len(ai_styles) >= 2  # At least some variety
        
        # All should have proper names and bankrolls
        for player in ai_players:
            assert player.name.startswith("AI_")
            assert player.bankroll == 1000
            assert player.is_ai


class TestAIPlayerIntegration:
    """Integration tests for AI players with game mechanics."""
    
    def test_ai_player_betting_rounds(self):
        """Test AI player through multiple betting rounds."""
        ai = BalancedAI("Test_AI", 1000)
        
        # Deal hole cards
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.SPADES, Rank.ACE)
        ]
        ai.deal_hole_cards(cards)
        
        # Preflop
        preflop_state = {
            'pot_size': 30,
            'current_bet': 20,
            'min_raise': 20,
            'players_in_hand': 4,
            'community_cards': [],
            'betting_round': 'preflop'
        }
        
        preflop_decision, preflop_amount = ai.make_decision(preflop_state)
        assert preflop_decision in [PlayerAction.CALL, PlayerAction.RAISE]
        
        # Simulate placing the bet
        if preflop_decision == PlayerAction.CALL:
            ai.call(20)
        else:
            ai.raise_bet(20, preflop_amount)
            
        # Flop
        ai.reset_for_new_round()
        flop_state = {
            'pot_size': 80,
            'current_bet': 0,
            'min_raise': 20,
            'players_in_hand': 3,
            'community_cards': [
                Card(Suit.HEARTS, Rank.KING),
                Card(Suit.DIAMONDS, Rank.QUEEN),
                Card(Suit.CLUBS, Rank.JACK)
            ],
            'betting_round': 'flop'
        }
        
        flop_decision, flop_amount = ai.make_decision(flop_state)
        
        # Should continue with overpair
        assert flop_decision != PlayerAction.FOLD
        
    def test_ai_player_all_in_scenario(self):
        """Test AI player in all-in scenario."""
        ai = WildAI("Wild_AI", 100)  # Short stack
        
        cards = [
            Card(Suit.HEARTS, Rank.KING),
            Card(Suit.SPADES, Rank.KING)
        ]
        ai.deal_hole_cards(cards)
        
        # Facing large bet relative to stack
        game_state = {
            'pot_size': 200,
            'current_bet': 80,  # 80% of stack
            'min_raise': 20,
            'players_in_hand': 2,
            'community_cards': [],
            'betting_round': 'preflop'
        }
        
        decision, amount = ai.make_decision(game_state)
        
        # With strong hand and short stack, might go all-in
        if decision == PlayerAction.ALL_IN:
            assert amount == ai.bankroll
        elif decision == PlayerAction.CALL:
            assert amount <= ai.bankroll
