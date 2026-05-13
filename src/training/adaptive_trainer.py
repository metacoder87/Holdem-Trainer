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
            elif weakness == WeaknessType.TOO_TIGHT:
                focus_distribution['late_position_opens'] = 0.3
                focus_distribution['profitable_steals'] = 0.2
            elif weakness == WeaknessType.TOO_PASSIVE:
                focus_distribution['aggression'] = 0.3
                focus_distribution['bet_sizing'] = 0.2
            elif weakness == WeaknessType.TOO_AGGRESSIVE:
                focus_distribution['bluff_selection'] = 0.3
                focus_distribution['pot_control'] = 0.2
            elif weakness == WeaknessType.POOR_POT_ODDS:
                focus_distribution['pot_odds'] = 0.4
                focus_distribution['equity'] = 0.2
            elif weakness == WeaknessType.POOR_POSITION_PLAY:
                focus_distribution['position'] = 0.3
                focus_distribution['blind_defense'] = 0.2
            elif weakness == WeaknessType.WEAK_3BET_DEFENSE:
                focus_distribution['3bet_defense'] = 0.3
                focus_distribution['hand_ranges'] = 0.2
            elif weakness == WeaknessType.POOR_BET_SIZING:
                focus_distribution['bet_sizing'] = 0.3
                focus_distribution['value_targets'] = 0.2
            elif weakness == WeaknessType.TILT_PRONE:
                focus_distribution['session_pacing'] = 0.3
                focus_distribution['reset_routines'] = 0.2
                
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
                'difficulty': self.current_difficulty,
                'correct_answer': 'bet',
                'explanation': 'Top pair with a good kicker should often bet for value instead of defaulting to passive calls/checks.'
            },
            WeaknessType.TOO_LOOSE: {
                'question': 'You are in early position with {hand}. Should you enter the pot?',
                'type': 'hand_selection',
                'difficulty': self.current_difficulty,
                'correct_answer': 'fold',
                'explanation': 'Marginal offsuit hands lose value from early position because many players still act behind you.'
            },
            WeaknessType.TOO_TIGHT: {
                'question': 'Folded to you on the button with K9 suited. What is the best default action?',
                'type': 'late_position_opens',
                'difficulty': self.current_difficulty,
                'correct_answer': 'raise',
                'explanation': 'Late position lets you open wider because you have fewer players behind and position postflop.'
            },
            WeaknessType.TOO_AGGRESSIVE: {
                'question': 'Your flop bluff is called and the turn completes the front-door flush. What is the best default adjustment without a blocker?',
                'type': 'bluff_selection',
                'difficulty': self.current_difficulty,
                'correct_answer': 'check',
                'explanation': 'When the board worsens for your range and you lack blockers, reduce bluff frequency and control the pot.'
            },
            WeaknessType.POOR_POSITION_PLAY: {
                'question': 'You face a cutoff open from the big blind with a marginal offsuit hand. What factor matters most?',
                'type': 'position',
                'difficulty': self.current_difficulty,
                'correct_answer': 'position',
                'explanation': 'Out-of-position hands realize less equity, so defense ranges must account for positional disadvantage.'
            },
            WeaknessType.WEAK_3BET_DEFENSE: {
                'question': 'Button opens, small blind 3-bets, and you hold AQ suited on the button. What is the best default response?',
                'type': '3bet_defense',
                'difficulty': self.current_difficulty,
                'correct_answer': 'continue',
                'explanation': 'Strong suited broadways retain equity and playability against many 3-bet ranges.'
            },
            WeaknessType.POOR_BET_SIZING: {
                'question': 'You value bet a strong hand on a wet flop. Should your sizing usually be small or large?',
                'type': 'bet_sizing',
                'difficulty': self.current_difficulty,
                'correct_answer': 'large',
                'explanation': 'Wet boards reward larger value/protection sizes because many worse draws and pairs can continue.'
            },
            WeaknessType.TILT_PRONE: {
                'question': 'After two large lost pots, what is the best next action before continuing?',
                'type': 'session_pacing',
                'difficulty': self.current_difficulty,
                'correct_answer': 'pause',
                'explanation': 'A short reset protects decision quality when recent results may bias your next choices.'
            },
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
            
        question = (
            template.get('question', '')
            .replace('${pot}', '100')
            .replace('${bet}', '40')
            .replace('{hand}', 'J9 offsuit')
        )
        payload = dict(template)
        payload['question'] = question
        payload.setdefault('explanation', 'Choose the line that best addresses this leak.')
        payload.setdefault('correct_answer', 'review')
        payload['weakness_type'] = weakness.value
        return payload
        
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
            },
            WeaknessType.TOO_TIGHT: {
                'situation': 'Action folds to you on the button with a playable suited king',
                'hand': 'K9 suited',
                'pot_size': 30,
                'your_position': 'button',
                'opponents': 2,
                'recommended_actions': ['open raise when stacks are healthy', 'use position to realize equity'],
                'learning_point': 'Late position lets you profitably open more hands than early position'
            },
            WeaknessType.TOO_AGGRESSIVE: {
                'situation': 'Your continuation bet was called and the turn completes a flush draw',
                'pot_size': 180,
                'your_position': 'cutoff',
                'opponents': 1,
                'recommended_actions': ['check more often without relevant blockers', 'continue bluffing with equity or blockers'],
                'learning_point': 'Aggression needs range advantage, blockers, or equity to stay profitable'
            },
            WeaknessType.POOR_POSITION_PLAY: {
                'situation': 'You defend the big blind and must act first on every postflop street',
                'pot_size': 120,
                'your_position': 'big blind',
                'opponents': 1,
                'recommended_actions': ['tighten marginal calls out of position', 'prefer hands with equity realization'],
                'learning_point': 'Position changes how much equity your hand can realize'
            },
            WeaknessType.WEAK_3BET_DEFENSE: {
                'situation': 'You open the button and face a small blind 3-bet',
                'hand': 'AQ suited',
                'pot_size': 150,
                'your_position': 'button',
                'opponents': 1,
                'recommended_actions': ['continue with strong suited broadways', 'fold dominated offsuit hands'],
                'learning_point': 'Good 3-bet defense separates hands that realize equity from dominated calls'
            },
            WeaknessType.POOR_BET_SIZING: {
                'situation': 'You have an overpair on a connected two-tone flop',
                'pot_size': 160,
                'your_position': 'hijack',
                'opponents': 1,
                'recommended_actions': ['size up for value and protection', 'avoid tiny bets on wet boards'],
                'learning_point': 'Board texture should influence value-bet sizing'
            },
            WeaknessType.TILT_PRONE: {
                'situation': 'You lost two large pots in five hands and notice faster decisions',
                'pot_size': 0,
                'your_position': 'session',
                'opponents': 0,
                'recommended_actions': ['pause before the next hand', 'review whether decisions or variance caused the losses'],
                'learning_point': 'Reset routines protect your strategy when emotion changes decision speed'
            },
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
            WeaknessType.TOO_TIGHT,       # Fundamental
            WeaknessType.TOO_PASSIVE,     # Fundamental
            WeaknessType.POOR_POSITION_PLAY,  # Intermediate
            WeaknessType.WEAK_3BET_DEFENSE,  # Intermediate
            WeaknessType.POOR_BET_SIZING,    # Intermediate
            WeaknessType.TOO_AGGRESSIVE,     # Advanced
            WeaknessType.TILT_PRONE,          # Advanced
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
            WeaknessType.TOO_TIGHT: [
                'Late position opening ranges',
                'Steal opportunities',
                'Equity realization in position'
            ],
            WeaknessType.TOO_PASSIVE: [
                'Value betting',
                'Bet sizing strategy',
                'Aggression frequency'
            ],
            WeaknessType.TOO_AGGRESSIVE: [
                'Bluff selection',
                'Blocker awareness',
                'Pot control'
            ],
            WeaknessType.POOR_POT_ODDS: [
                'Pot odds calculation',
                'Implied odds',
                'Drawing hand strategy'
            ],
            WeaknessType.POOR_POSITION_PLAY: [
                'Position and equity realization',
                'Blind defense',
                'In-position pressure'
            ],
            WeaknessType.WEAK_3BET_DEFENSE: [
                '3-bet ranges',
                'Defending vs 3-bets',
                '4-bet strategy'
            ],
            WeaknessType.POOR_BET_SIZING: [
                'Board texture sizing',
                'Value targeting',
                'Protection betting'
            ],
            WeaknessType.TILT_PRONE: [
                'Session pacing',
                'Reset routines',
                'Decision quality checks'
            ]
        }
        
        return topic_map.get(weakness, ['General poker strategy'])
