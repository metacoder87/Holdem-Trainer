"""
Test suite for Statistics and Analytics.
Tests poker statistics calculations, odds computation, and performance analysis.
"""
import pytest
from src.stats.calculator import PotOddsCalculator, HandOddsCalculator, EquityCalculator
from src.stats.analyzer import GameAnalyzer, PlayerAnalyzer
from src.game.card import Card, Suit, Rank
from src.game.hand import Hand
from src.game.player import Player


class TestPotOddsCalculator:
    """Test cases for PotOddsCalculator."""
    
    def test_calculate_pot_odds_basic(self):
        """Test basic pot odds calculation."""
        calculator = PotOddsCalculator()
        
        # Pot: $100, Call: $20
        pot_odds = calculator.calculate_pot_odds(pot_size=100, bet_to_call=20)
        expected_odds = 20 / (100 + 20)  # 20/120 = 1/6 = 16.67%
        
        assert abs(pot_odds - expected_odds) < 0.001
        
    def test_calculate_pot_odds_percentage(self):
        """Test pot odds as percentage."""
        calculator = PotOddsCalculator()
        
        pot_odds_decimal = calculator.calculate_pot_odds(100, 25)
        pot_odds_percent = calculator.calculate_pot_odds_percentage(100, 25)
        
        assert abs(pot_odds_percent - (pot_odds_decimal * 100)) < 0.01
        
    def test_calculate_pot_odds_ratio(self):
        """Test pot odds as ratio."""
        calculator = PotOddsCalculator()
        
        # Pot: $300, Call: $100 -> 3:1 odds
        ratio = calculator.calculate_pot_odds_ratio(300, 100)
        
        assert ratio == (3, 1)
        
    def test_calculate_pot_odds_invalid_inputs(self):
        """Test pot odds calculation with invalid inputs."""
        calculator = PotOddsCalculator()
        
        with pytest.raises(ValueError):
            calculator.calculate_pot_odds(-100, 20)  # Negative pot
            
        with pytest.raises(ValueError):
            calculator.calculate_pot_odds(100, -20)  # Negative bet
            
        with pytest.raises(ValueError):
            calculator.calculate_pot_odds(100, 0)  # Zero bet
            
    def test_implied_odds(self):
        """Test implied odds calculation."""
        calculator = PotOddsCalculator()
        
        # Current pot: $100, Call: $20, Expected future bets: $50
        implied_odds = calculator.calculate_implied_odds(
            pot_size=100, 
            bet_to_call=20, 
            expected_future_bets=50
        )
        
        # Effective pot becomes $150, so odds are 20/170
        expected_odds = 20 / (100 + 20 + 50)
        
        assert abs(implied_odds - expected_odds) < 0.001
        
    def test_reverse_implied_odds(self):
        """Test reverse implied odds calculation."""
        calculator = PotOddsCalculator()
        
        reverse_odds = calculator.calculate_reverse_implied_odds(
            pot_size=200,
            bet_to_call=50,
            potential_future_losses=100
        )
        
        # Account for potential future losses
        expected_odds = (50 + 100) / (200 + 50)  # Include future losses
        
        assert abs(reverse_odds - expected_odds) < 0.001


class TestHandOddsCalculator:
    """Test cases for HandOddsCalculator."""
    
    def test_calculate_outs_open_ended_straight(self):
        """Test calculating outs for open-ended straight draw."""
        calculator = HandOddsCalculator()
        
        # Hand: 8-9, Board: 7-10-K
        hole_cards = [
            Card(Suit.HEARTS, Rank.EIGHT),
            Card(Suit.SPADES, Rank.NINE)
        ]
        community_cards = [
            Card(Suit.DIAMONDS, Rank.SEVEN),
            Card(Suit.CLUBS, Rank.TEN),
            Card(Suit.HEARTS, Rank.KING)
        ]
        
        outs = calculator.calculate_outs(hole_cards, community_cards, "straight")
        
        # 6s and Jacks complete the straight (8 cards total)
        assert outs == 8
        
    def test_calculate_outs_flush_draw(self):
        """Test calculating outs for flush draw."""
        calculator = HandOddsCalculator()
        
        # Hand: A♥-5♥, Board: 2♥-7♥-K♠
        hole_cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.HEARTS, Rank.FIVE)
        ]
        community_cards = [
            Card(Suit.HEARTS, Rank.TWO),
            Card(Suit.HEARTS, Rank.SEVEN),
            Card(Suit.SPADES, Rank.KING)
        ]
        
        outs = calculator.calculate_outs(hole_cards, community_cards, "flush")
        
        # 9 remaining hearts (13 total - 4 seen)
        assert outs == 9
        
    def test_calculate_hand_probability_turn(self):
        """Test calculating probability of hitting on turn."""
        calculator = HandOddsCalculator()
        
        # 9 outs, 47 unknown cards (52 - 5 seen)
        probability = calculator.calculate_hand_probability(outs=9, cards_to_come=1)
        
        expected_prob = 9 / 47
        assert abs(probability - expected_prob) < 0.001
        
    def test_calculate_hand_probability_turn_and_river(self):
        """Test calculating probability of hitting by river."""
        calculator = HandOddsCalculator()
        
        # 9 outs, 2 cards to come
        probability = calculator.calculate_hand_probability(outs=9, cards_to_come=2)
        
        # Probability of NOT hitting on turn: 38/47
        # Probability of NOT hitting on river (if missed turn): 37/46
        # Probability of missing both: (38/47) * (37/46)
        # Probability of hitting at least once: 1 - ((38/47) * (37/46))
        
        miss_both = (38/47) * (37/46)
        expected_prob = 1 - miss_both
        
        assert abs(probability - expected_prob) < 0.001
        
    def test_rule_of_four_and_two(self):
        """Test rule of 4 and 2 approximation."""
        calculator = HandOddsCalculator()
        
        # After flop (2 cards to come)
        rule_of_four = calculator.rule_of_four_and_two(outs=9, cards_to_come=2)
        assert abs(rule_of_four - (9 * 4)) < 1  # Approximate
        
        # After turn (1 card to come)  
        rule_of_two = calculator.rule_of_four_and_two(outs=9, cards_to_come=1)
        assert abs(rule_of_two - (9 * 2)) < 1  # Approximate
        
    def test_calculate_hand_strength(self):
        """Test calculating current hand strength."""
        calculator = HandOddsCalculator()
        
        # Strong hand: Top pair, top kicker
        hole_cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.SPADES, Rank.KING)
        ]
        community_cards = [
            Card(Suit.DIAMONDS, Rank.ACE),
            Card(Suit.CLUBS, Rank.SEVEN),
            Card(Suit.HEARTS, Rank.TWO)
        ]
        
        strength = calculator.calculate_hand_strength(hole_cards, community_cards)
        
        # Should be relatively high strength
        assert strength > 0.7  # Strong hand
        
    def test_calculate_hand_potential(self):
        """Test calculating hand improvement potential."""
        calculator = HandOddsCalculator()
        
        # Drawing hand with potential
        hole_cards = [
            Card(Suit.HEARTS, Rank.JACK),
            Card(Suit.HEARTS, Rank.TEN)
        ]
        community_cards = [
            Card(Suit.HEARTS, Rank.NINE),
            Card(Suit.SPADES, Rank.EIGHT),
            Card(Suit.CLUBS, Rank.TWO)
        ]
        
        potential = calculator.calculate_hand_potential(hole_cards, community_cards)
        
        # Open-ended straight flush draw should have high potential
        assert potential > 0.3
        

class TestEquityCalculator:
    """Test cases for EquityCalculator."""
    
    def test_calculate_equity_heads_up(self):
        """Test equity calculation in heads-up situation."""
        calculator = EquityCalculator()
        
        # AA vs KK preflop
        hand1 = [Card(Suit.HEARTS, Rank.ACE), Card(Suit.SPADES, Rank.ACE)]
        hand2 = [Card(Suit.HEARTS, Rank.KING), Card(Suit.SPADES, Rank.KING)]
        
        equity1, equity2 = calculator.calculate_heads_up_equity(hand1, hand2)
        
        # AA should have ~80% equity vs KK
        assert equity1 > 0.75
        assert equity2 < 0.25
        assert abs((equity1 + equity2) - 1.0) < 0.01  # Should sum to 1
        
    def test_calculate_equity_multiway(self):
        """Test equity calculation in multiway pot."""
        calculator = EquityCalculator()
        
        hands = [
            [Card(Suit.HEARTS, Rank.ACE), Card(Suit.SPADES, Rank.ACE)],  # AA
            [Card(Suit.HEARTS, Rank.KING), Card(Suit.SPADES, Rank.KING)],  # KK
            [Card(Suit.HEARTS, Rank.QUEEN), Card(Suit.SPADES, Rank.QUEEN)]  # QQ
        ]
        
        equities = calculator.calculate_multiway_equity(hands)
        
        assert len(equities) == 3
        assert abs(sum(equities) - 1.0) < 0.01  # Should sum to 1
        assert equities[0] > equities[1] > equities[2]  # AA > KK > QQ
        
    def test_calculate_equity_with_board(self):
        """Test equity calculation with known community cards."""
        calculator = EquityCalculator()
        
        hand1 = [Card(Suit.HEARTS, Rank.ACE), Card(Suit.SPADES, Rank.KING)]
        hand2 = [Card(Suit.HEARTS, Rank.TWO), Card(Suit.SPADES, Rank.TWO)]
        
        # Flop favors pocket pair
        board = [
            Card(Suit.DIAMONDS, Rank.TWO),
            Card(Suit.CLUBS, Rank.SEVEN),
            Card(Suit.HEARTS, Rank.NINE)
        ]
        
        equity1, equity2 = calculator.calculate_heads_up_equity(hand1, hand2, board)
        
        # Pocket twos should now have much higher equity (set vs overcards)
        assert equity2 > equity1
        

class TestGameAnalyzer:
    """Test cases for GameAnalyzer."""
    
    def test_analyze_preflop_action(self):
        """Test analyzing preflop action."""
        analyzer = GameAnalyzer()
        
        # Simulate preflop action data
        action_data = {
            'position': 2,  # Early position
            'hole_cards': [Card(Suit.HEARTS, Rank.ACE), Card(Suit.SPADES, Rank.KING)],
            'action': 'raise',
            'amount': 50,
            'pot_size_before': 30,
            'players_in_hand': 6
        }
        
        analysis = analyzer.analyze_preflop_action(action_data)
        
        assert 'hand_strength' in analysis
        assert 'position_factor' in analysis
        assert 'recommended_action' in analysis
        
        # AK should be strong enough to raise from any position
        assert analysis['recommended_action'] in ['raise', 'call']
        
    def test_analyze_postflop_action(self):
        """Test analyzing postflop action."""
        analyzer = GameAnalyzer()
        
        action_data = {
            'hole_cards': [Card(Suit.HEARTS, Rank.ACE), Card(Suit.SPADES, Rank.KING)],
            'community_cards': [
                Card(Suit.DIAMONDS, Rank.ACE),
                Card(Suit.CLUBS, Rank.SEVEN),
                Card(Suit.HEARTS, Rank.TWO)
            ],
            'action': 'bet',
            'amount': 75,
            'pot_size_before': 150,
            'players_in_hand': 3,
            'position': 5
        }
        
        analysis = analyzer.analyze_postflop_action(action_data)
        
        assert 'hand_strength' in analysis
        assert 'board_texture' in analysis
        assert 'pot_odds' in analysis
        assert 'equity' in analysis
        
    def test_analyze_betting_patterns(self):
        """Test analyzing betting patterns."""
        analyzer = GameAnalyzer()
        
        # Simulate betting sequence
        betting_sequence = [
            {'player': 'Player1', 'action': 'raise', 'amount': 50},
            {'player': 'Player2', 'action': 'call', 'amount': 50},
            {'player': 'Player3', 'action': 'raise', 'amount': 150},
            {'player': 'Player1', 'action': 'fold', 'amount': 0}
        ]
        
        patterns = analyzer.analyze_betting_patterns(betting_sequence)
        
        assert 'aggression_levels' in patterns
        assert 'fold_frequency' in patterns
        assert 'bet_sizing' in patterns
        

class TestPlayerAnalyzer:
    """Test cases for PlayerAnalyzer."""
    
    def test_calculate_vpip(self):
        """Test calculating VPIP (Voluntarily Put $ In Pot)."""
        analyzer = PlayerAnalyzer()
        
        # Player stats: played 100 hands, voluntarily put money in 25 times
        vpip = analyzer.calculate_vpip(hands_played=100, voluntary_hands=25)
        
        assert vpip == 0.25  # 25%
        
    def test_calculate_pfr(self):
        """Test calculating PFR (Preflop Raise)."""
        analyzer = PlayerAnalyzer()
        
        # Player raised preflop 15 times out of 100 hands
        pfr = analyzer.calculate_pfr(hands_played=100, preflop_raises=15)
        
        assert pfr == 0.15  # 15%
        
    def test_calculate_aggression_factor(self):
        """Test calculating aggression factor."""
        analyzer = PlayerAnalyzer()
        
        # (Bets + Raises) / Calls
        aggression = analyzer.calculate_aggression_factor(
            bets=20, raises=10, calls=15
        )
        
        expected_af = (20 + 10) / 15  # 2.0
        assert abs(aggression - expected_af) < 0.01
        
    def test_calculate_fold_to_cbet(self):
        """Test calculating fold to continuation bet frequency."""
        analyzer = PlayerAnalyzer()
        
        fold_to_cbet = analyzer.calculate_fold_to_cbet(
            cbet_opportunities=50, folds_to_cbet=35
        )
        
        assert fold_to_cbet == 0.7  # 70%
        
    def test_analyze_positional_play(self):
        """Test analyzing player's positional tendencies."""
        analyzer = PlayerAnalyzer()
        
        position_data = {
            'early_position': {'hands': 30, 'vpip': 12, 'pfr': 8},
            'middle_position': {'hands': 35, 'vpip': 18, 'pfr': 12},
            'late_position': {'hands': 35, 'vpip': 28, 'pfr': 18}
        }
        
        analysis = analyzer.analyze_positional_play(position_data)
        
        assert 'early_position_vpip' in analysis
        assert 'positional_awareness' in analysis
        
        # Should show increasing VPIP from early to late position
        assert analysis['early_position_vpip'] < analysis['late_position_vpip']
        
    def test_player_type_classification(self):
        """Test classifying player type based on stats."""
        analyzer = PlayerAnalyzer()
        
        # Tight-aggressive player stats
        stats = {
            'vpip': 0.18,  # 18%
            'pfr': 0.15,   # 15%
            'aggression_factor': 3.2,
            'fold_to_cbet': 0.65
        }
        
        player_type = analyzer.classify_player_type(stats)
        
        # Should classify as TAG (Tight-Aggressive)
        assert 'tight' in player_type.lower()
        assert 'aggressive' in player_type.lower()
        
    def test_winrate_calculation(self):
        """Test calculating various win rates."""
        analyzer = PlayerAnalyzer()
        
        # Sample data
        total_hands = 1000
        hands_won = 180
        total_invested = 50000  # chips
        total_winnings = 52500  # chips
        
        hand_winrate = analyzer.calculate_hand_winrate(hands_won, total_hands)
        bb_winrate = analyzer.calculate_bb_winrate(
            total_winnings - total_invested, total_hands, big_blind=10
        )
        
        assert hand_winrate == 0.18  # 18%
        expected_bb_per_100 = ((52500 - 50000) / total_hands) * 100 / 10
        assert abs(bb_winrate - expected_bb_per_100) < 0.01
