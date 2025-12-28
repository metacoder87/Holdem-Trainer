"""
Test suite for Adaptive Training System.
Tests dynamic content integration, career tracking, and personalized training.
"""
import pytest
from datetime import datetime, timedelta
from training.adaptive_trainer import AdaptiveTrainer, SkillLevel, WeaknessType
from training.career_tracker import CareerTracker, CareerMetrics
from training.progression_analyzer import ProgressionAnalyzer, TrendDirection
from training.content_loader import ContentLoader
from game.player import Player


class TestCareerTracker:
    """Test cases for long-term career tracking."""
    
    def test_career_tracker_creation(self):
        """Test creating a career tracker."""
        tracker = CareerTracker("TestPlayer")
        assert tracker.player_name == "TestPlayer"
        assert tracker.total_hands == 0
        assert len(tracker.sessions) == 0
        
    def test_record_session(self):
        """Test recording a gameplay session."""
        tracker = CareerTracker("TestPlayer")
        
        session_data = {
            'hands_played': 50,
            'vpip': 0.25,
            'pfr': 0.18,
            'aggression_factor': 2.5,
            'winrate': 0.15,
            'profit': 500
        }
        
        tracker.record_session(session_data)
        
        assert tracker.total_hands == 50
        assert len(tracker.sessions) == 1
        assert tracker.sessions[0]['vpip'] == 0.25
        
    def test_get_career_metrics(self):
        """Test retrieving overall career metrics."""
        tracker = CareerTracker("TestPlayer")
        
        # Record multiple sessions
        for i in range(5):
            session_data = {
                'hands_played': 50,
                'vpip': 0.25 + (i * 0.01),
                'pfr': 0.18,
                'aggression_factor': 2.5,
                'winrate': 0.15,
                'profit': 100
            }
            tracker.record_session(session_data)
            
        metrics = tracker.get_career_metrics()
        
        assert metrics.total_hands == 250
        assert metrics.avg_vpip > 0
        assert metrics.avg_pfr > 0
        assert metrics.total_profit == 500
        
    def test_get_trend_analysis(self):
        """Test analyzing trends over time."""
        tracker = CareerTracker("TestPlayer")
        
        # Simulate improving VPIP over time
        for i in range(10):
            session_data = {
                'hands_played': 50,
                'vpip': 0.35 - (i * 0.01),  # Decreasing from 0.35 to 0.26
                'pfr': 0.18,
                'aggression_factor': 2.5,
                'winrate': 0.15,
                'profit': 100
            }
            tracker.record_session(session_data)
            
        trends = tracker.get_trend_analysis('vpip', window=5)
        
        assert trends['direction'] == 'decreasing'
        assert trends['change'] < 0
        
    def test_get_recent_sessions(self):
        """Test retrieving recent sessions."""
        tracker = CareerTracker("TestPlayer")
        
        for i in range(10):
            session_data = {
                'hands_played': 50,
                'vpip': 0.25,
                'pfr': 0.18,
                'aggression_factor': 2.5,
                'winrate': 0.15,
                'profit': 100
            }
            tracker.record_session(session_data)
            
        recent = tracker.get_recent_sessions(count=3)
        
        assert len(recent) == 3
        
    def test_career_report_generation(self):
        """Test generating comprehensive career report."""
        tracker = CareerTracker("TestPlayer")
        
        for i in range(20):
            session_data = {
                'hands_played': 100,
                'vpip': 0.25,
                'pfr': 0.18,
                'aggression_factor': 2.0 + (i * 0.1),
                'winrate': 0.15,
                'profit': 200
            }
            tracker.record_session(session_data)
            
        report = tracker.generate_career_report()
        
        assert 'total_hands' in report
        assert 'career_metrics' in report
        assert 'trends' in report
        assert 'milestones' in report


class TestProgressionAnalyzer:
    """Test cases for skill progression analysis."""
    
    def test_progression_analyzer_creation(self):
        """Test creating a progression analyzer."""
        analyzer = ProgressionAnalyzer()
        assert analyzer is not None
        
    def test_determine_skill_level(self):
        """Test determining player skill level."""
        analyzer = ProgressionAnalyzer()
        
        # Beginner metrics
        beginner_metrics = {
            'vpip': 0.45,  # Too loose
            'pfr': 0.10,   # Too passive
            'aggression_factor': 1.0,
            'total_hands': 100
        }
        
        level = analyzer.determine_skill_level(beginner_metrics)
        assert level == SkillLevel.BEGINNER
        
        # Advanced metrics
        advanced_metrics = {
            'vpip': 0.23,
            'pfr': 0.18,
            'aggression_factor': 2.8,
            'total_hands': 5000
        }
        
        level = analyzer.determine_skill_level(advanced_metrics)
        assert level in [SkillLevel.ADVANCED, SkillLevel.EXPERT, SkillLevel.MASTER]
        
    def test_identify_weaknesses(self):
        """Test identifying specific weaknesses."""
        analyzer = ProgressionAnalyzer()
        
        metrics = {
            'vpip': 0.45,  # Too loose
            'pfr': 0.10,   # Too passive
            'aggression_factor': 0.8,  # Not aggressive enough
            'fold_to_3bet': 0.75,  # Folding too much to 3-bets
        }
        
        weaknesses = analyzer.identify_weaknesses(metrics)
        
        assert WeaknessType.TOO_LOOSE in weaknesses
        assert WeaknessType.TOO_PASSIVE in weaknesses
        
    def test_suggest_study_topics(self):
        """Test suggesting appropriate study topics."""
        analyzer = ProgressionAnalyzer()
        
        weaknesses = [WeaknessType.TOO_LOOSE, WeaknessType.POOR_POT_ODDS]
        
        topics = analyzer.suggest_study_topics(weaknesses)
        
        assert 'preflop_hand_selection' in topics
        assert 'pot_odds_calculation' in topics
        
    def test_calculate_improvement_rate(self):
        """Test calculating rate of improvement."""
        analyzer = ProgressionAnalyzer()
        
        base_time = datetime.now()
        sessions = [
            {'vpip': 0.40, 'timestamp': base_time - timedelta(days=30)},
            {'vpip': 0.35, 'timestamp': base_time - timedelta(days=20)},
            {'vpip': 0.30, 'timestamp': base_time - timedelta(days=10)},
            {'vpip': 0.27, 'timestamp': base_time},
        ]
        
        rate = analyzer.calculate_improvement_rate(sessions, 'vpip')
        
        # VPIP is decreasing (0.40 -> 0.27), after inversion rate should be positive (improvement)
        assert rate > 0  # Positive rate = improvement for VPIP
        
    def test_predict_mastery_timeline(self):
        """Test predicting time to reach mastery."""
        analyzer = ProgressionAnalyzer()
        
        metrics = {
            'vpip': 0.30,
            'pfr': 0.15,
            'aggression_factor': 1.8,
            'total_hands': 1000
        }
        
        improvement_rate = -0.01  # Improving
        
        timeline = analyzer.predict_mastery_timeline(metrics, improvement_rate)
        
        assert 'estimated_hands' in timeline
        assert 'estimated_days' in timeline
        assert 'current_level' in timeline


class TestAdaptiveTrainer:
    """Test cases for adaptive training system."""
    
    def test_adaptive_trainer_creation(self):
        """Test creating an adaptive trainer."""
        trainer = AdaptiveTrainer("TestPlayer")
        assert trainer.player_name == "TestPlayer"
        assert trainer.content_loader is not None
        
    def test_configure_from_weaknesses(self):
        """Test configuring training based on identified weaknesses."""
        trainer = AdaptiveTrainer("TestPlayer")
        
        weaknesses = [WeaknessType.TOO_PASSIVE, WeaknessType.POOR_POT_ODDS]
        
        config = trainer.configure_from_weaknesses(weaknesses)
        
        assert 'focus_areas' in config
        assert 'quiz_distribution' in config
        assert 'pot_odds' in config['focus_areas']
        assert 'aggression' in config['focus_areas']
        
    def test_generate_targeted_quiz(self):
        """Test generating quiz targeted at specific weakness."""
        trainer = AdaptiveTrainer("TestPlayer")
        
        quiz = trainer.generate_targeted_quiz(WeaknessType.POOR_POT_ODDS)
        
        assert quiz is not None
        assert 'question' in quiz
        assert 'correct_answer' in quiz
        assert 'explanation' in quiz
        
    def test_adjust_difficulty(self):
        """Test adjusting difficulty based on performance."""
        trainer = AdaptiveTrainer("TestPlayer")
        
        # Simulate high performance
        performance_data = {
            'correct_answers': 9,
            'total_questions': 10,
            'avg_response_time': 15
        }
        
        trainer.adjust_difficulty(performance_data)
        
        assert trainer.current_difficulty > 1  # Should increase
        
    def test_create_practice_scenario(self):
        """Test creating practice scenarios for specific situations."""
        trainer = AdaptiveTrainer("TestPlayer")
        
        scenario = trainer.create_practice_scenario(WeaknessType.TOO_PASSIVE)
        
        assert 'situation' in scenario
        assert 'pot_size' in scenario
        assert 'recommended_actions' in scenario
        
    def test_track_practice_results(self):
        """Test tracking results of practice sessions."""
        trainer = AdaptiveTrainer("TestPlayer")
        
        practice_result = {
            'weakness_type': WeaknessType.POOR_POT_ODDS,
            'correct': True,
            'time_taken': 20
        }
        
        trainer.track_practice_result(practice_result)
        
        stats = trainer.get_practice_statistics()
        
        assert len(stats['completed_exercises']) > 0
        
    def test_generate_personalized_curriculum(self):
        """Test generating personalized learning path."""
        trainer = AdaptiveTrainer("TestPlayer")
        
        weaknesses = [
            WeaknessType.TOO_LOOSE,
            WeaknessType.POOR_POT_ODDS,
            WeaknessType.TOO_PASSIVE
        ]
        
        curriculum = trainer.generate_personalized_curriculum(weaknesses)
        
        assert 'modules' in curriculum
        assert 'estimated_duration' in curriculum
        assert len(curriculum['modules']) > 0


class TestDynamicContentIntegration:
    """Test cases for dynamic educational content integration."""
    
    def test_get_contextual_content(self):
        """Test retrieving context-aware educational content."""
        loader = ContentLoader()
        
        context = {
            'situation': 'facing_bet',
            'pot_odds': 3.0,
            'hand_strength': 'draw',
            'weakness': WeaknessType.POOR_POT_ODDS
        }
        
        content = loader.get_contextual_content(context)
        
        assert content is not None
        assert 'explanation' in content
        assert 'reference' in content
        
    def test_extract_relevant_quote(self):
        """Test extracting relevant quote from educational content."""
        loader = ContentLoader()
        
        topic = 'pot_odds'
        situation = 'drawing_hand'
        
        quote = loader.extract_relevant_quote(topic, situation)
        
        assert quote is not None
        assert len(quote) > 0
        
    def test_link_mistake_to_content(self):
        """Test linking identified mistake to educational material."""
        loader = ContentLoader()
        
        mistake = {
            'type': 'poor_call',
            'pot_odds_required': 3.5,
            'pot_odds_actual': 2.0,
            'action_taken': 'call'
        }
        
        content = loader.link_mistake_to_content(mistake)
        
        assert 'explanation' in content
        assert 'relevant_section' in content
        assert 'study_recommendation' in content
        
    def test_generate_inline_tip(self):
        """Test generating inline tips during gameplay."""
        loader = ContentLoader()
        
        game_state = {
            'pot_size': 100,
            'bet_to_call': 30,
            'hand_strength': 'medium',
            'position': 'button'
        }
        
        tip = loader.generate_inline_tip(game_state)
        
        assert tip is not None
        assert 'message' in tip
        assert 'source' in tip


class TestIntegratedFeedbackLoop:
    """Test cases for integrated feedback and training loop."""
    
    def test_feedback_to_training_pipeline(self):
        """Test complete pipeline from feedback to training."""
        # Create components
        tracker = CareerTracker("TestPlayer")
        analyzer = ProgressionAnalyzer()
        trainer = AdaptiveTrainer("TestPlayer")
        
        # Record session with weaknesses
        session_data = {
            'hands_played': 100,
            'vpip': 0.45,  # Too loose
            'pfr': 0.10,   # Too passive
            'aggression_factor': 1.0,
            'winrate': 0.05,
            'profit': -100
        }
        
        tracker.record_session(session_data)
        
        # Analyze for weaknesses
        metrics = tracker.get_career_metrics()
        weaknesses = analyzer.identify_weaknesses(metrics.to_dict())
        
        # Configure training
        config = trainer.configure_from_weaknesses(weaknesses)
        
        assert len(config['focus_areas']) > 0
        assert WeaknessType.TOO_LOOSE in weaknesses or WeaknessType.TOO_PASSIVE in weaknesses
        
    def test_continuous_improvement_cycle(self):
        """Test continuous cycle of play, review, practice."""
        tracker = CareerTracker("TestPlayer")
        analyzer = ProgressionAnalyzer()
        trainer = AdaptiveTrainer("TestPlayer")
        
        # Simulate multiple cycles
        for cycle in range(3):
            # Play session
            session_data = {
                'hands_played': 100,
                'vpip': 0.40 - (cycle * 0.05),  # Improving
                'pfr': 0.15 + (cycle * 0.02),   # Improving
                'aggression_factor': 1.5 + (cycle * 0.3),
                'winrate': 0.10 + (cycle * 0.05),
                'profit': 50 + (cycle * 50)
            }
            
            tracker.record_session(session_data)
            
            # Analyze
            metrics = tracker.get_career_metrics()
            weaknesses = analyzer.identify_weaknesses(metrics.to_dict())
            
            # Train
            trainer.configure_from_weaknesses(weaknesses)
            
        # Check improvement
        final_metrics = tracker.get_career_metrics()
        assert final_metrics.total_hands == 300
        
        # VPIP should have improved (decreased)
        first_session = tracker.sessions[0]
        last_session = tracker.sessions[-1]
        assert last_session['vpip'] < first_session['vpip']
        
    def test_long_term_progression_tracking(self):
        """Test tracking progression over many sessions."""
        tracker = CareerTracker("TestPlayer")
        
        # Simulate 50 sessions over time
        for i in range(50):
            session_data = {
                'hands_played': 100,
                'vpip': max(0.22, 0.40 - (i * 0.004)),  # Gradual improvement
                'pfr': min(0.20, 0.12 + (i * 0.002)),   # Gradual improvement
                'aggression_factor': min(3.0, 1.5 + (i * 0.03)),
                'winrate': min(0.20, 0.05 + (i * 0.003)),
                'profit': 100 + (i * 20)
            }
            tracker.record_session(session_data)
            
        report = tracker.generate_career_report()
        
        assert report['total_hands'] == 5000
        assert 'skill_progression' in report
        
        # Check trends show improvement
        vpip_trend = tracker.get_trend_analysis('vpip', window=10)
        assert vpip_trend['direction'] == 'decreasing'  # Improving


class TestCareerReporting:
    """Test cases for career report generation."""
    
    def test_milestone_detection(self):
        """Test detecting achievement milestones."""
        tracker = CareerTracker("TestPlayer")
        
        # Reach 1000 hands milestone
        for i in range(10):
            session_data = {
                'hands_played': 100,
                'vpip': 0.25,
                'pfr': 0.18,
                'aggression_factor': 2.5,
                'winrate': 0.15,
                'profit': 200
            }
            tracker.record_session(session_data)
            
        milestones = tracker.get_milestones()
        
        assert '1000_hands' in [m['type'] for m in milestones]
        
    def test_skill_level_evolution(self):
        """Test tracking skill level changes over time."""
        tracker = CareerTracker("TestPlayer")
        analyzer = ProgressionAnalyzer()
        
        skill_levels = []
        
        for i in range(20):
            session_data = {
                'hands_played': 200,
                'vpip': max(0.23, 0.40 - (i * 0.01)),
                'pfr': min(0.19, 0.12 + (i * 0.005)),
                'aggression_factor': min(2.8, 1.5 + (i * 0.08)),
                'winrate': 0.15,
                'profit': 300
            }
            tracker.record_session(session_data)
            
            # Track skill level after each session
            metrics = tracker.get_career_metrics()
            level = analyzer.determine_skill_level(metrics.to_dict())
            skill_levels.append(level)
            
        # Should show progression
        assert skill_levels[-1].value >= skill_levels[0].value
        
    def test_generate_progress_visualization_data(self):
        """Test generating data for progress visualization."""
        tracker = CareerTracker("TestPlayer")
        
        for i in range(30):
            session_data = {
                'hands_played': 100,
                'vpip': 0.25,
                'pfr': 0.18,
                'aggression_factor': 2.5,
                'winrate': 0.15,
                'profit': 150
            }
            tracker.record_session(session_data)
            
        viz_data = tracker.get_visualization_data()
        
        assert 'vpip_over_time' in viz_data
        assert 'pfr_over_time' in viz_data
        assert 'profit_over_time' in viz_data
        assert len(viz_data['vpip_over_time']) == 30
