"""
Test suite for Training Mode features.
Tests interactive poker education, quizzes, and analysis systems.
"""
import pytest
from unittest.mock import Mock, patch
from src.training.trainer import PokerTrainer, QuizType
from src.training.analyzer import HandAnalyzer, SessionReviewer
from src.training.hud import TrainerHUD
from src.game.player import Player, PlayerAction
from src.game.card import Card, Suit, Rank
from src.game.pot import Pot


class TestPokerTrainer:
    """Test cases for PokerTrainer class."""
    
    def test_trainer_creation(self):
        """Test creating a poker trainer."""
        trainer = PokerTrainer()
        
        assert trainer.training_enabled is False
        assert trainer.quiz_frequency > 0
        assert len(trainer.quiz_types) > 0
        
    def test_enable_training_mode(self):
        """Test enabling training mode."""
        trainer = PokerTrainer()
        
        trainer.enable_training()
        
        assert trainer.training_enabled is True
        
    def test_disable_training_mode(self):
        """Test disabling training mode."""
        trainer = PokerTrainer()
        trainer.enable_training()
        
        trainer.disable_training()
        
        assert trainer.training_enabled is False
        
    def test_should_trigger_quiz(self):
        """Test quiz triggering logic."""
        trainer = PokerTrainer()
        trainer.enable_training()
        
        # Should trigger quiz eventually
        triggered = False
        for _ in range(100):  # Try multiple times
            if trainer.should_trigger_quiz():
                triggered = True
                break
                
        assert triggered  # Should trigger at some point
        
    def test_generate_pot_odds_quiz(self):
        """Test generating pot odds quiz."""
        trainer = PokerTrainer()
        pot_size = 200
        bet_to_call = 50
        
        quiz = trainer.generate_quiz(QuizType.POT_ODDS, pot_size=pot_size, bet_to_call=bet_to_call)
        
        assert quiz is not None
        assert 'question' in quiz
        assert 'correct_answer' in quiz
        assert 'explanation' in quiz
        assert quiz['correct_answer'] == 0.2  # 50/(200+50)
        
    def test_generate_equity_quiz(self):
        """Test generating equity requirement quiz."""
        trainer = PokerTrainer()
        
        quiz = trainer.generate_quiz(QuizType.REQUIRED_EQUITY, pot_size=150, bet_to_call=30)
        
        assert quiz is not None
        assert quiz['correct_answer'] == 30 / (150 + 30)  # Required equity
        
    def test_evaluate_user_answer(self):
        """Test evaluating user quiz answers."""
        trainer = PokerTrainer()
        
        # Correct answer
        result = trainer.evaluate_answer(0.2, 0.2, tolerance=0.01)
        assert result['correct'] is True
        
        # Close answer (within tolerance)
        result = trainer.evaluate_answer(0.2, 0.195, tolerance=0.01)
        assert result['correct'] is True
        
        # Incorrect answer
        result = trainer.evaluate_answer(0.2, 0.3, tolerance=0.01)
        assert result['correct'] is False
        
    def test_quiz_difficulty_adjustment(self):
        """Test quiz difficulty adjustment based on performance."""
        trainer = PokerTrainer()
        
        # Simulate correct answers
        for _ in range(5):
            trainer.record_quiz_result(True)
            
        assert trainer.current_difficulty > trainer.base_difficulty
        
        # Simulate incorrect answers
        for _ in range(5):
            trainer.record_quiz_result(False)
            
        assert trainer.current_difficulty < trainer.base_difficulty


class TestHandAnalyzer:
    """Test cases for HandAnalyzer class."""
    
    def test_analyzer_creation(self):
        """Test creating a hand analyzer."""
        analyzer = HandAnalyzer()
        
        assert analyzer is not None
        
    def test_analyze_decision_pot_odds(self):
        """Test analyzing decision based on pot odds."""
        analyzer = HandAnalyzer()
        
        analysis = analyzer.analyze_decision(
            action=PlayerAction.CALL,
            pot_size=100,
            bet_to_call=25,
            hand_equity=0.3,
            opponent_type="tight-aggressive"
        )
        
        assert 'pot_odds' in analysis
        assert 'required_equity' in analysis
        assert 'recommendation' in analysis
        assert 'reasoning' in analysis
        
        # With 30% equity vs 20% required, call should be recommended
        assert analysis['recommendation'] == 'call'
        
    def test_analyze_decision_insufficient_equity(self):
        """Test analyzing decision with insufficient equity."""
        analyzer = HandAnalyzer()
        
        analysis = analyzer.analyze_decision(
            action=PlayerAction.CALL,
            pot_size=100,
            bet_to_call=50,
            hand_equity=0.2,
            opponent_type="loose-passive"
        )
        
        # With 20% equity vs 33% required, fold should be recommended
        assert analysis['recommendation'] == 'fold'
        assert 'unprofitable' in analysis['reasoning'].lower()
        
    def test_analyze_bluff_against_opponent_type(self):
        """Test analyzing bluff attempts against different opponent types."""
        analyzer = HandAnalyzer()
        
        # Bluff against tight player - should be good
        analysis = analyzer.analyze_bluff(
            bet_size=75,
            pot_size=100,
            opponent_type="tight-passive",
            board_texture="dry"
        )
        
        assert 'fold_frequency' in analysis
        assert analysis['profitability'] is True  # Should be profitable
        
        # Bluff against loose player - should be bad
        analysis = analyzer.analyze_bluff(
            bet_size=75,
            pot_size=100,
            opponent_type="loose-aggressive",
            board_texture="wet"
        )
        
        assert analysis['profitability'] is False  # Should be unprofitable
        
    def test_generate_post_hand_feedback(self):
        """Test generating comprehensive post-hand feedback."""
        analyzer = HandAnalyzer()
        
        hand_data = {
            'actions': [
                {'player': 'User', 'action': 'raise', 'amount': 50, 'pot_before': 30},
                {'player': 'AI_1', 'action': 'call', 'amount': 50, 'pot_before': 80}
            ],
            'final_pot': 130,
            'winner': 'AI_1',
            'user_hand_strength': 0.7,
            'opponent_stats': {'AI_1': {'vpip': 0.15, 'pfr': 0.05, 'type': 'tight-passive'}}
        }
        
        feedback = analyzer.generate_post_hand_feedback(hand_data)
        
        assert 'summary' in feedback
        assert 'key_decisions' in feedback
        assert 'opponent_analysis' in feedback
        assert 'learning_points' in feedback


class TestSessionReviewer:
    """Test cases for SessionReviewer class."""
    
    def test_reviewer_creation(self):
        """Test creating a session reviewer."""
        reviewer = SessionReviewer()
        
        assert reviewer is not None
        
    def test_analyze_positional_stats(self):
        """Test analyzing positional play statistics."""
        reviewer = SessionReviewer()
        
        session_data = {
            'early_position': {'hands': 20, 'vpip': 7, 'pfr': 4},
            'middle_position': {'hands': 25, 'vpip': 12, 'pfr': 8},
            'late_position': {'hands': 30, 'vpip': 18, 'pfr': 12}
        }
        
        analysis = reviewer.analyze_positional_play(session_data)
        
        assert 'early_position_vpip' in analysis
        assert 'position_awareness' in analysis
        assert 'recommendations' in analysis
        
        # Should show increasing VPIP from early to late position
        assert analysis['early_position_vpip'] < analysis['late_position_vpip']
        
    def test_identify_statistical_leaks(self):
        """Test identifying common statistical leaks."""
        reviewer = SessionReviewer()
        
        stats = {
            'overall_vpip': 0.45,  # Too high
            'early_position_vpip': 0.35,  # Way too high
            'aggression_factor': 0.8,  # Too passive
            'fold_to_cbet': 0.8,  # Too high
            'pfr': 0.05  # Too low
        }
        
        leaks = reviewer.identify_leaks(stats)
        
        assert 'vpip_too_high' in [leak['type'] for leak in leaks]
        assert 'too_passive' in [leak['type'] for leak in leaks]
        assert len(leaks) > 0
        
    def test_generate_improvement_suggestions(self):
        """Test generating actionable improvement suggestions."""
        reviewer = SessionReviewer()
        
        leaks = [
            {'type': 'vpip_too_high', 'severity': 'high', 'value': 0.45},
            {'type': 'too_passive', 'severity': 'medium', 'value': 0.8}
        ]
        
        suggestions = reviewer.generate_suggestions(leaks)
        
        assert len(suggestions) > 0
        assert all('action' in suggestion for suggestion in suggestions)
        assert all('reason' in suggestion for suggestion in suggestions)
        
    def test_generate_session_report(self):
        """Test generating comprehensive session report."""
        reviewer = SessionReviewer()
        
        session_data = {
            'hands_played': 100,
            'vpip': 0.25,
            'pfr': 0.18,
            'aggression_factor': 2.1,
            'net_result': 150,
            'biggest_pot_won': 85,
            'position_stats': {
                'early_position': {'hands': 30, 'vpip': 8, 'pfr': 5},
                'late_position': {'hands': 35, 'vpip': 15, 'pfr': 12}
            }
        }
        
        report = reviewer.generate_session_report(session_data)
        
        assert 'session_summary' in report
        assert 'statistical_analysis' in report
        assert 'identified_leaks' in report
        assert 'recommendations' in report
        assert 'overall_grade' in report


class TestTrainerHUD:
    """Test cases for TrainerHUD (Heads-Up Display)."""
    
    def test_hud_creation(self):
        """Test creating trainer HUD."""
        hud = TrainerHUD()
        
        assert hud.is_enabled is False
        assert hud.display_mode == 'basic'
        
    def test_enable_hud(self):
        """Test enabling HUD display."""
        hud = TrainerHUD()
        
        hud.enable()
        
        assert hud.is_enabled is True
        
    def test_update_opponent_stats(self):
        """Test updating opponent statistics display."""
        hud = TrainerHUD()
        hud.enable()
        
        opponent_stats = {
            'AI_1': {'vpip': 0.22, 'pfr': 0.18, 'af': 2.1, 'type': 'balanced'},
            'AI_2': {'vpip': 0.45, 'pfr': 0.05, 'af': 0.8, 'type': 'loose-passive'}
        }
        
        hud.update_opponent_stats(opponent_stats)
        
        assert len(hud.opponent_data) == 2
        assert 'AI_1' in hud.opponent_data
        assert hud.opponent_data['AI_1']['type'] == 'balanced'
        
    def test_format_opponent_display(self):
        """Test formatting opponent stats for display."""
        hud = TrainerHUD()
        
        stats = {'vpip': 0.22, 'pfr': 0.18, 'af': 2.1, 'type': 'tight-aggressive'}
        
        display_text = hud.format_opponent_display('AI_1', stats)
        
        assert 'AI_1' in display_text
        assert '22%' in display_text  # VPIP
        assert '18%' in display_text  # PFR
        assert '2.1' in display_text  # AF
        assert 'tight-aggressive' in display_text.lower()
        
    def test_generate_pot_odds_display(self):
        """Test generating pot odds information display."""
        hud = TrainerHUD()
        
        display = hud.generate_pot_odds_display(pot_size=150, bet_to_call=50)
        
        assert 'pot odds' in display.lower()
        assert '25.0%' in display or '3.0:1' in display  # 50/(150+50) = 25%, 150/50 = 3:1
        
    def test_generate_equity_display(self):
        """Test generating hand equity display."""
        hud = TrainerHUD()
        
        display = hud.generate_equity_display(hand_equity=0.35, required_equity=0.25)
        
        assert '35.0%' in display  # Hand equity
        assert '25.0%' in display  # Required equity
        assert 'favorable' in display.lower() or 'good' in display.lower()


class TestTrainingIntegration:
    """Integration tests for training system components."""
    
    def test_training_workflow(self):
        """Test complete training workflow."""
        trainer = PokerTrainer()
        analyzer = HandAnalyzer()
        hud = TrainerHUD()
        
        # Enable training
        trainer.enable_training()
        hud.enable()
        
        # Simulate decision point
        if trainer.should_trigger_quiz():
            quiz = trainer.generate_quiz(QuizType.POT_ODDS, pot_size=100, bet_to_call=25)
            
            # Simulate user answer
            user_answer = 0.25  # 25/(100+25) = 0.25
            result = trainer.evaluate_answer(quiz['correct_answer'], user_answer)
            
            assert result['correct'] is True
            
        # Analyze decision
        analysis = analyzer.analyze_decision(
            action=PlayerAction.CALL,
            pot_size=100,
            bet_to_call=25,
            hand_equity=0.3,
            opponent_type="tight-aggressive"
        )
        
        assert analysis['recommendation'] == 'call'
        
    def test_educational_content_loading(self):
        """Test loading educational content and tips."""
        from src.training.content_loader import ContentLoader
        
        loader = ContentLoader()
        
        # Should load various educational content
        poker_tips = loader.load_tips()
        poker_vocab = loader.load_vocabulary()
        strategy_guides = loader.load_strategy_guides()
        
        assert len(poker_tips) > 0
        assert len(poker_vocab) > 0
        assert len(strategy_guides) > 0
        
        # Content should have proper structure
        assert all('title' in tip for tip in poker_tips)
        assert all('definition' in word for word in poker_vocab)
