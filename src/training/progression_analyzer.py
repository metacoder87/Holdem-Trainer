"""
Progression Analyzer module for skill level assessment and improvement tracking.
Identifies weaknesses, suggests study topics, and predicts progression timeline.
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import statistics


class SkillLevel(Enum):
    """Player skill level classification."""
    BEGINNER = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    EXPERT = 4
    MASTER = 5


class WeaknessType(Enum):
    """Types of poker weaknesses that can be identified."""
    TOO_LOOSE = "too_loose"  # VPIP too high
    TOO_TIGHT = "too_tight"  # VPIP too low
    TOO_PASSIVE = "too_passive"  # PFR too low
    TOO_AGGRESSIVE = "too_aggressive"  # Aggression too high
    POOR_POT_ODDS = "poor_pot_odds"  # Not using pot odds correctly
    POOR_POSITION_PLAY = "poor_position_play"  # Not adjusting for position
    WEAK_3BET_DEFENSE = "weak_3bet_defense"  # Folding too much to 3-bets
    POOR_BET_SIZING = "poor_bet_sizing"  # Inconsistent or poor bet sizes
    TILT_PRONE = "tilt_prone"  # Performance drops after losses


class TrendDirection(Enum):
    """Direction of performance trend."""
    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"


class ProgressionAnalyzer:
    """
    Analyzes player progression and identifies areas for improvement.
    Determines skill levels and suggests personalized study topics.
    """
    
    def __init__(self):
        """Initialize the progression analyzer."""
        # Optimal ranges for different metrics (for no-limit hold'em)
        self.optimal_ranges = {
            'vpip': (0.20, 0.28),
            'pfr': (0.15, 0.22),
            'aggression_factor': (2.0, 3.5),
            'fold_to_3bet': (0.55, 0.70),
            'cbet_flop': (0.60, 0.75)
        }
        
    def determine_skill_level(self, metrics: Dict[str, Any]) -> SkillLevel:
        """
        Determine player's current skill level based on metrics.
        
        Args:
            metrics: Dictionary of player statistics
            
        Returns:
            SkillLevel enum value
        """
        total_hands = metrics.get('total_hands', 0)
        vpip = metrics.get('vpip', 0)
        pfr = metrics.get('pfr', 0)
        agg_factor = metrics.get('aggression_factor', 0)
        
        # Score based on how close to optimal ranges
        score = 0
        
        # VPIP score
        if self.optimal_ranges['vpip'][0] <= vpip <= self.optimal_ranges['vpip'][1]:
            score += 2
        elif abs(vpip - 0.24) < 0.10:  # Close to optimal
            score += 1
            
        # PFR score
        if self.optimal_ranges['pfr'][0] <= pfr <= self.optimal_ranges['pfr'][1]:
            score += 2
        elif abs(pfr - 0.18) < 0.08:
            score += 1
            
        # Aggression score
        if self.optimal_ranges['aggression_factor'][0] <= agg_factor <= self.optimal_ranges['aggression_factor'][1]:
            score += 2
        elif abs(agg_factor - 2.5) < 1.0:
            score += 1
            
        # Experience factor
        if total_hands >= 10000:
            score += 2
        elif total_hands >= 5000:
            score += 1
        elif total_hands >= 1000:
            score += 0.5
            
        # Determine level based on score
        if score >= 7:
            return SkillLevel.MASTER
        elif score >= 5.5:
            return SkillLevel.EXPERT
        elif score >= 4:
            return SkillLevel.ADVANCED
        elif score >= 2:
            return SkillLevel.INTERMEDIATE
        else:
            return SkillLevel.BEGINNER
            
    def identify_weaknesses(self, metrics: Dict[str, Any]) -> List[WeaknessType]:
        """
        Identify specific weaknesses based on metrics.
        
        Args:
            metrics: Dictionary of player statistics
            
        Returns:
            List of identified weakness types
        """
        weaknesses = []
        
        vpip = metrics.get('vpip', 0)
        pfr = metrics.get('pfr', 0)
        agg_factor = metrics.get('aggression_factor', 0)
        fold_to_3bet = metrics.get('fold_to_3bet', 0)
        
        # Check VPIP
        if vpip > self.optimal_ranges['vpip'][1] + 0.10:
            weaknesses.append(WeaknessType.TOO_LOOSE)
        elif vpip < self.optimal_ranges['vpip'][0] - 0.05:
            weaknesses.append(WeaknessType.TOO_TIGHT)
            
        # Check PFR
        if pfr < self.optimal_ranges['pfr'][0] - 0.05:
            weaknesses.append(WeaknessType.TOO_PASSIVE)
            
        # Check aggression
        if agg_factor < 1.5:
            weaknesses.append(WeaknessType.TOO_PASSIVE)
        elif agg_factor > 4.0:
            weaknesses.append(WeaknessType.TOO_AGGRESSIVE)
            
        # Check 3-bet defense
        if fold_to_3bet > 0.75:
            weaknesses.append(WeaknessType.WEAK_3BET_DEFENSE)
            
        # Check for pot odds understanding (if available)
        if 'pot_odds_accuracy' in metrics and metrics['pot_odds_accuracy'] < 0.60:
            weaknesses.append(WeaknessType.POOR_POT_ODDS)
            
        return weaknesses
        
    def suggest_study_topics(self, weaknesses: List[WeaknessType]) -> List[str]:
        """
        Suggest study topics based on identified weaknesses.
        
        Args:
            weaknesses: List of weakness types
            
        Returns:
            List of recommended study topics
        """
        topic_mapping = {
            WeaknessType.TOO_LOOSE: ['preflop_hand_selection', 'starting_hands', 'position_awareness'],
            WeaknessType.TOO_TIGHT: ['hand_ranges', 'profitable_situations', 'exploitative_play'],
            WeaknessType.TOO_PASSIVE: ['betting_for_value', 'aggression', 'bet_sizing'],
            WeaknessType.TOO_AGGRESSIVE: ['hand_selection', 'bankroll_management', 'risk_assessment'],
            WeaknessType.POOR_POT_ODDS: ['pot_odds_calculation', 'implied_odds', 'drawing_hands'],
            WeaknessType.POOR_POSITION_PLAY: ['positional_awareness', 'button_play', 'blind_defense'],
            WeaknessType.WEAK_3BET_DEFENSE: ['3bet_defense', 'hand_ranges', 'restealing'],
            WeaknessType.POOR_BET_SIZING: ['bet_sizing_strategy', 'value_betting', 'bluffing'],
            WeaknessType.TILT_PRONE: ['mental_game', 'emotional_control', 'bankroll_management']
        }
        
        topics = set()
        for weakness in weaknesses:
            topics.update(topic_mapping.get(weakness, []))
            
        return list(topics)
        
    def calculate_improvement_rate(self, sessions: List[Dict[str, Any]], metric: str) -> float:
        """
        Calculate rate of improvement for a specific metric.
        
        Args:
            sessions: List of session data with timestamps
            metric: Metric to analyze
            
        Returns:
            Improvement rate (positive = improving for most metrics)
        """
        if len(sessions) < 3:
            return 0.0
            
        # Sort by timestamp
        sorted_sessions = sorted(sessions, key=lambda x: x.get('timestamp', datetime.now()))
        
        # Get first and last values
        values = [s.get(metric, 0) for s in sorted_sessions if metric in s]
        
        if len(values) < 2:
            return 0.0
            
        # Calculate linear regression slope (simple version)
        n = len(values)
        x = list(range(n))
        y = values
        
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
            
        slope = numerator / denominator
        
        # For metrics like VPIP where lower is better, invert the slope
        if metric in ['vpip']:
            return -slope
            
        return slope
        
    def predict_mastery_timeline(self, metrics: Dict[str, Any], improvement_rate: float) -> Dict[str, Any]:
        """
        Predict timeline to reach mastery level.
        
        Args:
            metrics: Current player metrics
            improvement_rate: Rate of improvement per session
            
        Returns:
            Dictionary with timeline predictions
        """
        current_level = self.determine_skill_level(metrics)
        current_hands = metrics.get('total_hands', 0)
        
        # Estimate hands needed to reach each level
        level_requirements = {
            SkillLevel.BEGINNER: 0,
            SkillLevel.INTERMEDIATE: 1000,
            SkillLevel.ADVANCED: 5000,
            SkillLevel.EXPERT: 15000,
            SkillLevel.MASTER: 50000
        }
        
        # Calculate hands to next level
        next_level = SkillLevel(min(current_level.value + 1, 5))
        hands_to_next = level_requirements[next_level] - current_hands
        
        # Calculate hands to mastery
        hands_to_mastery = level_requirements[SkillLevel.MASTER] - current_hands
        
        # Estimate sessions (assuming 100 hands per session)
        hands_per_session = 100
        sessions_to_next = max(hands_to_next // hands_per_session, 0)
        sessions_to_mastery = max(hands_to_mastery // hands_per_session, 0)
        
        # Estimate days (assuming 1 session per day)
        return {
            'current_level': current_level.name,
            'next_level': next_level.name,
            'estimated_hands': hands_to_next,
            'estimated_sessions': sessions_to_next,
            'estimated_days': sessions_to_next,
            'hands_to_mastery': hands_to_mastery,
            'sessions_to_mastery': sessions_to_mastery,
            'improvement_rate': improvement_rate
        }
        
    def analyze_consistency(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze consistency of player performance.
        
        Args:
            sessions: List of session data
            
        Returns:
            Dictionary with consistency metrics
        """
        if len(sessions) < 5:
            return {'consistency': 'insufficient_data'}
            
        # Calculate standard deviation of key metrics
        vpip_values = [s.get('vpip', 0) for s in sessions if 'vpip' in s]
        profit_values = [s.get('profit', 0) for s in sessions if 'profit' in s]
        
        consistency_score = 0
        
        if vpip_values:
            vpip_std = statistics.stdev(vpip_values) if len(vpip_values) > 1 else 0
            # Lower std deviation = more consistent
            if vpip_std < 0.05:
                consistency_score += 2
            elif vpip_std < 0.10:
                consistency_score += 1
                
        if profit_values:
            profit_std = statistics.stdev(profit_values) if len(profit_values) > 1 else 0
            # Check profit consistency
            positive_sessions = sum(1 for p in profit_values if p > 0)
            win_rate = positive_sessions / len(profit_values)
            
            if win_rate > 0.60:
                consistency_score += 2
            elif win_rate > 0.50:
                consistency_score += 1
                
        consistency_level = 'high' if consistency_score >= 3 else ('medium' if consistency_score >= 2 else 'low')
        
        return {
            'consistency': consistency_level,
            'score': consistency_score,
            'vpip_std': statistics.stdev(vpip_values) if len(vpip_values) > 1 else 0,
            'profit_win_rate': sum(1 for p in profit_values if p > 0) / len(profit_values) if profit_values else 0
        }
