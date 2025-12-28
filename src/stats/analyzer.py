"""
Statistics Analyzer module for PyHoldem Pro.
Implements game analysis, player profiling, and performance metrics.
"""
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from game.card import Card
from game.player import Player
from stats.calculator import HandOddsCalculator, PotOddsCalculator


class GameAnalyzer:
    """Analyzes game situations and provides strategic insights."""
    
    def analyze_preflop_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a preflop action for strategic correctness.
        
        Args:
            action_data: Dictionary containing action context
            
        Returns:
            Analysis results with recommendations
        """
        position = action_data.get('position', 0)
        hole_cards = action_data.get('hole_cards', [])
        action = action_data.get('action', '')
        amount = action_data.get('amount', 0)
        pot_size_before = action_data.get('pot_size_before', 0)
        players_in_hand = action_data.get('players_in_hand', 2)
        
        analysis = {
            'action_taken': action,
            'amount': amount,
            'position': position,
            'players_in_hand': players_in_hand
        }
        
        # Evaluate hand strength
        if len(hole_cards) == 2:
            hand_strength = self._evaluate_preflop_hand_strength(hole_cards)
            analysis['hand_strength'] = hand_strength
            
            # Position factor (later position is stronger)
            position_factor = position / 9.0  # Normalize to 0-1
            analysis['position_factor'] = position_factor
            
            # Adjusted strength based on position
            adjusted_strength = hand_strength + position_factor * 0.1
            analysis['adjusted_strength'] = adjusted_strength
            
            # Strategic recommendation
            if adjusted_strength > 0.8:
                recommended = 'raise'
            elif adjusted_strength > 0.6:
                recommended = 'call'
            elif adjusted_strength > 0.4 and position_factor > 0.6:
                recommended = 'call'  # Play more hands in position
            else:
                recommended = 'fold'
            
            analysis['recommended_action'] = recommended
            
            # Action evaluation
            if action == recommended:
                analysis['action_quality'] = 'optimal'
            elif (action == 'call' and recommended == 'raise') or (action == 'raise' and recommended == 'call'):
                analysis['action_quality'] = 'acceptable'
            else:
                analysis['action_quality'] = 'suboptimal'
        
        return analysis
    
    def analyze_postflop_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a postflop action for strategic correctness.
        
        Args:
            action_data: Dictionary containing action context
            
        Returns:
            Analysis results with recommendations
        """
        hole_cards = action_data.get('hole_cards', [])
        community_cards = action_data.get('community_cards', [])
        action = action_data.get('action', '')
        amount = action_data.get('amount', 0)
        pot_size_before = action_data.get('pot_size_before', 0)
        players_in_hand = action_data.get('players_in_hand', 2)
        position = action_data.get('position', 0)
        
        analysis = {
            'action_taken': action,
            'amount': amount,
            'betting_round': len(community_cards)
        }
        
        if len(hole_cards) == 2 and len(community_cards) >= 3:
            # Calculate hand metrics
            hand_strength = HandOddsCalculator.calculate_hand_strength(hole_cards, community_cards)
            analysis['hand_strength'] = hand_strength
            
            # Calculate pot odds if facing a bet
            if amount > 0:
                pot_odds = PotOddsCalculator.calculate_pot_odds(pot_size_before, amount)
                analysis['pot_odds'] = pot_odds
            
            # Estimate equity
            analysis['equity'] = self._estimate_hand_equity(hole_cards, community_cards, players_in_hand)
            
            # Board texture analysis
            board_texture = self._analyze_board_texture(community_cards)
            analysis['board_texture'] = board_texture
            
            # Positional advantage
            analysis['position_strength'] = position / 9.0
        
        return analysis
    
    def analyze_betting_patterns(self, betting_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze a sequence of betting actions for patterns.
        
        Args:
            betting_sequence: List of betting actions
            
        Returns:
            Pattern analysis results
        """
        if not betting_sequence:
            return {}
        
        patterns = {
            'total_actions': len(betting_sequence),
            'unique_players': len(set(action.get('player', '') for action in betting_sequence)),
            'aggression_levels': {},
            'fold_frequency': 0,
            'bet_sizing': {}
        }
        
        # Analyze each player's actions
        player_actions = defaultdict(list)
        for action in betting_sequence:
            player = action.get('player', '')
            if player:
                player_actions[player].append(action)
        
        # Calculate aggression and fold metrics
        total_players = len(player_actions)
        folds = 0
        
        for player, actions in player_actions.items():
            aggressive_actions = 0
            total_actions = len(actions)
            
            for action in actions:
                if action.get('action') in ['raise', 'bet']:
                    aggressive_actions += 1
                elif action.get('action') == 'fold':
                    folds += 1
            
            if total_actions > 0:
                aggression_ratio = aggressive_actions / total_actions
                patterns['aggression_levels'][player] = aggression_ratio
        
        if total_players > 0:
            patterns['fold_frequency'] = folds / len(betting_sequence)
        
        # Analyze bet sizing
        bet_amounts = [action.get('amount', 0) for action in betting_sequence 
                      if action.get('action') in ['bet', 'raise'] and action.get('amount', 0) > 0]
        
        if bet_amounts:
            patterns['bet_sizing'] = {
                'average': sum(bet_amounts) / len(bet_amounts),
                'minimum': min(bet_amounts),
                'maximum': max(bet_amounts),
                'variance': self._calculate_variance(bet_amounts)
            }
        
        return patterns
    
    def _evaluate_preflop_hand_strength(self, hole_cards: List[Card]) -> float:
        """Evaluate preflop hand strength."""
        if len(hole_cards) != 2:
            return 0.0
        
        card1, card2 = hole_cards
        
        # Pocket pairs
        if card1.rank == card2.rank:
            return 0.6 + (card1.rank.value / 14) * 0.3
        
        # Suited connectors and high cards
        suited = card1.suit == card2.suit
        connected = abs(card1.rank.value - card2.rank.value) <= 2
        
        high_card_bonus = max(card1.rank.value, card2.rank.value) / 14 * 0.4
        low_card_bonus = min(card1.rank.value, card2.rank.value) / 14 * 0.2
        suited_bonus = 0.1 if suited else 0
        connected_bonus = 0.05 if connected else 0
        
        return min(high_card_bonus + low_card_bonus + suited_bonus + connected_bonus, 1.0)
    
    def _estimate_hand_equity(self, hole_cards: List[Card], community_cards: List[Card],
                             opponents: int) -> float:
        """Estimate hand equity against multiple opponents."""
        base_strength = HandOddsCalculator.calculate_hand_strength(hole_cards, community_cards)
        potential = HandOddsCalculator.calculate_hand_potential(hole_cards, community_cards)
        
        # Adjust for number of opponents
        opponent_factor = 1 / (1 + opponents * 0.2)  # More opponents = lower individual equity
        
        estimated_equity = (base_strength + potential * 0.4) * opponent_factor
        return min(estimated_equity, 1.0)
    
    def _analyze_board_texture(self, community_cards: List[Card]) -> Dict[str, Any]:
        """Analyze board texture characteristics."""
        if len(community_cards) < 3:
            return {}
        
        ranks = [card.rank.value for card in community_cards]
        suits = [card.suit for card in community_cards]
        
        texture = {
            'dry': False,
            'wet': False,
            'paired': False,
            'flush_possible': False,
            'straight_possible': False
        }
        
        # Check for pairs
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
        
        texture['paired'] = any(count >= 2 for count in rank_counts.values())
        
        # Check for flush possibility
        suit_counts = {}
        for suit in suits:
            suit_counts[suit] = suit_counts.get(suit, 0) + 1
        
        texture['flush_possible'] = any(count >= 3 for count in suit_counts.values())
        
        # Check for straight possibility
        sorted_ranks = sorted(set(ranks))
        if len(sorted_ranks) >= 3:
            for i in range(len(sorted_ranks) - 2):
                if sorted_ranks[i+2] - sorted_ranks[i] <= 4:
                    texture['straight_possible'] = True
                    break
        
        # Classify as wet or dry
        if texture['flush_possible'] or texture['straight_possible']:
            texture['wet'] = True
        else:
            texture['dry'] = True
        
        return texture
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance


class PlayerAnalyzer:
    """Analyzes player statistics and behavior patterns."""
    
    def calculate_vpip(self, hands_played: int, voluntary_hands: int) -> float:
        """
        Calculate VPIP (Voluntarily Put $ In Pot) percentage.
        
        Args:
            hands_played: Total hands played
            voluntary_hands: Hands where player voluntarily put money in pot
            
        Returns:
            VPIP as decimal (0-1)
        """
        if hands_played <= 0:
            return 0.0
        return voluntary_hands / hands_played
    
    def calculate_pfr(self, hands_played: int, preflop_raises: int) -> float:
        """
        Calculate PFR (Preflop Raise) percentage.
        
        Args:
            hands_played: Total hands played
            preflop_raises: Number of preflop raises made
            
        Returns:
            PFR as decimal (0-1)
        """
        if hands_played <= 0:
            return 0.0
        return preflop_raises / hands_played
    
    def calculate_aggression_factor(self, bets: int, raises: int, calls: int) -> float:
        """
        Calculate aggression factor (bets+raises)/calls.
        
        Args:
            bets: Number of bets made
            raises: Number of raises made
            calls: Number of calls made
            
        Returns:
            Aggression factor
        """
        if calls <= 0:
            return float('inf') if (bets + raises) > 0 else 0.0
        return (bets + raises) / calls
    
    def calculate_fold_to_cbet(self, cbet_opportunities: int, folds_to_cbet: int) -> float:
        """
        Calculate fold to continuation bet frequency.
        
        Args:
            cbet_opportunities: Times faced a continuation bet
            folds_to_cbet: Times folded to continuation bet
            
        Returns:
            Fold to c-bet percentage as decimal (0-1)
        """
        if cbet_opportunities <= 0:
            return 0.0
        return folds_to_cbet / cbet_opportunities
    
    def analyze_positional_play(self, position_data: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
        """
        Analyze player's positional tendencies.
        
        Args:
            position_data: Dictionary with position statistics
            
        Returns:
            Positional analysis results
        """
        analysis = {}
        
        for position, stats in position_data.items():
            hands = stats.get('hands', 0)
            vpip_count = stats.get('vpip', 0)
            pfr_count = stats.get('pfr', 0)
            
            if hands > 0:
                position_vpip = vpip_count / hands
                position_pfr = pfr_count / hands
                
                analysis[f'{position}_vpip'] = position_vpip
                analysis[f'{position}_pfr'] = position_pfr
        
        # Calculate positional awareness
        early_vpip = analysis.get('early_position_vpip', 0)
        late_vpip = analysis.get('late_position_vpip', 0)
        
        if early_vpip > 0:
            positional_awareness = (late_vpip - early_vpip) / early_vpip
        else:
            positional_awareness = 0.0
        
        analysis['positional_awareness'] = positional_awareness
        
        return analysis
    
    def classify_player_type(self, stats: Dict[str, float]) -> str:
        """
        Classify player type based on statistics.
        
        Args:
            stats: Dictionary of player statistics
            
        Returns:
            Player type classification
        """
        vpip = stats.get('vpip', 0.0)
        pfr = stats.get('pfr', 0.0)
        aggression_factor = stats.get('aggression_factor', 0.0)
        
        # Basic classification
        if vpip < 0.20:
            tightness = "Tight"
        elif vpip < 0.35:
            tightness = "Normal"
        else:
            tightness = "Loose"
        
        if aggression_factor < 1.0:
            aggression = "Passive"
        elif aggression_factor < 2.5:
            aggression = "Normal"
        else:
            aggression = "Aggressive"
        
        return f"{tightness}-{aggression}"
    
    def calculate_hand_winrate(self, hands_won: int, total_hands: int) -> float:
        """
        Calculate hand win rate.
        
        Args:
            hands_won: Number of hands won
            total_hands: Total hands played
            
        Returns:
            Win rate as decimal (0-1)
        """
        if total_hands <= 0:
            return 0.0
        return hands_won / total_hands
    
    def calculate_bb_winrate(self, net_winnings: float, hands_played: int, big_blind: float) -> float:
        """
        Calculate win rate in big blinds per 100 hands.
        
        Args:
            net_winnings: Net profit/loss
            hands_played: Total hands played
            big_blind: Big blind amount
            
        Returns:
            Win rate in BB/100 hands
        """
        if hands_played <= 0 or big_blind <= 0:
            return 0.0
        
        bb_per_hand = net_winnings / big_blind / hands_played
        return bb_per_hand * 100  # Per 100 hands
    
    def analyze_session_performance(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze performance for a single session.
        
        Args:
            session_data: Session statistics and results
            
        Returns:
            Performance analysis
        """
        hands_played = session_data.get('hands_played', 0)
        hands_won = session_data.get('hands_won', 0)
        starting_stack = session_data.get('starting_stack', 0)
        ending_stack = session_data.get('ending_stack', 0)
        biggest_pot = session_data.get('biggest_pot', 0)
        
        analysis = {
            'hands_played': hands_played,
            'hands_won': hands_won,
            'starting_stack': starting_stack,
            'ending_stack': ending_stack,
            'net_result': ending_stack - starting_stack,
            'biggest_pot': biggest_pot
        }
        
        if hands_played > 0:
            analysis['win_rate'] = hands_won / hands_played
            analysis['profit_per_hand'] = (ending_stack - starting_stack) / hands_played
        else:
            analysis['win_rate'] = 0.0
            analysis['profit_per_hand'] = 0.0
        
        if starting_stack > 0:
            analysis['roi'] = (ending_stack - starting_stack) / starting_stack
        else:
            analysis['roi'] = 0.0
        
        # Session rating
        if analysis['roi'] > 0.1:
            analysis['session_rating'] = 'excellent'
        elif analysis['roi'] > 0.05:
            analysis['session_rating'] = 'good'
        elif analysis['roi'] > -0.05:
            analysis['session_rating'] = 'break_even'
        else:
            analysis['session_rating'] = 'poor'
        
        return analysis
    
    def generate_player_report(self, player_stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive player performance report.
        
        Args:
            player_stats: Complete player statistics
            
        Returns:
            Detailed performance report
        """
        report = {
            'basic_stats': {},
            'playing_style': {},
            'performance_metrics': {},
            'recommendations': []
        }
        
        # Basic statistics
        games_played = player_stats.get('games_played', 0)
        games_won = player_stats.get('games_won', 0)
        total_winnings = player_stats.get('total_winnings', 0)
        
        if games_played > 0:
            report['basic_stats'] = {
                'games_played': games_played,
                'win_rate': games_won / games_played,
                'average_winnings': total_winnings / games_played,
                'total_profit': total_winnings
            }
        
        # Playing style analysis
        vpip = player_stats.get('vpip', 0)
        pfr = player_stats.get('pfr', 0)
        aggression_factor = player_stats.get('aggression_factor', 0)
        
        if vpip > 0 or pfr > 0:
            report['playing_style'] = {
                'player_type': self.classify_player_type(player_stats),
                'vpip': vpip,
                'pfr': pfr,
                'aggression_factor': aggression_factor
            }
        
        # Performance trends and recommendations
        win_rate = report['basic_stats'].get('win_rate', 0)
        
        if win_rate < 0.3:
            report['recommendations'].append("Focus on tighter hand selection")
        if vpip > 0.4:
            report['recommendations'].append("Consider playing fewer hands")
        if aggression_factor < 1.0:
            report['recommendations'].append("Increase aggression with strong hands")
        
        return report
