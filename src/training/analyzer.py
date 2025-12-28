"""
Hand and Session Analyzer for PyHoldem Pro Training Mode.
Provides post-hand analysis and session reviews with actionable feedback.
"""
from typing import Dict, List, Any, Tuple, Optional
from game.player import PlayerAction
from stats.calculator import PotOddsCalculator


class HandAnalyzer:
    """Analyzes individual hands and provides educational feedback."""
    
    def __init__(self):
        """Initialize the hand analyzer."""
        self.opponent_type_profiles = {
            'tight-passive': {
                'vpip': 0.15, 'pfr': 0.05, 'af': 0.8, 'fold_to_bluff': 0.7,
                'description': 'Plays few hands, rarely bets/raises, folds to pressure'
            },
            'tight-aggressive': {
                'vpip': 0.20, 'pfr': 0.16, 'af': 2.5, 'fold_to_bluff': 0.5,
                'description': 'Plays few hands but plays them aggressively'
            },
            'loose-passive': {
                'vpip': 0.35, 'pfr': 0.08, 'af': 1.2, 'fold_to_bluff': 0.3,
                'description': 'Plays many hands but passively, calls too much'
            },
            'loose-aggressive': {
                'vpip': 0.40, 'pfr': 0.25, 'af': 3.0, 'fold_to_bluff': 0.2,
                'description': 'Plays many hands aggressively, hard to bluff'
            },
            'balanced': {
                'vpip': 0.25, 'pfr': 0.18, 'af': 2.0, 'fold_to_bluff': 0.4,
                'description': 'Well-rounded player with solid fundamentals'
            }
        }
        
    def analyze_decision(self, action: PlayerAction, pot_size: float, 
                        bet_to_call: float, hand_equity: float, 
                        opponent_type: str) -> Dict[str, Any]:
        """
        Analyze a player's decision with educational feedback.
        
        Args:
            action: The action taken by the player
            pot_size: Current pot size
            bet_to_call: Amount needed to call
            hand_equity: Player's estimated hand equity
            opponent_type: Type of opponent faced
            
        Returns:
            Analysis with recommendation and reasoning
        """
        pot_odds = PotOddsCalculator.calculate_pot_odds(pot_size, bet_to_call)
        required_equity = pot_odds
        
        analysis = {
            'action_taken': action.value,
            'pot_odds': pot_odds,
            'pot_odds_percentage': pot_odds * 100,
            'required_equity': required_equity,
            'hand_equity': hand_equity,
            'hand_equity_percentage': hand_equity * 100,
            'opponent_type': opponent_type
        }
        
        # Determine mathematically correct decision
        if hand_equity > required_equity:
            math_decision = 'call'
            equity_advantage = hand_equity - required_equity
        else:
            math_decision = 'fold'
            equity_advantage = hand_equity - required_equity  # Will be negative
            
        analysis['math_recommendation'] = math_decision
        analysis['equity_advantage'] = equity_advantage
        
        # Adjust recommendation based on opponent type
        opponent_profile = self.opponent_type_profiles.get(opponent_type, {})
        adjusted_decision = self._adjust_for_opponent_type(
            math_decision, opponent_type, opponent_profile, hand_equity
        )
        
        analysis['recommendation'] = adjusted_decision
        analysis['reasoning'] = self._generate_reasoning(
            action, math_decision, adjusted_decision, analysis, opponent_profile
        )
        
        return analysis
        
    def _adjust_for_opponent_type(self, math_decision: str, opponent_type: str,
                                 opponent_profile: Dict, hand_equity: float) -> str:
        """Adjust mathematical decision based on opponent tendencies."""
        # Against tight players, bluffs work better
        if 'tight' in opponent_type and hand_equity < 0.3:
            # Weak hand against tight player - consider bluffing/folding
            return math_decision
            
        # Against loose players, value bet thinner
        if 'loose' in opponent_type and hand_equity > 0.6:
            # Strong hand against loose player - more likely to call
            return 'call' if math_decision == 'call' else math_decision
            
        return math_decision
        
    def _generate_reasoning(self, action: PlayerAction, math_decision: str,
                           final_decision: str, analysis: Dict,
                           opponent_profile: Dict) -> str:
        """Generate detailed reasoning for the decision analysis."""
        pot_odds_pct = analysis['pot_odds_percentage']
        hand_equity_pct = analysis['hand_equity_percentage']
        equity_advantage = analysis['equity_advantage'] * 100
        
        reasoning_parts = []
        
        # Mathematical analysis
        if equity_advantage > 0:
            reasoning_parts.append(
                f"✅ MATH: Your hand equity ({hand_equity_pct:.1f}%) exceeds "
                f"required equity ({pot_odds_pct:.1f}%), making this a "
                f"profitable call with {equity_advantage:.1f}% advantage."
            )
        else:
            reasoning_parts.append(
                f"❌ MATH: Your hand equity ({hand_equity_pct:.1f}%) is below "
                f"required equity ({pot_odds_pct:.1f}%), making this call "
                f"unprofitable by {abs(equity_advantage):.1f}%."
            )
            
        # Opponent type consideration
        if opponent_profile:
            opponent_desc = opponent_profile.get('description', '')
            reasoning_parts.append(
                f"🎯 OPPONENT: Against a {analysis['opponent_type']} player "
                f"({opponent_desc}), this affects the decision because:"
            )
            
            if 'tight' in analysis['opponent_type']:
                reasoning_parts.append(
                    "• Tight players fold more often to pressure\n"
                    "• They typically have strong hands when betting\n"
                    "• Bluffs are more effective against them"
                )
            elif 'loose' in analysis['opponent_type']:
                reasoning_parts.append(
                    "• Loose players call more often with weak hands\n"
                    "• Value betting is more profitable against them\n"
                    "• Bluffs are less effective due to high call frequency"
                )
                
        # Action evaluation
        action_str = action.value if hasattr(action, 'value') else str(action)
        if action_str == final_decision:
            reasoning_parts.append(f"✅ RESULT: Your {action_str} was optimal!")
        elif action_str == math_decision:
            reasoning_parts.append(
                f"📊 RESULT: Your {action_str} was mathematically sound, "
                f"though {final_decision} might be slightly better against this opponent type."
            )
        else:
            reasoning_parts.append(
                f"⚠️  RESULT: Your {action_str} was suboptimal. "
                f"Consider {final_decision} in similar situations."
            )
            
        return "\n\n".join(reasoning_parts)
        
    def analyze_bluff(self, bet_size: float, pot_size: float, 
                     opponent_type: str, board_texture: str) -> Dict[str, Any]:
        """
        Analyze the profitability of a bluff attempt.
        
        Args:
            bet_size: Size of the bluff bet
            pot_size: Current pot size
            opponent_type: Type of opponent
            board_texture: Board texture (wet/dry)
            
        Returns:
            Bluff analysis with profitability assessment
        """
        opponent_profile = self.opponent_type_profiles.get(opponent_type, {})
        base_fold_frequency = opponent_profile.get('fold_to_bluff', 0.4)
        
        # Adjust fold frequency based on board texture
        if board_texture == 'dry':
            fold_frequency = base_fold_frequency * 1.2  # More likely to fold on dry boards
        else:  # wet board
            fold_frequency = base_fold_frequency * 0.8  # Less likely to fold on wet boards
            
        fold_frequency = min(0.9, max(0.1, fold_frequency))  # Clamp between 10-90%
        
        # Calculate bluff profitability
        # Profit when opponent folds: pot_size
        # Loss when opponent calls: -bet_size
        expected_value = (fold_frequency * pot_size) - ((1 - fold_frequency) * bet_size)
        
        return {
            'opponent_type': opponent_type,
            'fold_frequency': fold_frequency,
            'expected_value': expected_value,
            'profitability': expected_value > 0,
            'board_texture': board_texture,
            'bluff_to_pot_ratio': bet_size / pot_size if pot_size > 0 else 0
        }
        
    def generate_post_hand_feedback(self, hand_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive post-hand analysis and feedback.
        
        Args:
            hand_data: Complete hand information
            
        Returns:
            Detailed feedback with learning points
        """
        feedback = {
            'summary': self._generate_hand_summary(hand_data),
            'key_decisions': self._analyze_key_decisions(hand_data),
            'opponent_analysis': self._analyze_opponent_tendencies(hand_data),
            'learning_points': self._extract_learning_points(hand_data),
            'overall_rating': self._rate_hand_performance(hand_data)
        }
        
        return feedback
        
    def _generate_hand_summary(self, hand_data: Dict[str, Any]) -> str:
        """Generate a brief summary of the hand."""
        hero_name = hand_data.get('hero_name') or hand_data.get('player_name') or 'User'
        winner = hand_data.get('winner', 'Unknown')
        final_pot = hand_data.get('final_pot', 0)
        user_result = 'won' if winner == hero_name else 'lost'
        
        return (
            f"Hand Summary: You {user_result} this hand. "
            f"Final pot: ${final_pot:.0f}. Winner: {winner}."
        )
        
    def _analyze_key_decisions(self, hand_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze the key decisions made during the hand."""
        actions = hand_data.get('actions', [])
        key_decisions = []
        hero_name = hand_data.get('hero_name') or hand_data.get('player_name') or 'User'
        
        for i, action_data in enumerate(actions):
            if action_data.get('player') == hero_name:
                decision_analysis = {
                    'street': self._determine_street(i, len(actions)),
                    'action': action_data.get('action'),
                    'amount': action_data.get('amount', 0),
                    'pot_before': action_data.get('pot_before', 0),
                    'analysis': f"On the {self._determine_street(i, len(actions))}, you {action_data.get('action')}"
                }
                key_decisions.append(decision_analysis)
                
        return key_decisions
        
    def _analyze_opponent_tendencies(self, hand_data: Dict[str, Any]) -> Dict[str, str]:
        """Analyze opponent tendencies shown in this hand."""
        opponent_stats = hand_data.get('opponent_stats', {})
        analysis = {}
        
        for opponent, stats in opponent_stats.items():
            player_type = stats.get('type', 'unknown')
            vpip = stats.get('vpip', 0) * 100
            pfr = stats.get('pfr', 0) * 100
            
            analysis[opponent] = (
                f"{opponent} is a '{player_type}' player "
                f"(VPIP: {vpip:.0f}%, PFR: {pfr:.0f}%). "
                f"This means they {self._describe_player_type(player_type)}."
            )
            
        return analysis
        
    def _extract_learning_points(self, hand_data: Dict[str, Any]) -> List[str]:
        """Extract key learning points from the hand."""
        learning_points = []
        hero_name = hand_data.get('hero_name') or hand_data.get('player_name') or 'User'
        
        # Add generic learning points based on hand outcome
        if hand_data.get('winner') != hero_name:
            learning_points.append(
                "💡 Consider your opponent's likely holdings when making decisions."
            )
            
        user_strength = hand_data.get('user_hand_strength', 0)
        if user_strength < 0.3:
            learning_points.append(
                "💡 With weak hands, consider the pot odds before calling bets."
            )
        elif user_strength > 0.8:
            learning_points.append(
                "💡 With strong hands, focus on extracting maximum value from opponents."
            )
            
        return learning_points
        
    def _rate_hand_performance(self, hand_data: Dict[str, Any]) -> Dict[str, Any]:
        """Rate the player's overall performance in the hand."""
        # Simplified rating system
        hero_name = hand_data.get('hero_name') or hand_data.get('player_name') or 'User'
        user_won = hand_data.get('winner') == hero_name
        user_strength = hand_data.get('user_hand_strength', 0.5)
        
        if user_won:
            if user_strength > 0.7:
                rating = 'A'
                comment = "Well played! You maximized value with a strong hand."
            else:
                rating = 'A-'
                comment = "Good result! You made the most of a difficult situation."
        else:
            if user_strength < 0.3:
                rating = 'B'
                comment = "Acceptable. Sometimes you have to fold weak hands."
            else:
                rating = 'C+'
                comment = "Could improve. Look for ways to extract more value."
                
        return {
            'grade': rating,
            'comment': comment
        }
        
    def _determine_street(self, action_index: int, total_actions: int) -> str:
        """Determine which betting street an action occurred on."""
        # Simplified street determination
        if action_index < total_actions * 0.25:
            return "preflop"
        elif action_index < total_actions * 0.5:
            return "flop"
        elif action_index < total_actions * 0.75:
            return "turn"
        else:
            return "river"
            
    def _describe_player_type(self, player_type: str) -> str:
        """Describe what a player type means in simple terms."""
        descriptions = {
            'tight-passive': "play few hands and rarely bet/raise",
            'tight-aggressive': "play few hands but bet/raise when they do",
            'loose-passive': "play many hands but call more than bet",
            'loose-aggressive': "play many hands and bet/raise frequently",
            'balanced': "play a solid, well-rounded game"
        }
        return descriptions.get(player_type, "have an unknown playing style")


class SessionReviewer:
    """Analyzes complete playing sessions and identifies improvement areas."""
    
    def __init__(self):
        """Initialize the session reviewer."""
        self.benchmark_stats = {
            'vpip': {'tight': 0.15, 'optimal': 0.23, 'loose': 0.35},
            'pfr': {'tight': 0.08, 'optimal': 0.18, 'loose': 0.30},
            'aggression_factor': {'passive': 1.0, 'optimal': 2.0, 'aggressive': 3.5},
            'fold_to_cbet': {'station': 0.3, 'optimal': 0.6, 'folder': 0.8}
        }
        
    def analyze_positional_play(self, position_data: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
        """
        Analyze positional play statistics.
        
        Args:
            position_data: Position-based statistics
            
        Returns:
            Positional analysis with recommendations
        """
        analysis = {}
        
        for position, stats in position_data.items():
            hands = stats.get('hands', 0)
            vpip_count = stats.get('vpip', 0)
            pfr_count = stats.get('pfr', 0)
            
            if hands > 0:
                vpip_pct = vpip_count / hands
                pfr_pct = pfr_count / hands
                
                analysis[f'{position}_hands'] = hands
                analysis[f'{position}_vpip'] = vpip_pct
                analysis[f'{position}_pfr'] = pfr_pct
                
        # Calculate positional awareness
        early_vpip = analysis.get('early_position_vpip', 0)
        late_vpip = analysis.get('late_position_vpip', 0)
        
        if early_vpip > 0:
            position_awareness = (late_vpip - early_vpip) / early_vpip
        else:
            position_awareness = 0
            
        analysis['position_awareness'] = position_awareness
        
        # Generate recommendations
        recommendations = []
        if early_vpip > 0.25:
            recommendations.append(
                "🔴 Your early position VPIP is too high. Tighten up when out of position."
            )
        if position_awareness < 0.2:
            recommendations.append(
                "🔴 You're not adjusting enough for position. Play more hands in late position."
            )
            
        analysis['recommendations'] = recommendations
        
        return analysis
        
    def identify_leaks(self, stats: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Identify statistical leaks in player's game.
        
        Args:
            stats: Player's statistical data
            
        Returns:
            List of identified leaks with severity levels
        """
        leaks = []
        
        # VPIP analysis
        vpip = stats.get('overall_vpip', 0)
        if vpip > 0.4:
            leaks.append({
                'type': 'vpip_too_high',
                'severity': 'high',
                'value': vpip,
                'description': f"VPIP of {vpip*100:.0f}% is too high. Recommended: 20-25%"
            })
        elif vpip < 0.15:
            leaks.append({
                'type': 'vpip_too_low',
                'severity': 'medium',
                'value': vpip,
                'description': f"VPIP of {vpip*100:.0f}% is too tight. Consider 18-25%"
            })
            
        # Aggression factor analysis
        af = stats.get('aggression_factor', 2.0)
        if af < 1.5:
            leaks.append({
                'type': 'too_passive',
                'severity': 'high' if af < 1.0 else 'medium',
                'value': af,
                'description': f"Aggression factor of {af:.1f} is too passive. Aim for 2.0+"
            })
        elif af > 4.0:
            leaks.append({
                'type': 'too_aggressive',
                'severity': 'medium',
                'value': af,
                'description': f"Aggression factor of {af:.1f} may be too aggressive"
            })
            
        # PFR analysis
        pfr = stats.get('pfr', 0)
        if pfr < 0.10:
            leaks.append({
                'type': 'pfr_too_low',
                'severity': 'high',
                'value': pfr,
                'description': f"PFR of {pfr*100:.0f}% is too low. You should raise more preflop"
            })
            
        # Fold to c-bet analysis
        fold_to_cbet = stats.get('fold_to_cbet', 0.6)
        if fold_to_cbet > 0.75:
            leaks.append({
                'type': 'fold_too_much',
                'severity': 'medium',
                'value': fold_to_cbet,
                'description': f"Folding {fold_to_cbet*100:.0f}% to c-bets. Consider defending more"
            })
            
        return leaks
        
    def generate_suggestions(self, leaks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Generate actionable suggestions based on identified leaks.
        
        Args:
            leaks: List of identified leaks
            
        Returns:
            List of improvement suggestions
        """
        suggestions = []
        
        for leak in leaks:
            leak_type = leak['type']
            severity = leak['severity']
            
            if leak_type == 'vpip_too_high':
                suggestions.append({
                    'action': 'Tighten your starting hand selection',
                    'reason': 'Playing too many hands is costly, especially out of position',
                    'specific': 'Focus on premium hands (AA-JJ, AK, AQ) in early position'
                })
            elif leak_type == 'too_passive':
                suggestions.append({
                    'action': 'Increase your betting and raising frequency',
                    'reason': 'Passive play lets opponents see cards cheaply and control the pot',
                    'specific': 'Bet for value with strong hands, bluff with good draws'
                })
            elif leak_type == 'pfr_too_low':
                suggestions.append({
                    'action': 'Raise more often preflop instead of limping',
                    'reason': 'Raising builds pots and puts pressure on opponents',
                    'specific': 'Always raise AA-22, AK-AT, KQ-KJ, QJ+ when first in'
                })
            elif leak_type == 'fold_too_much':
                suggestions.append({
                    'action': 'Defend more hands against continuation bets',
                    'reason': 'Over-folding allows opponents to bluff profitably',
                    'specific': 'Call c-bets with draws, middle pairs, and ace-high on dry boards'
                })
                
        return suggestions
        
    def generate_session_report(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a comprehensive session report.
        
        Args:
            session_data: Complete session statistics
            
        Returns:
            Detailed session report with analysis and recommendations
        """
        hands_played = session_data.get('hands_played', 0)
        net_result = session_data.get('net_result', 0)
        
        # Session summary
        session_summary = {
            'hands_played': hands_played,
            'net_result': net_result,
            'bb_per_100': (net_result / hands_played * 100) if hands_played > 0 else 0,
            'session_length': f"{hands_played} hands"
        }
        
        # Statistical analysis
        stats = {
            'overall_vpip': session_data.get('vpip', 0),
            'pfr': session_data.get('pfr', 0),
            'aggression_factor': session_data.get('aggression_factor', 2.0),
            'fold_to_cbet': session_data.get('fold_to_cbet', 0.6)
        }
        
        # Identify leaks and generate suggestions
        leaks = self.identify_leaks(stats)
        suggestions = self.generate_suggestions(leaks)
        
        # Overall grade
        grade = self._calculate_overall_grade(stats, net_result, hands_played)
        
        return {
            'session_summary': session_summary,
            'statistical_analysis': stats,
            'identified_leaks': leaks,
            'recommendations': suggestions,
            'overall_grade': grade,
            'key_insights': self._generate_key_insights(stats, leaks)
        }
        
    def _calculate_overall_grade(self, stats: Dict[str, float], 
                                net_result: float, hands_played: int) -> Dict[str, Any]:
        """Calculate an overall performance grade."""
        score = 0
        max_score = 100
        
        # VPIP score (20 points)
        vpip = stats.get('overall_vpip', 0.25)
        if 0.18 <= vpip <= 0.28:
            score += 20
        elif 0.15 <= vpip <= 0.35:
            score += 15
        else:
            score += 10
            
        # PFR score (20 points)
        pfr = stats.get('pfr', 0.15)
        if 0.14 <= pfr <= 0.22:
            score += 20
        elif 0.10 <= pfr <= 0.28:
            score += 15
        else:
            score += 10
            
        # Aggression factor score (20 points)
        af = stats.get('aggression_factor', 2.0)
        if 1.8 <= af <= 2.8:
            score += 20
        elif 1.2 <= af <= 3.5:
            score += 15
        else:
            score += 10
            
        # Results score (40 points)
        if hands_played > 0:
            bb_per_100 = net_result / hands_played * 100
            if bb_per_100 > 5:
                score += 40
            elif bb_per_100 > 0:
                score += 30
            elif bb_per_100 > -5:
                score += 20
            else:
                score += 10
                
        percentage = (score / max_score) * 100
        
        if percentage >= 90:
            letter_grade = 'A+'
        elif percentage >= 85:
            letter_grade = 'A'
        elif percentage >= 80:
            letter_grade = 'B+'
        elif percentage >= 75:
            letter_grade = 'B'
        elif percentage >= 70:
            letter_grade = 'C+'
        elif percentage >= 65:
            letter_grade = 'C'
        else:
            letter_grade = 'D'
            
        return {
            'letter': letter_grade,
            'percentage': percentage,
            'points': f"{score}/{max_score}"
        }
        
    def _generate_key_insights(self, stats: Dict[str, float], 
                              leaks: List[Dict[str, Any]]) -> List[str]:
        """Generate key insights from the session."""
        insights = []
        
        if len(leaks) == 0:
            insights.append("🎉 Excellent session! No major statistical leaks identified.")
        elif len(leaks) == 1:
            insights.append("👍 Good session overall with only one area for improvement.")
        else:
            insights.append(f"📊 {len(leaks)} areas identified for improvement.")
            
        # Add specific insights based on stats
        vpip = stats.get('overall_vpip', 0.25)
        pfr = stats.get('pfr', 0.15)
        
        if pfr / vpip > 0.8 if vpip > 0 else False:
            insights.append("💪 High PFR/VPIP ratio shows aggressive play with selected hands.")
        elif pfr / vpip < 0.4 if vpip > 0 else True:
            insights.append("⚠️  Low PFR/VPIP ratio suggests too much passive calling.")
            
        return insights
