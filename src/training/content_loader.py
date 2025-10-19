"""
Educational Content Loader for PyHoldem Pro.
Loads poker tips, vocabulary, strategy guides, and cheat sheets.
"""
import json
import os
from typing import Dict, List, Any, Optional


class ContentLoader:
    """Loads and manages educational poker content."""
    
    def __init__(self, content_directory: str = "educational_content"):
        """
        Initialize the content loader.
        
        Args:
            content_directory: Directory containing educational content files
        """
        self.content_dir = content_directory
        self._ensure_content_directory()
        
    def _ensure_content_directory(self):
        """Ensure the educational content directory exists."""
        os.makedirs(self.content_dir, exist_ok=True)
        
    def load_tips(self) -> List[Dict[str, Any]]:
        """Load poker tips and tricks."""
        tips_file = os.path.join(self.content_dir, "poker_tips.json")
        
        if os.path.exists(tips_file):
            try:
                with open(tips_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
                
        # Return default tips if file doesn't exist
        return self._get_default_tips()
        
    def load_vocabulary(self) -> List[Dict[str, Any]]:
        """Load poker vocabulary and definitions."""
        vocab_file = os.path.join(self.content_dir, "poker_vocabulary.json")
        
        if os.path.exists(vocab_file):
            try:
                with open(vocab_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
                
        return self._get_default_vocabulary()
        
    def load_strategy_guides(self) -> List[Dict[str, Any]]:
        """Load strategy guides and articles."""
        strategy_file = os.path.join(self.content_dir, "strategy_guides.json")
        
        if os.path.exists(strategy_file):
            try:
                with open(strategy_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
                
        return self._get_default_strategies()
        
    def load_cheat_sheets(self) -> Dict[str, Any]:
        """Load poker cheat sheets and quick references."""
        cheat_sheet_file = os.path.join(self.content_dir, "cheat_sheets.json")
        
        if os.path.exists(cheat_sheet_file):
            try:
                with open(cheat_sheet_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
                
        return self._get_default_cheat_sheets()
        
    def save_content_files(self):
        """Save all default content to files."""
        # Save tips
        tips_file = os.path.join(self.content_dir, "poker_tips.json")
        with open(tips_file, 'w', encoding='utf-8') as f:
            json.dump(self._get_default_tips(), f, indent=2, ensure_ascii=False)
            
        # Save vocabulary
        vocab_file = os.path.join(self.content_dir, "poker_vocabulary.json")
        with open(vocab_file, 'w', encoding='utf-8') as f:
            json.dump(self._get_default_vocabulary(), f, indent=2, ensure_ascii=False)
            
        # Save strategies
        strategy_file = os.path.join(self.content_dir, "strategy_guides.json")
        with open(strategy_file, 'w', encoding='utf-8') as f:
            json.dump(self._get_default_strategies(), f, indent=2, ensure_ascii=False)
            
        # Save cheat sheets
        cheat_sheet_file = os.path.join(self.content_dir, "cheat_sheets.json")
        with open(cheat_sheet_file, 'w', encoding='utf-8') as f:
            json.dump(self._get_default_cheat_sheets(), f, indent=2, ensure_ascii=False)
            
    def _get_default_tips(self) -> List[Dict[str, Any]]:
        """Get default poker tips."""
        return [
            {
                "title": "Position is Power",
                "content": "Play more hands in late position (button and cutoff) and fewer hands in early position. Acting last gives you more information and control.",
                "category": "fundamental",
                "difficulty": "beginner"
            },
            {
                "title": "Tight is Right (Usually)",
                "content": "Play fewer, stronger hands. A common beginner mistake is playing too many hands. Start tight and loosen up as you improve.",
                "category": "fundamental", 
                "difficulty": "beginner"
            },
            {
                "title": "Pot Odds Are Your Friend",
                "content": "Calculate pot odds to make mathematically sound decisions. If you need to call $10 into a $40 pot, you need 20% equity to break even.",
                "category": "math",
                "difficulty": "intermediate"
            },
            {
                "title": "Aggression Pays",
                "content": "Betting and raising is usually better than calling. You can win by making your opponent fold or by having the best hand at showdown.",
                "category": "strategy",
                "difficulty": "intermediate"
            },
            {
                "title": "Watch Your Opponents",
                "content": "Pay attention to betting patterns, timing tells, and opponent tendencies. Tight players rarely bluff, loose players call too often.",
                "category": "psychology",
                "difficulty": "intermediate"
            },
            {
                "title": "Bankroll Management",
                "content": "Never play with more than 5% of your bankroll at any single table. This protects you from going broke during bad runs.",
                "category": "bankroll",
                "difficulty": "beginner"
            },
            {
                "title": "Value Betting",
                "content": "When you have a strong hand, bet for value against weaker hands that might call. Size your bets to maximize profit from worse hands.",
                "category": "betting",
                "difficulty": "intermediate"
            },
            {
                "title": "Bluffing Basics",
                "content": "Bluff against tight players and on scary boards. Avoid bluffing calling stations (loose-passive players) who rarely fold.",
                "category": "bluffing",
                "difficulty": "intermediate"
            },
            {
                "title": "Continuation Betting",
                "content": "If you raised preflop, consider betting the flop (~70% of the time) even if you missed. Many opponents will fold weak hands.",
                "category": "betting",
                "difficulty": "advanced"
            },
            {
                "title": "Hand Reading",
                "content": "Try to put opponents on a range of hands, not just one specific hand. Consider their position, actions, and tendencies.",
                "category": "advanced",
                "difficulty": "advanced"
            }
        ]
        
    def _get_default_vocabulary(self) -> List[Dict[str, Any]]:
        """Get default poker vocabulary."""
        return [
            {
                "term": "VPIP",
                "definition": "Voluntarily Put $ In Pot - Percentage of hands a player plays by calling or raising preflop",
                "example": "A tight player might have a VPIP of 15%, while a loose player might have 40%"
            },
            {
                "term": "PFR",
                "definition": "Preflop Raise - Percentage of hands a player raises preflop",
                "example": "An aggressive player with 20% VPIP and 16% PFR raises most hands they play"
            },
            {
                "term": "Aggression Factor",
                "definition": "(Bets + Raises) ÷ Calls - Measures how aggressive a player is postflop",
                "example": "AF of 3.0 means the player bets/raises 3 times for every call"
            },
            {
                "term": "Pot Odds",
                "definition": "The ratio of the current pot size to the bet you must call",
                "example": "If pot is $100 and you must call $25, you're getting 4:1 pot odds (20% equity needed)"
            },
            {
                "term": "Equity",
                "definition": "Your percentage chance of winning the hand if all cards were dealt out",
                "example": "Pocket aces have about 85% equity against a random hand preflop"
            },
            {
                "term": "Outs",
                "definition": "Cards that will improve your hand to likely best hand",
                "example": "With a flush draw, you typically have 9 outs (remaining cards of your suit)"
            },
            {
                "term": "Position",
                "definition": "Where you sit relative to the dealer button - affects betting order",
                "example": "Late position (button/cutoff) is strongest, early position (UTG) is weakest"
            },
            {
                "term": "Continuation Bet (C-bet)",
                "definition": "Betting on the flop after you raised preflop",
                "example": "You raise with AK, opponent calls, flop comes 9-7-2, you bet - that's a c-bet"
            },
            {
                "term": "Bluff Catcher",
                "definition": "A medium-strength hand that can only beat bluffs",
                "example": "Third pair on a scary board - it beats bluffs but loses to value bets"
            },
            {
                "term": "Nuts",
                "definition": "The best possible hand given the board cards",
                "example": "On a board of A-K-Q-J-10 rainbow, the nuts would be any straight"
            },
            {
                "term": "Drawing Dead",
                "definition": "Having no outs - no cards can improve your hand to win",
                "example": "Having 7-2 against AA on a board of A-A-K-Q-J"
            },
            {
                "term": "Implied Odds",
                "definition": "Pot odds considering money you might win on future betting rounds",
                "example": "Calling a small bet with a draw, expecting to win a big pot if you hit"
            }
        ]
        
    def _get_default_strategies(self) -> List[Dict[str, Any]]:
        """Get default strategy guides."""
        return [
            {
                "title": "Preflop Hand Selection",
                "content": """
                **EARLY POSITION (UTG, UTG+1):**
                Play tight - only premium hands:
                • Pocket Pairs: AA, KK, QQ, JJ, 10-10
                • Suited: AKs, AQs, AJs
                • Offsuit: AK, AQ
                
                **MIDDLE POSITION (MP, MP+1):**
                Add some medium hands:
                • Pocket Pairs: 99, 88, 77
                • Suited: KQs, QJs, JTs, A10s, KJs
                • Offsuit: AJ, KQ
                
                **LATE POSITION (CO, BTN):**
                Play more hands for value and position:
                • Pocket Pairs: Any pair 22+
                • Suited: Any two cards 9+ or suited connectors 54s+
                • Offsuit: A9+, K10+, QJ, J10
                
                **BLINDS:**
                Defend wider against raises, but be careful out of position.
                """,
                "category": "preflop",
                "difficulty": "beginner"
            },
            {
                "title": "Postflop Continuation Betting",
                "content": """
                **WHEN TO C-BET:**
                • You have a strong hand or draw
                • Board is dry (like A-7-2 rainbow)
                • Opponent is tight and likely to fold
                • You're in position
                
                **C-BET SIZING:**
                • Strong hands: 65-75% pot for value
                • Bluffs: 50-65% pot for fold equity
                • Dry boards: Smaller sizing (40-50%)
                • Wet boards: Larger sizing (70-80%)
                
                **WHEN NOT TO C-BET:**
                • Very wet, coordinated boards (9-8-7 with two suits)
                • Against multiple opponents
                • When opponent is loose-passive (calling station)
                • When you have no equity and no fold equity
                """,
                "category": "postflop",
                "difficulty": "intermediate"
            },
            {
                "title": "Pot Odds and Drawing Hands",
                "content": """
                **CALCULATING POT ODDS:**
                1. Add bet you must call to current pot
                2. Divide your call by the total
                3. Compare to your equity percentage
                
                **COMMON DRAWS AND ODDS:**
                • Flush draw (9 outs): ~35% equity (need 22% pot odds)
                • Open-ended straight (8 outs): ~31% equity (need 24% pot odds)
                • Gutshot straight (4 outs): ~16% equity (need 40% pot odds)
                • Two overcards (6 outs): ~24% equity (need 30% pot odds)
                
                **RULE OF 4 AND 2:**
                • After flop: Multiply outs by 4 for approximate %
                • After turn: Multiply outs by 2 for approximate %
                
                Example: 9 outs after flop = 9 × 4 = 36% equity
                """,
                "category": "math",
                "difficulty": "intermediate"
            },
            {
                "title": "Reading Opponent Types",
                "content": """
                **TIGHT-AGGRESSIVE (TAG):**
                • VPIP: 15-25%, PFR: 12-20%
                • Strategy: Rarely bluffs, value bets strong hands
                • Counter: Bluff more, fold to their aggression
                
                **LOOSE-AGGRESSIVE (LAG):**
                • VPIP: 25-40%, PFR: 18-35%
                • Strategy: Plays many hands aggressively
                • Counter: Tighten up, value bet thinner
                
                **TIGHT-PASSIVE (Rock):**
                • VPIP: 10-20%, PFR: 5-12%
                • Strategy: Plays few hands, calls more than raises
                • Counter: Steal their blinds, value bet thin
                
                **LOOSE-PASSIVE (Fish):**
                • VPIP: 30-60%, PFR: 5-15%
                • Strategy: Calls too much, rarely raises
                • Counter: Value bet heavily, avoid bluffs
                """,
                "category": "psychology",
                "difficulty": "advanced"
            }
        ]
        
    def _get_default_cheat_sheets(self) -> Dict[str, Any]:
        """Get default cheat sheets."""
        return {
            "starting_hands": {
                "premium": ["AA", "KK", "QQ", "JJ", "AKs", "AK"],
                "strong": ["1010", "AQs", "AQ", "AJs", "KQs", "KQ"],
                "playable": ["99", "88", "77", "AJ", "A10s", "KJs", "QJs", "JTs"],
                "marginal": ["66", "55", "44", "33", "22", "A9s", "K10s", "Q10s", "J9s"]
            },
            "pot_odds_chart": {
                "2_to_1": {"percentage": 33.3, "example": "$20 call into $40 pot"},
                "3_to_1": {"percentage": 25.0, "example": "$10 call into $30 pot"},
                "4_to_1": {"percentage": 20.0, "example": "$10 call into $40 pot"},
                "5_to_1": {"percentage": 16.7, "example": "$10 call into $50 pot"}
            },
            "common_draws": {
                "flush_draw": {"outs": 9, "flop_equity": 35, "turn_equity": 19},
                "open_ended_straight": {"outs": 8, "flop_equity": 31, "turn_equity": 17},
                "gutshot": {"outs": 4, "flop_equity": 16, "turn_equity": 9},
                "two_pair_to_full_house": {"outs": 4, "flop_equity": 16, "turn_equity": 9}
            },
            "position_names": {
                "UTG": "Under the Gun - First to act preflop",
                "MP": "Middle Position",
                "CO": "Cutoff - One seat right of button",
                "BTN": "Button - Best position, acts last postflop",
                "SB": "Small Blind - Posts small blind",
                "BB": "Big Blind - Posts big blind"
            },
            "betting_patterns": {
                "value_betting": "Bet strong hands to get called by worse hands",
                "bluffing": "Bet weak hands to make better hands fold",
                "slow_playing": "Play strong hands passively to trap opponents",
                "semi_bluffing": "Bet draws that can improve to best hand"
            }
        }
        
    def get_random_tip(self) -> Dict[str, Any]:
        """Get a random poker tip."""
        tips = self.load_tips()
        if tips:
            import random
            return random.choice(tips)
        return {"title": "No tips available", "content": ""}
        
    def get_tips_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get tips filtered by category."""
        tips = self.load_tips()
        return [tip for tip in tips if tip.get('category') == category]
        
    def get_tips_by_difficulty(self, difficulty: str) -> List[Dict[str, Any]]:
        """Get tips filtered by difficulty level."""
        tips = self.load_tips()
        return [tip for tip in tips if tip.get('difficulty') == difficulty]
        
    def search_vocabulary(self, search_term: str) -> List[Dict[str, Any]]:
        """Search vocabulary for terms containing the search term."""
        vocab = self.load_vocabulary()
        search_lower = search_term.lower()
        
        return [
            term for term in vocab 
            if search_lower in term.get('term', '').lower() or 
               search_lower in term.get('definition', '').lower()
        ]
        
    def get_cheat_sheet(self, sheet_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific cheat sheet by name."""
        cheat_sheets = self.load_cheat_sheets()
        return cheat_sheets.get(sheet_name)
