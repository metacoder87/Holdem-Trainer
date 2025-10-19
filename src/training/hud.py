"""
Trainer HUD (Heads-Up Display) for PyHoldem Pro.
Provides real-time opponent statistics and poker education in terminal interface.
"""
from typing import Dict, List, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn
import math


class TrainerHUD:
    """Heads-up display for training mode with opponent statistics and poker insights."""
    
    def __init__(self):
        """Initialize the trainer HUD."""
        self.is_enabled = False
        self.display_mode = 'basic'  # basic, detailed, minimal
        self.console = Console()
        self.opponent_data: Dict[str, Dict[str, Any]] = {}
        self.current_stats = {}
        
        # Color schemes for different player types
        self.player_type_colors = {
            'tight-passive': 'blue',
            'tight-aggressive': 'green', 
            'loose-passive': 'yellow',
            'loose-aggressive': 'red',
            'balanced': 'cyan',
            'unknown': 'white'
        }
        
    def enable(self):
        """Enable the HUD display."""
        self.is_enabled = True
        
    def disable(self):
        """Disable the HUD display."""
        self.is_enabled = False
        
    def set_display_mode(self, mode: str):
        """Set the HUD display mode."""
        if mode in ['basic', 'detailed', 'minimal']:
            self.display_mode = mode
            
    def update_opponent_stats(self, opponent_stats: Dict[str, Dict[str, Any]]):
        """
        Update opponent statistics data.
        
        Args:
            opponent_stats: Dictionary of opponent names and their stats
        """
        self.opponent_data.update(opponent_stats)
        
    def update_current_stats(self, stats: Dict[str, Any]):
        """Update current game situation statistics."""
        self.current_stats = stats
        
    def display_opponent_panel(self) -> Panel:
        """Create a panel displaying opponent statistics."""
        if not self.opponent_data:
            return Panel("No opponent data available", title="🎯 Opponent Analysis")
            
        # Create table for opponent stats
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Player", style="cyan", width=12)
        table.add_column("Type", style="green", width=15)
        table.add_column("VPIP", style="blue", width=8)
        table.add_column("PFR", style="red", width=8)
        table.add_column("AF", style="yellow", width=6)
        table.add_column("Tendency", style="white", width=20)
        
        for opponent, stats in self.opponent_data.items():
            player_type = stats.get('type', 'unknown')
            vpip_pct = f"{stats.get('vpip', 0) * 100:.0f}%"
            pfr_pct = f"{stats.get('pfr', 0) * 100:.0f}%"
            af = f"{stats.get('af', 0.0):.1f}"
            tendency = self._get_tendency_description(stats)
            
            # Color code based on player type
            type_color = self.player_type_colors.get(player_type, 'white')
            
            table.add_row(
                opponent,
                f"[{type_color}]{player_type}[/{type_color}]",
                vpip_pct,
                pfr_pct,
                af,
                tendency
            )
            
        return Panel(table, title="🎯 Opponent Analysis", border_style="bright_blue")
        
    def display_pot_odds_panel(self) -> Panel:
        """Create a panel displaying current pot odds information."""
        pot_size = self.current_stats.get('pot_size', 0)
        bet_to_call = self.current_stats.get('bet_to_call', 0)
        
        if bet_to_call == 0:
            content = Text("No bet to call - you can check or bet", style="green")
            return Panel(content, title="💰 Pot Odds", border_style="green")
            
        pot_odds = bet_to_call / (pot_size + bet_to_call) if (pot_size + bet_to_call) > 0 else 0
        pot_odds_pct = pot_odds * 100
        ratio = (pot_size / bet_to_call) if bet_to_call > 0 else 0
        
        # Create pot odds visualization
        content = Text()
        content.append(f"Pot Size: ${pot_size:.0f}\n", style="white")
        content.append(f"To Call: ${bet_to_call:.0f}\n", style="yellow")
        content.append(f"Pot Odds: {pot_odds_pct:.1f}% ", style="bold cyan")
        content.append(f"({ratio:.1f}:1)\n", style="cyan")
        
        # Add equity requirement
        content.append(f"\nEquity needed: {pot_odds_pct:.1f}%\n", style="bold red")
        
        # Add visual representation
        odds_bar = self._create_odds_bar(pot_odds)
        content.append(f"Visual: {odds_bar}\n", style="green")
        
        return Panel(content, title="💰 Pot Odds Calculator", border_style="yellow")
        
    def display_equity_panel(self) -> Panel:
        """Create a panel displaying hand equity information."""
        hand_equity = self.current_stats.get('hand_equity', 0)
        required_equity = self.current_stats.get('required_equity', 0)
        
        if hand_equity == 0 and required_equity == 0:
            return Panel("Equity information not available", title="📊 Hand Equity")
            
        content = Text()
        
        # Hand equity
        hand_equity_pct = hand_equity * 100
        required_equity_pct = required_equity * 100
        
        content.append(f"Your Equity: {hand_equity_pct:.1f}%\n", style="bold green")
        content.append(f"Required: {required_equity_pct:.1f}%\n", style="bold red")
        
        # Comparison
        if hand_equity > required_equity:
            advantage = (hand_equity - required_equity) * 100
            content.append(f"✅ Profitable call (+{advantage:.1f}%)\n", style="bold green")
            recommendation = "CALL/RAISE"
            rec_color = "green"
        else:
            disadvantage = (required_equity - hand_equity) * 100
            content.append(f"❌ Unprofitable call (-{disadvantage:.1f}%)\n", style="bold red")
            recommendation = "FOLD"
            rec_color = "red"
            
        content.append(f"\nRecommendation: ", style="white")
        content.append(recommendation, style=f"bold {rec_color}")
        
        return Panel(content, title="📊 Hand Equity Analysis", border_style="green")
        
    def display_training_tips_panel(self) -> Panel:
        """Display contextual training tips based on current situation."""
        tips = self._get_contextual_tips()
        
        content = Text()
        for i, tip in enumerate(tips, 1):
            content.append(f"{i}. {tip}\n", style="cyan")
            
        return Panel(content, title="💡 Training Tips", border_style="cyan")
        
    def format_opponent_display(self, opponent_name: str, stats: Dict[str, Any]) -> str:
        """
        Format opponent statistics for display.
        
        Args:
            opponent_name: Name of the opponent
            stats: Opponent statistics
            
        Returns:
            Formatted string for display
        """
        vpip_pct = stats.get('vpip', 0) * 100
        pfr_pct = stats.get('pfr', 0) * 100
        af = stats.get('af', 0.0)
        player_type = stats.get('type', 'unknown')
        
        return (
            f"{opponent_name}: {player_type} "
            f"(VPIP:{vpip_pct:.0f}% PFR:{pfr_pct:.0f}% AF:{af:.1f})"
        )
        
    def generate_pot_odds_display(self, pot_size: float, bet_to_call: float) -> str:
        """Generate pot odds display text."""
        if bet_to_call == 0:
            return "No bet to call"
            
        pot_odds = bet_to_call / (pot_size + bet_to_call)
        pot_odds_pct = pot_odds * 100
        ratio = pot_size / bet_to_call
        
        return f"Pot Odds: {pot_odds_pct:.1f}% ({ratio:.1f}:1) - Need {pot_odds_pct:.1f}% equity"
        
    def generate_equity_display(self, hand_equity: float, required_equity: float) -> str:
        """Generate hand equity display text."""
        hand_pct = hand_equity * 100
        required_pct = required_equity * 100
        
        if hand_equity > required_equity:
            return f"Equity: {hand_pct:.1f}% vs {required_pct:.1f}% required - FAVORABLE"
        else:
            return f"Equity: {hand_pct:.1f}% vs {required_pct:.1f}% required - UNFAVORABLE"
            
    def display_complete_hud(self):
        """Display the complete HUD interface."""
        if not self.is_enabled:
            return
            
        panels = []
        
        # Always show opponent analysis
        opponent_panel = self.display_opponent_panel()
        panels.append(opponent_panel)
        
        # Show pot odds if relevant
        if self.current_stats.get('bet_to_call', 0) > 0:
            pot_odds_panel = self.display_pot_odds_panel()
            panels.append(pot_odds_panel)
            
        # Show equity analysis if available
        if self.current_stats.get('hand_equity', 0) > 0:
            equity_panel = self.display_equity_panel()
            panels.append(equity_panel)
            
        # Show training tips in detailed mode
        if self.display_mode == 'detailed':
            tips_panel = self.display_training_tips_panel()
            panels.append(tips_panel)
            
        # Display panels based on mode
        if self.display_mode == 'minimal':
            # Show only one panel at a time
            if panels:
                self.console.print(panels[0])
        else:
            # Show multiple panels
            if len(panels) <= 2:
                for panel in panels:
                    self.console.print(panel)
            else:
                # Use columns for better layout
                columns = Columns(panels[:2], equal=True)
                self.console.print(columns)
                if len(panels) > 2:
                    for panel in panels[2:]:
                        self.console.print(panel)
                        
    def _get_tendency_description(self, stats: Dict[str, Any]) -> str:
        """Get a brief description of opponent tendencies."""
        player_type = stats.get('type', 'unknown')
        
        descriptions = {
            'tight-passive': "Folds often, calls when betting",
            'tight-aggressive': "Few hands, bets strong",
            'loose-passive': "Many hands, calls too much", 
            'loose-aggressive': "Many hands, bets often",
            'balanced': "Solid fundamentals",
            'unknown': "Insufficient data"
        }
        
        return descriptions.get(player_type, "Unknown style")
        
    def _create_odds_bar(self, pot_odds: float) -> str:
        """Create a visual representation of pot odds."""
        bar_length = 20
        filled_length = int(bar_length * pot_odds)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        return f"[{bar}] {pot_odds*100:.1f}%"
        
    def _get_contextual_tips(self) -> List[str]:
        """Get contextual tips based on current game state."""
        tips = []
        
        # Pot odds tips
        bet_to_call = self.current_stats.get('bet_to_call', 0)
        if bet_to_call > 0:
            pot_odds = self.current_stats.get('pot_odds', 0)
            if pot_odds > 0.3:
                tips.append("High pot odds! You need less equity to call profitably")
            elif pot_odds < 0.15:
                tips.append("Poor pot odds - you need a very strong hand to call")
                
        # Opponent-specific tips
        for opponent, stats in self.opponent_data.items():
            player_type = stats.get('type', '')
            if 'tight' in player_type:
                tips.append(f"{opponent} is tight - bluffs work better against them")
            elif 'loose' in player_type:
                tips.append(f"{opponent} is loose - value bet thinner against them")
                
        # General tips if no specific ones
        if not tips:
            tips = [
                "Consider your position when making decisions",
                "Think about your opponent's likely holdings",
                "Use pot odds to guide your calling decisions"
            ]
            
        return tips[:3]  # Limit to 3 tips to avoid clutter
        
    def display_quiz_interface(self, quiz_data: Dict[str, Any]) -> str:
        """
        Display a quiz question in an attractive format.
        
        Args:
            quiz_data: Quiz question and data
            
        Returns:
            Formatted quiz display
        """
        question = quiz_data.get('question', 'No question available')
        
        # Create quiz panel
        quiz_panel = Panel(
            question,
            title="🎓 TRAINING QUIZ",
            border_style="bright_yellow",
            padding=(1, 2)
        )
        
        self.console.print(quiz_panel)
        
        return "Quiz displayed - waiting for answer..."
        
    def display_quiz_result(self, result: Dict[str, Any]):
        """
        Display quiz result with feedback.
        
        Args:
            result: Quiz evaluation result
        """
        is_correct = result.get('correct', False)
        feedback = result.get('feedback', 'No feedback available')
        explanation = result.get('explanation', '')
        
        # Choose color and icon based on correctness
        if is_correct:
            border_color = "bright_green"
            title = "✅ CORRECT!"
        else:
            border_color = "bright_red" 
            title = "❌ INCORRECT"
            
        content = Text()
        content.append(feedback + "\n\n", style="white")
        
        if explanation:
            content.append(explanation, style="cyan")
            
        result_panel = Panel(
            content,
            title=title,
            border_style=border_color,
            padding=(1, 2)
        )
        
        self.console.print(result_panel)
        
    def display_performance_summary(self, performance: Dict[str, Any]):
        """Display training performance summary."""
        accuracy = performance.get('accuracy', 0)
        total_quizzes = performance.get('total_quizzes', 0)
        streak = performance.get('current_streak', 0)
        grade = performance.get('grade', 'N/A')
        
        # Create performance table
        table = Table(title="📈 Training Performance")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Quizzes", str(total_quizzes))
        table.add_row("Accuracy", f"{accuracy:.1f}%")
        table.add_row("Current Streak", str(streak))
        table.add_row("Grade", grade)
        
        performance_panel = Panel(
            table,
            border_style="bright_blue"
        )
        
        self.console.print(performance_panel)
        
    def clear_display(self):
        """Clear the console display."""
        self.console.clear()
        
    def print_separator(self):
        """Print a visual separator."""
        self.console.print("─" * 80, style="dim")
