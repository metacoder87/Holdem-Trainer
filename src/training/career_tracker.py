"""
Career Tracker module for long-term player progression.
Tracks statistics across hundreds or thousands of hands to show improvement over time.
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import statistics


@dataclass
class CareerMetrics:
    """Aggregated career statistics."""
    total_hands: int
    total_sessions: int
    avg_vpip: float
    avg_pfr: float
    avg_aggression_factor: float
    avg_winrate: float
    total_profit: float
    best_session_profit: float
    worst_session_profit: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class CareerTracker:
    """
    Tracks player performance across multiple sessions for long-term analysis.
    Provides career statistics, trend analysis, and milestone tracking.
    """
    
    def __init__(self, player_name: str):
        """
        Initialize career tracker.
        
        Args:
            player_name: Name of the player being tracked
        """
        self.player_name = player_name
        self.sessions: List[Dict[str, Any]] = []
        self.total_hands = 0
        self.milestones_achieved: List[Dict[str, Any]] = []
        
    def record_session(self, session_data: Dict[str, Any]) -> None:
        """
        Record a gameplay session.
        
        Args:
            session_data: Dictionary containing session statistics
        """
        session_data['timestamp'] = datetime.now()
        session_data['session_number'] = len(self.sessions) + 1
        
        self.sessions.append(session_data)
        self.total_hands += session_data.get('hands_played', 0)
        
        # Check for milestones
        self._check_milestones()
        
    def get_career_metrics(self) -> CareerMetrics:
        """
        Get aggregated career statistics.
        
        Returns:
            CareerMetrics object with overall statistics
        """
        if not self.sessions:
            return CareerMetrics(
                total_hands=0,
                total_sessions=0,
                avg_vpip=0.0,
                avg_pfr=0.0,
                avg_aggression_factor=0.0,
                avg_winrate=0.0,
                total_profit=0.0,
                best_session_profit=0.0,
                worst_session_profit=0.0
            )
            
        # Calculate averages
        vpip_values = [s['vpip'] for s in self.sessions if 'vpip' in s]
        pfr_values = [s['pfr'] for s in self.sessions if 'pfr' in s]
        agg_values = [s['aggression_factor'] for s in self.sessions if 'aggression_factor' in s]
        winrate_values = [s.get('winrate', 0) for s in self.sessions]
        profit_values = [s.get('profit', 0) for s in self.sessions]
        
        return CareerMetrics(
            total_hands=self.total_hands,
            total_sessions=len(self.sessions),
            avg_vpip=statistics.mean(vpip_values) if vpip_values else 0.0,
            avg_pfr=statistics.mean(pfr_values) if pfr_values else 0.0,
            avg_aggression_factor=statistics.mean(agg_values) if agg_values else 0.0,
            avg_winrate=statistics.mean(winrate_values) if winrate_values else 0.0,
            total_profit=sum(profit_values),
            best_session_profit=max(profit_values) if profit_values else 0.0,
            worst_session_profit=min(profit_values) if profit_values else 0.0
        )
        
    def get_trend_analysis(self, metric: str, window: int = 10) -> Dict[str, Any]:
        """
        Analyze trend for a specific metric.
        
        Args:
            metric: The metric to analyze (e.g., 'vpip', 'pfr')
            window: Number of recent sessions to analyze
            
        Returns:
            Dictionary containing trend information
        """
        if len(self.sessions) < 2:
            return {'direction': 'insufficient_data', 'change': 0.0}
            
        recent_sessions = self.sessions[-window:]
        values = [s.get(metric, 0) for s in recent_sessions if metric in s]
        
        if len(values) < 2:
            return {'direction': 'insufficient_data', 'change': 0.0}
            
        # Calculate trend
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        
        avg_first = statistics.mean(first_half)
        avg_second = statistics.mean(second_half)
        
        change = avg_second - avg_first
        
        if abs(change) < 0.01:
            direction = 'stable'
        elif change > 0:
            direction = 'increasing'
        else:
            direction = 'decreasing'
            
        return {
            'direction': direction,
            'change': change,
            'recent_avg': avg_second,
            'previous_avg': avg_first
        }
        
    def get_recent_sessions(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get most recent sessions.
        
        Args:
            count: Number of sessions to retrieve
            
        Returns:
            List of recent session dictionaries
        """
        return self.sessions[-count:]
        
    def generate_career_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive career report.
        
        Returns:
            Dictionary containing detailed career analysis
        """
        metrics = self.get_career_metrics()
        
        report = {
            'player_name': self.player_name,
            'total_hands': self.total_hands,
            'career_metrics': metrics.to_dict(),
            'trends': {
                'vpip': self.get_trend_analysis('vpip'),
                'pfr': self.get_trend_analysis('pfr'),
                'aggression_factor': self.get_trend_analysis('aggression_factor'),
                'winrate': self.get_trend_analysis('winrate'),
                'profit': self.get_trend_analysis('profit')
            },
            'milestones': self.milestones_achieved,
            'session_count': len(self.sessions),
            'report_generated': datetime.now().isoformat()
        }
        
        # Add skill progression
        if len(self.sessions) >= 5:
            report['skill_progression'] = self._analyze_skill_progression()
            
        return report
        
    def _check_milestones(self) -> None:
        """Check and record achievement milestones."""
        milestones = [
            (100, '100_hands'),
            (500, '500_hands'),
            (1000, '1000_hands'),
            (5000, '5000_hands'),
            (10000, '10000_hands')
        ]
        
        for hands, milestone_type in milestones:
            if self.total_hands >= hands:
                # Check if not already achieved
                if not any(m['type'] == milestone_type for m in self.milestones_achieved):
                    self.milestones_achieved.append({
                        'type': milestone_type,
                        'achieved_at': datetime.now().isoformat(),
                        'total_hands': self.total_hands
                    })
                    
    def _analyze_skill_progression(self) -> Dict[str, Any]:
        """Analyze how skills have progressed over time."""
        if len(self.sessions) < 5:
            return {}
            
        # Compare first 5 sessions to last 5 sessions
        first_five = self.sessions[:5]
        last_five = self.sessions[-5:]
        
        def avg_metric(sessions, metric):
            values = [s.get(metric, 0) for s in sessions if metric in s]
            return statistics.mean(values) if values else 0
            
        return {
            'vpip': {
                'early': avg_metric(first_five, 'vpip'),
                'recent': avg_metric(last_five, 'vpip'),
                'improvement': avg_metric(first_five, 'vpip') - avg_metric(last_five, 'vpip')
            },
            'pfr': {
                'early': avg_metric(first_five, 'pfr'),
                'recent': avg_metric(last_five, 'pfr'),
                'improvement': avg_metric(last_five, 'pfr') - avg_metric(first_five, 'pfr')
            },
            'aggression_factor': {
                'early': avg_metric(first_five, 'aggression_factor'),
                'recent': avg_metric(last_five, 'aggression_factor'),
                'improvement': avg_metric(last_five, 'aggression_factor') - avg_metric(first_five, 'aggression_factor')
            }
        }
        
    def get_milestones(self) -> List[Dict[str, Any]]:
        """Get all achieved milestones."""
        return self.milestones_achieved
        
    def get_visualization_data(self) -> Dict[str, List[float]]:
        """
        Get data formatted for visualization/graphing.
        
        Returns:
            Dictionary with metrics over time
        """
        return {
            'vpip_over_time': [s.get('vpip', 0) for s in self.sessions],
            'pfr_over_time': [s.get('pfr', 0) for s in self.sessions],
            'aggression_over_time': [s.get('aggression_factor', 0) for s in self.sessions],
            'winrate_over_time': [s.get('winrate', 0) for s in self.sessions],
            'profit_over_time': [s.get('profit', 0) for s in self.sessions]
        }
        
    def save_to_file(self, filepath: str) -> None:
        """
        Save career data to file.
        
        Args:
            filepath: Path to save file
        """
        data = {
            'player_name': self.player_name,
            'total_hands': self.total_hands,
            'sessions': [
                {**s, 'timestamp': s['timestamp'].isoformat() if 'timestamp' in s else None}
                for s in self.sessions
            ],
            'milestones': self.milestones_achieved
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
            
    @classmethod
    def load_from_file(cls, filepath: str) -> 'CareerTracker':
        """
        Load career data from file.
        
        Args:
            filepath: Path to load from
            
        Returns:
            CareerTracker instance
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        tracker = cls(data['player_name'])
        tracker.total_hands = data['total_hands']
        tracker.milestones_achieved = data['milestones']
        
        # Restore sessions with datetime objects
        for session in data['sessions']:
            if session.get('timestamp'):
                session['timestamp'] = datetime.fromisoformat(session['timestamp'])
            tracker.sessions.append(session)
            
        return tracker
