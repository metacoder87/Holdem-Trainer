"""
Adaptive Trainer module for personalized, targeted poker training.
Automatically configures training sessions based on identified weaknesses.
"""
from typing import List, Dict, Any, Optional
import random
from training.progression_analyzer import WeaknessType, SkillLevel
from training.content_loader import ContentLoader


class AdaptiveTrainer:
    """
    Creates personalized training sessions that target specific weaknesses.
    Adapts difficulty and focus areas based on player performance.
    """
    
    def __init__(self, player_name: str):
        """
        Initialize adaptive trainer.
        
        Args:
            player_name: Name of the player
        """
        self.player_name = player_name
        self.content_loader = ContentLoader()
        self.current_difficulty = 1
        self.practice_history: List[Dict[str, Any]] = []
        self.focus_areas: List[WeaknessType] = []
        
    def configure_from_weaknesses(self, weaknesses: List[WeaknessType]) -> Dict[str, Any]:
        """
        Configure training session based on identified weaknesses.
        
        Args:
            weaknesses: List of weakness types to address
            
        Returns:
            Training configuration dictionary
        """
        self.focus_areas = weaknesses
        
        # Map weaknesses to training focus
        focus_distribution = {}
        
        for weakness in weaknesses:
            if weakness == WeaknessType.TOO_LOOSE:
                focus_distribution['hand_selection'] = 0.3
                focus_distribution['position'] = 0.2
            elif weakness == WeaknessType.TOO_PASSIVE:
                focus_distribution['aggression'] = 0.3
                focus_distribution['bet_sizing'] = 0.2
            elif weakness == WeaknessType.POOR_POT_ODDS:
                focus_distribution['pot_odds'] = 0.4
                focus_distribution['equity'] = 0.2
            elif weakness == WeaknessType.WEAK_3BET_DEFENSE:
                focus_distribution['3bet_defense'] = 0.3
                focus_distribution['hand_ranges'] = 0.2
                
        # Normalize distribution
        total = sum(focus_distribution.values())
        if total > 0:
            focus_distribution = {k: v/total for k, v in focus_distribution.items()}
            
        return {
            'focus_areas': list(focus_distribution.keys()),
            'quiz_distribution': focus_distribution,
            'difficulty': self.current_difficulty,
            'estimated_duration': len(weaknesses) * 10,  # 10 min per weakness
            'weakness_targets': [w.value for w in weaknesses]
        }
        
    def generate_targeted_quiz(self, weakness: WeaknessType) -> Dict[str, Any]:
        """
        Generate a quiz question targeting a specific weakness.
        
        Args:
            weakness: The weakness to target
            
        Returns:
            Quiz dictionary with question, answer, and explanation
        """
        quiz_templates = {
            WeaknessType.POOR_POT_ODDS: {
                'question': 'You have a flush draw on the flop. Pot is ${pot}, opponent bets ${bet}. Should you call?',
                'type': 'pot_odds',
                'difficulty': self.current_difficulty
            },
            WeaknessType.TOO_PASSIVE: {
                'question': 'You have top pair on the flop. Pot is ${pot}. What should you bet?',
                'type': 'bet_sizing',
                'difficulty': self.current_difficulty
            },
            WeaknessType.TOO_LOOSE: {
                'question': 'You are in early position with {hand}. Should you enter the pot?',
                'type': 'hand_selection',
                'difficulty': self.current_difficulty
            }
        }
        
        template = quiz_templates.get(weakness, quiz_templates[WeaknessType.POOR_POT_ODDS])
        
        # Generate specific values based on difficulty
        if template['type'] == 'pot_odds':
            pot = random.randint(50, 200) * (1 + self.current_difficulty * 0.5)
            bet = random.randint(20, 100) * (1 + self.current_difficulty * 0.5)
            pot_odds = pot / bet
            
            # With 9 outs (flush draw), need ~4.5:1 odds
            correct_answer = 'yes' if pot_odds >= 4.0 else 'no'
            
            question = template['question'].replace('${pot}', str(int(pot))).replace('${bet}', str(int(bet)))
            
            return {
                'question': question,
                'correct_answer': correct_answer,
                'explanation': f"Pot odds: {pot_odds:.1f}:1. With 9 outs (flush draw), you need ~4:1 odds to call profitably.",
                'weakness_type': weakness.value,
                'pot': pot,
                'bet': bet
            }
            
        return template
        
    def adjust_difficulty(self, performance_data: Dict[str, Any]) -> None:
        """
        Adjust difficulty based on recent performance.
        
        Args:
            performance_data: Dictionary with recent quiz results
        """
        correct = performance_data.get('correct_answers', 0)
        total = performance_data.get('total_questions', 1)
        accuracy = correct / total if total > 0 else 0
        
        # Adjust difficulty (1-5 scale)
        if accuracy > 0.85 and self.current_difficulty < 5:
            self.current_difficulty += 1
        elif accuracy < 0.60 and self.current_difficulty > 1:
            self.current_difficulty -= 1
            
    def create_practice_scenario(self, weakness: WeaknessType) -> Dict[str, Any]:
        """
        Create a practice scenario for a specific weakness.
        
        Args:
            weakness: The weakness to address
            
        Returns:
            Practice scenario dictionary
        """
        scenarios = {
            WeaknessType.TOO_PASSIVE: {
                'situation': 'You have top pair, good kicker on a dry flop',
                'pot_size': 100,
                'your_position': 'button',
                'opponents': 1,
                'recommended_actions': ['bet 60-70% pot for value', 'protect your hand'],
                'learning_point': 'Value betting with strong hands is crucial'
            },
            WeaknessType.POOR_POT_ODDS: {
                'situation': 'You have an open-ended straight draw on the turn',
                'pot_size': 150,
                'bet_to_call': 50,
                'outs': 8,
                'recommended_actions': ['calculate pot odds', 'compare to odds of hitting'],
                'learning_point': 'With 8 outs, you need ~5:1 pot odds to call profitably'
            },
            WeaknessType.TOO_LOOSE: {
                'situation': 'You are in early position pre-flop',
                'hand': 'J9 offsuit',
                'pot_size': 0,
                'recommended_actions': ['fold marginal hands from early position'],
                'learning_point': 'Tight is right from early position'
            }
        }
        
        return scenarios.get(weakness, scenarios[WeaknessType.TOO_PASSIVE])
        
    def track_practice_result(self, result: Dict[str, Any]) -> None:
        """
        Track the result of a practice exercise.
        
        Args:
            result: Dictionary with practice result data
        """
        self.practice_history.append({
            'weakness_type': result.get('weakness_type'),
            'correct': result.get('correct', False),
            'time_taken': result.get('time_taken', 0),
            'difficulty': self.current_difficulty
        })
        
    def get_practice_statistics(self) -> Dict[str, Any]:
        """
        Get statistics on practice performance.
        
        Returns:
            Dictionary with practice statistics
        """
        if not self.practice_history:
            return {'completed_exercises': []}
            
        by_weakness = {}
        for practice in self.practice_history:
            weakness = practice.get('weakness_type')
            if weakness not in by_weakness:
                by_weakness[weakness] = {'correct': 0, 'total': 0}
            by_weakness[weakness]['total'] += 1
            if practice.get('correct'):
                by_weakness[weakness]['correct'] += 1
                
        return {
            'completed_exercises': self.practice_history,
            'by_weakness': by_weakness,
            'total_exercises': len(self.practice_history),
            'current_difficulty': self.current_difficulty
        }
        
    def generate_personalized_curriculum(self, weaknesses: List[WeaknessType]) -> Dict[str, Any]:
        """
        Generate a complete personalized learning curriculum.
        
        Args:
            weaknesses: List of weaknesses to address
            
        Returns:
            Curriculum dictionary with modules and timeline
        """
        modules = []
        
        # Prioritize weaknesses (most critical first)
        priority_order = [
            WeaknessType.POOR_POT_ODDS,  # Fundamental
            WeaknessType.TOO_LOOSE,       # Fundamental
            WeaknessType.TOO_PASSIVE,     # Fundamental
            WeaknessType.WEAK_3BET_DEFENSE,  # Intermediate
            WeaknessType.POOR_BET_SIZING,    # Intermediate
            WeaknessType.TOO_AGGRESSIVE,     # Advanced
        ]
        
        sorted_weaknesses = sorted(weaknesses, 
                                   key=lambda w: priority_order.index(w) if w in priority_order else 99)
        
        for i, weakness in enumerate(sorted_weaknesses):
            module = {
                'order': i + 1,
                'weakness': weakness.value,
                'topics': self._get_topics_for_weakness(weakness),
                'exercises': 10,  # 10 practice exercises per module
                'estimated_time': 30,  # 30 minutes
                'quizzes': 5  # 5 quizzes
            }
            modules.append(module)
            
        total_time = sum(m['estimated_time'] for m in modules)
        
        return {
            'modules': modules,
            'total_modules': len(modules),
            'estimated_duration': total_time,
            'difficulty_level': self.current_difficulty,
            'recommended_pace': 'One module per day'
        }
        
    def _get_topics_for_weakness(self, weakness: WeaknessType) -> List[str]:
        """Get relevant study topics for a weakness."""
        topic_map = {
            WeaknessType.TOO_LOOSE: [
                'Starting hand requirements',
                'Position-based hand selection',
                'Table dynamics'
            ],
            WeaknessType.TOO_PASSIVE: [
                'Value betting',
                'Bet sizing strategy',
                'Aggression frequency'
            ],
            WeaknessType.POOR_POT_ODDS: [
                'Pot odds calculation',
                'Implied odds',
                'Drawing hand strategy'
            ],
            WeaknessType.WEAK_3BET_DEFENSE: [
                '3-bet ranges',
                'Defending vs 3-bets',
                '4-bet strategy'
            ]
        }
        
        return topic_map.get(weakness, ['General poker strategy'])
