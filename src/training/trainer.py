"""
Poker Trainer module for PyHoldem Pro.
Implements interactive training features including quizzes and real-time education.
"""
import random
import math
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple
from stats.calculator import PotOddsCalculator


class QuizType(Enum):
    """Types of training quizzes."""
    POT_ODDS = "pot_odds"
    REQUIRED_EQUITY = "required_equity"
    IMPLIED_ODDS = "implied_odds"
    HAND_READING = "hand_reading"
    POSITION_PLAY = "position_play"
    BET_SIZING = "bet_sizing"


class PokerTrainer:
    """Interactive poker training system."""
    
    # Per-topic mastery is tracked here. Each entry is a running window of
    # the most recent N attempts; `get_random_quiz_type` uses this to bias
    # selection toward under-trained topics.
    _MASTERY_WINDOW = 20

    def __init__(self):
        """Initialize the poker trainer."""
        self.training_enabled = False
        self.quiz_frequency = 0.15  # 15% chance to trigger quiz
        self.base_difficulty = 1.0
        self.current_difficulty = 1.0
        self.quiz_history: List[Dict[str, Any]] = []
        self.performance_stats = {
            'total_quizzes': 0,
            'correct_answers': 0,
            'streak': 0,
            'best_streak': 0
        }

        self.quiz_types = [
            QuizType.POT_ODDS,
            QuizType.REQUIRED_EQUITY,
            QuizType.IMPLIED_ODDS,
            QuizType.BET_SIZING
        ]

        # Per-topic running window of {1=correct, 0=incorrect} results.
        self.topic_history: Dict[QuizType, List[int]] = {q: [] for q in self.quiz_types}
        
    def enable_training(self):
        """Enable training mode."""
        self.training_enabled = True
        
    def disable_training(self):
        """Disable training mode."""
        self.training_enabled = False
        
    def should_trigger_quiz(self) -> bool:
        """
        Determine if a quiz should be triggered.
        
        Returns:
            True if quiz should be shown
        """
        if not self.training_enabled:
            return False
            
        # Adjust frequency based on recent performance
        adjusted_frequency = self.quiz_frequency
        if self.performance_stats['streak'] > 3:
            adjusted_frequency *= 0.7  # Reduce frequency for good players
        elif self.performance_stats['streak'] < -2:
            adjusted_frequency *= 1.3  # Increase frequency for struggling players
            
        return random.random() < adjusted_frequency
        
    def generate_quiz(self, quiz_type: QuizType, **kwargs) -> Dict[str, Any]:
        """
        Generate a quiz question based on the current game state.
        
        Args:
            quiz_type: Type of quiz to generate
            **kwargs: Additional parameters for quiz generation
            
        Returns:
            Dictionary containing quiz question, answer, and explanation
        """
        if quiz_type == QuizType.POT_ODDS:
            return self._generate_pot_odds_quiz(**kwargs)
        elif quiz_type == QuizType.REQUIRED_EQUITY:
            return self._generate_required_equity_quiz(**kwargs)
        elif quiz_type == QuizType.IMPLIED_ODDS:
            return self._generate_implied_odds_quiz(**kwargs)
        elif quiz_type == QuizType.BET_SIZING:
            return self._generate_bet_sizing_quiz(**kwargs)
        else:
            return self._generate_default_quiz()
            
    def _generate_pot_odds_quiz(self, pot_size: float, bet_to_call: float) -> Dict[str, Any]:
        """Generate a pot odds quiz question."""
        correct_answer = PotOddsCalculator.calculate_pot_odds(pot_size, bet_to_call)
        percentage = correct_answer * 100
        ratio = PotOddsCalculator.calculate_pot_odds_ratio(pot_size, bet_to_call)
        
        question = (
            f"📊 TRAINING QUIZ - POT ODDS\n"
            f"The pot is ${pot_size:.0f} and you must call ${bet_to_call:.0f}.\n"
            f"What are your pot odds as a percentage?\n"
            f"(Round to the nearest whole number)"
        )
        
        explanation = (
            f"💡 EXPLANATION:\n"
            f"Pot Odds = Bet to Call ÷ (Pot Size + Bet to Call)\n"
            f"= ${bet_to_call:.0f} ÷ (${pot_size:.0f} + ${bet_to_call:.0f})\n"
            f"= ${bet_to_call:.0f} ÷ ${pot_size + bet_to_call:.0f}\n"
            f"= {correct_answer:.3f} = {percentage:.1f}%\n"
            f"As a ratio: {ratio[0]}:1 odds"
        )
        
        return {
            'type': QuizType.POT_ODDS.value,
            'question': question,
            'correct_answer': correct_answer,
            'correct_percentage': round(percentage),
            'explanation': explanation,
            'difficulty': self.current_difficulty
        }
        
    def _generate_required_equity_quiz(
        self,
        pot_size: float,
        bet_to_call: float,
        fold_equity: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Generate a required-equity quiz with fold-equity adjustment.

        Pure pot-odds is `bet / (pot + bet)`. The "required equity to call"
        question becomes interesting when there's fold equity in play: against
        a player who folds X% to a raise/jam, required call equity drops.

        This produces a different correct answer than the paired pot-odds quiz
        so the two quiz types actually train distinct skills.
        """
        if fold_equity is None:
            # Pick a non-trivial fold-equity figure each time so the answer
            # diverges from the raw pot-odds answer.
            fold_equity = random.uniform(0.10, 0.50)

        raw_required = PotOddsCalculator.calculate_pot_odds(pot_size, bet_to_call)
        # When the opponent folds with probability f, we win the pot directly
        # in those branches. Effective required equity on the (1-f) non-fold
        # branch: (raw - f) / (1 - f), clamped to [0, 1].
        adjusted = (raw_required - fold_equity) / (1.0 - fold_equity)
        adjusted = max(0.0, min(1.0, adjusted))
        percentage = adjusted * 100

        question = (
            "🎯 TRAINING QUIZ - REQUIRED EQUITY (with fold equity)\n"
            f"The pot is ${pot_size:.0f}, the bet to call is ${bet_to_call:.0f}.\n"
            f"You estimate your opponent folds {fold_equity * 100:.0f}% of the time "
            "when you shove.\n"
            "What minimum equity do you need on the called branch to break even?\n"
            "(Answer as a percentage, rounded to the nearest whole number)"
        )

        raw_pct = raw_required * 100
        explanation = (
            "💡 EXPLANATION:\n"
            f"Without fold equity, you'd need {raw_pct:.1f}% to call.\n"
            f"Because the opponent folds {fold_equity * 100:.0f}% of the time, "
            "you collect the pot directly in those branches.\n"
            "On the remaining (called) branch, you only need to win often "
            f"enough that the combined EV is breakeven:\n"
            f"= (raw_required - fold_equity) / (1 - fold_equity)\n"
            f"= ({raw_pct:.1f}% - {fold_equity * 100:.0f}%) / "
            f"(100% - {fold_equity * 100:.0f}%)\n"
            f"= {percentage:.1f}%"
        )

        return {
            'type': QuizType.REQUIRED_EQUITY.value,
            'question': question,
            'correct_answer': adjusted,
            'correct_percentage': round(percentage),
            'explanation': explanation,
            'difficulty': self.current_difficulty,
            'context': {
                'pot_size': pot_size,
                'bet_to_call': bet_to_call,
                'fold_equity': fold_equity,
                'raw_pot_odds': raw_required,
            },
        }
        
    def _generate_implied_odds_quiz(self, pot_size: float, bet_to_call: float, 
                                  future_bets: float = None) -> Dict[str, Any]:
        """Generate an implied odds quiz question."""
        if future_bets is None:
            future_bets = pot_size * random.uniform(0.3, 0.8)
            
        implied_odds = PotOddsCalculator.calculate_implied_odds(pot_size, bet_to_call, future_bets)
        percentage = implied_odds * 100
        
        question = (
            f"🔮 TRAINING QUIZ - IMPLIED ODDS\n"
            f"Current pot: ${pot_size:.0f}, you must call ${bet_to_call:.0f}\n"
            f"You estimate you can win an additional ${future_bets:.0f} if you hit your draw.\n"
            f"What are your implied odds as a percentage?\n"
            f"(Round to nearest whole number)"
        )
        
        explanation = (
            f"💡 EXPLANATION:\n"
            f"Implied Odds = Bet to Call ÷ (Pot + Bet + Future Winnings)\n"
            f"= ${bet_to_call:.0f} ÷ (${pot_size:.0f} + ${bet_to_call:.0f} + ${future_bets:.0f})\n"
            f"= ${bet_to_call:.0f} ÷ ${pot_size + bet_to_call + future_bets:.0f}\n"
            f"= {implied_odds:.3f} = {percentage:.1f}%\n\n"
            f"Implied odds are better than direct pot odds when you can win more money later."
        )
        
        return {
            'type': QuizType.IMPLIED_ODDS.value,
            'question': question,
            'correct_answer': implied_odds,
            'correct_percentage': round(percentage),
            'explanation': explanation,
            'difficulty': self.current_difficulty
        }
        
    def _generate_bet_sizing_quiz(self, pot_size: float, hand_strength: float = None) -> Dict[str, Any]:
        """Generate a bet sizing quiz question."""
        if hand_strength is None:
            hand_strength = random.uniform(0.6, 0.9)
            
        # Optimal bet sizing based on hand strength and pot size
        if hand_strength > 0.8:
            optimal_ratio = 0.75  # 75% pot bet with strong hands
        elif hand_strength > 0.7:
            optimal_ratio = 0.5   # 50% pot bet with good hands
        else:
            optimal_ratio = 0.33  # 33% pot bet with marginal hands
            
        optimal_bet = pot_size * optimal_ratio
        
        strength_desc = "very strong" if hand_strength > 0.8 else "strong" if hand_strength > 0.7 else "decent"
        
        question = (
            f"💰 TRAINING QUIZ - BET SIZING\n"
            f"You have a {strength_desc} hand and the pot is ${pot_size:.0f}.\n"
            f"What would be an optimal bet size for value?\n"
            f"(Answer in dollars, no $ sign needed)"
        )
        
        explanation = (
            f"💡 EXPLANATION:\n"
            f"With a {strength_desc} hand (strength: {hand_strength:.1f}), optimal sizing is:\n"
            f"• {optimal_ratio*100:.0f}% of pot = ${optimal_bet:.0f}\n\n"
            f"Bet sizing guidelines:\n"
            f"• Strong hands (0.8+): 60-80% pot for value\n"
            f"• Good hands (0.7+): 40-60% pot for value\n"
            f"• Marginal hands: 25-40% pot for thin value\n"
            f"• Bluffs: 60-100% pot for fold equity"
        )
        
        return {
            'type': QuizType.BET_SIZING.value,
            'question': question,
            'correct_answer': optimal_bet,
            'explanation': explanation,
            'difficulty': self.current_difficulty,
            'acceptable_range': (optimal_bet * 0.8, optimal_bet * 1.2)
        }
        
    def _generate_default_quiz(self) -> Dict[str, Any]:
        """Generate a default quiz when specific type is unavailable."""
        return {
            'type': 'default',
            'question': "Training quiz not available at this time.",
            'correct_answer': 0,
            'explanation': "Continue playing to unlock more training opportunities!",
            'difficulty': 1.0
        }
        
    def evaluate_answer(self, correct_answer: float, user_answer: float, 
                       tolerance: float = 0.05) -> Dict[str, Any]:
        """
        Evaluate a user's quiz answer.
        
        Args:
            correct_answer: The correct answer
            user_answer: The user's answer
            tolerance: Acceptable margin of error
            
        Returns:
            Evaluation result with feedback
        """
        if isinstance(user_answer, str):
            try:
                user_answer = float(user_answer)
            except ValueError:
                return {
                    'correct': False,
                    'feedback': "Please enter a valid number.",
                    'user_answer': user_answer,
                    'correct_answer': correct_answer
                }
                
        # Tolerance semantics (pinned, see tests/test_training_mode.py):
        #
        # - Fractional correct answers (0 < a <= 1) such as pot-odds (0.25):
        #     * Accept fractional input if |a - user| <= tolerance.
        #     * Also accept percent input if |a*100 - user| <= tolerance*100,
        #       so a tolerance of 0.05 means "within 5 percentage points" in
        #       either input form. The two checks are equivalent and the
        #       union just lets the user type either 0.25 or 25 freely.
        #
        # - Numeric correct answers (e.g. bet sizing in chips, > 1):
        #     * tolerance <= 1.0 is treated as a RELATIVE fraction
        #       (tolerance=0.2 -> within 20% of the target).
        #     * tolerance > 1.0 is treated as an ABSOLUTE chip amount.
        difference = abs(correct_answer - user_answer)

        is_fractional = 0 < correct_answer <= 1.0
        if is_fractional:
            is_correct = difference <= tolerance

            # Also accept percent answers when the user enters 0-100.
            percentage_tolerance = tolerance * 100
            percentage_difference = abs((correct_answer * 100) - user_answer)
            is_correct = is_correct or (percentage_difference <= percentage_tolerance)
        else:
            if tolerance <= 1.0:
                # Relative tolerance: a fraction of |correct_answer|.
                allowed_diff = abs(correct_answer) * tolerance
            else:
                # Absolute tolerance: in chips/units.
                allowed_diff = tolerance
            is_correct = difference <= allowed_diff
            
        # Update performance stats
        self.performance_stats['total_quizzes'] += 1
        if is_correct:
            self.performance_stats['correct_answers'] += 1
            self.performance_stats['streak'] = max(0, self.performance_stats['streak']) + 1
            self.performance_stats['best_streak'] = max(
                self.performance_stats['best_streak'], 
                self.performance_stats['streak']
            )
            feedback = self._generate_positive_feedback()
        else:
            self.performance_stats['streak'] = min(0, self.performance_stats['streak']) - 1
            feedback = self._generate_corrective_feedback(correct_answer, user_answer)
            
        # Adjust difficulty based on performance
        self._adjust_difficulty(is_correct)
        
        return {
            'correct': is_correct,
            'feedback': feedback,
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'difference': difference,
            'performance_stats': self.performance_stats.copy()
        }
        
    def _generate_positive_feedback(self) -> str:
        """Generate encouraging feedback for correct answers."""
        positive_messages = [
            "🎉 Excellent! You're thinking like a pro!",
            "✅ Correct! Your poker math is on point!",
            "🎯 Perfect! You nailed that calculation!",
            "💪 Great job! Your training is paying off!",
            "⭐ Outstanding! You're mastering poker fundamentals!"
        ]
        
        streak = self.performance_stats['streak']
        base_message = random.choice(positive_messages)
        
        if streak > 5:
            return f"{base_message}\n🔥 Amazing streak! {streak} in a row!"
        elif streak > 3:
            return f"{base_message}\n⚡ You're on fire! {streak} correct!"
            
        return base_message
        
    def _generate_corrective_feedback(self, correct: float, user_answer: float) -> str:
        """Generate helpful feedback for incorrect answers."""
        return (
            f"❌ Not quite right.\n"
            f"Your answer: {user_answer}\n"
            f"Correct answer: {correct:.3f} ({correct*100:.1f}%)\n"
            f"💡 Review the explanation above and try to understand the calculation!"
        )
        
    def _adjust_difficulty(self, correct: bool):
        """Adjust quiz difficulty based on performance."""
        if correct:
            self.current_difficulty = min(2.0, self.current_difficulty + 0.05)
        else:
            self.current_difficulty = max(0.5, self.current_difficulty - 0.1)
            
    def record_quiz_result(self, correct: bool):
        """Record a quiz result for testing purposes."""
        if correct:
            self.performance_stats['correct_answers'] += 1
            self.performance_stats['streak'] = max(0, self.performance_stats['streak']) + 1
        else:
            self.performance_stats['streak'] = min(0, self.performance_stats['streak']) - 1
            
        self.performance_stats['total_quizzes'] += 1
        self._adjust_difficulty(correct)
        
    def topic_mastery(self, quiz_type: QuizType) -> float:
        """Return rolling accuracy in [0, 1] for a topic.

        Returns 0.5 (neutral) when there's no data yet, so under-trained
        topics aren't aggressively over-weighted before the user has seen them.
        """
        window = self.topic_history.get(quiz_type) or []
        if not window:
            return 0.5
        return sum(window) / len(window)

    def record_topic_result(self, quiz_type: QuizType, correct: bool) -> None:
        """Append a result to the topic's rolling window."""
        window = self.topic_history.setdefault(quiz_type, [])
        window.append(1 if correct else 0)
        if len(window) > self._MASTERY_WINDOW:
            del window[: len(window) - self._MASTERY_WINDOW]

    def get_random_quiz_type(self) -> QuizType:
        """Pick a quiz topic biased toward under-mastered ones.

        Weight = max(0.2, 1 - mastery). A topic at 100% accuracy still gets
        20% relative weight so the user occasionally reviews mastered material;
        a topic at 0% accuracy gets ~5x the weight of a mastered one.
        """
        weights: Dict[QuizType, float] = {}
        for quiz_type in self.quiz_types:
            mastery = self.topic_mastery(quiz_type)
            weights[quiz_type] = max(0.2, 1.0 - mastery)

        quiz_types = list(weights.keys())
        quiz_weights = list(weights.values())
        return random.choices(quiz_types, weights=quiz_weights)[0]
        
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of training performance."""
        total = self.performance_stats['total_quizzes']
        correct = self.performance_stats['correct_answers']
        
        accuracy = (correct / total * 100) if total > 0 else 0
        
        if accuracy >= 90:
            grade = "A+"
            message = "Exceptional poker math skills!"
        elif accuracy >= 80:
            grade = "A"
            message = "Excellent understanding of poker fundamentals!"
        elif accuracy >= 70:
            grade = "B"
            message = "Good grasp of poker concepts. Keep practicing!"
        elif accuracy >= 60:
            grade = "C"
            message = "Fair understanding. Focus on the basics."
        else:
            grade = "D"
            message = "Needs improvement. Review fundamental concepts."
            
        return {
            'total_quizzes': total,
            'correct_answers': correct,
            'accuracy': accuracy,
            'current_streak': self.performance_stats['streak'],
            'best_streak': self.performance_stats['best_streak'],
            'grade': grade,
            'message': message,
            'difficulty_level': self.current_difficulty
        }
