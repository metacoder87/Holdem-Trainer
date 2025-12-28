"""
Display module for terminal-based poker UI.
Handles all visual output to the terminal.
"""
import os
import sys
from typing import List, Dict, Any, Optional
from game.card import Card
from game.table import Table


class Display:
    """
    Main display class for terminal output.
    Provides methods for showing game information to the user.
    """
    
    def __init__(self):
        """Initialize the display."""
        self.use_colors = self._check_color_support()
        
    def _check_color_support(self) -> bool:
        """Check if terminal supports colors (avoiding platform issues)."""
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        
    def clear_screen(self) -> None:
        """Clear the terminal screen (platform-independent)."""
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def display_title(self) -> None:
        """Display game title banner."""
        print("\n" + "="*70)
        print("   🃏  PyHoldem Pro - Terminal Texas Hold'em Poker  🃏")
        print("="*70 + "\n")
        
    def display_message(self, message: str, prefix: str = "") -> None:
        """Display a general message."""
        if prefix:
            print(f"{prefix} {message}")
        else:
            print(message)
            
    def display_error(self, message: str) -> None:
        """Display error message (using prefix to avoid parsing ANSI codes)."""
        print(f"❌ ERROR: {message}")
        
    def display_success(self, message: str) -> None:
        """Display success message."""
        print(f"✅ {message}")
        
    def display_section_header(self, title: str) -> None:
        """Display a section header."""
        print(f"\n{'─'*70}")
        print(f"  {title}")
        print('─'*70)
        
    def display_menu(self, prompt: str, options: List[str]) -> None:
        """Display a menu with numbered options."""
        print(f"\n{prompt}")
        for i, option in enumerate(options, 1):
            print(f"  {i}. {option}")
        print()
        
    def display_statistics(self, stats: Dict[str, Any]) -> None:
        """Display player statistics."""
        print("\n📊 Statistics:")
        for key, value in stats.items():
            # Format key for display
            formatted_key = key.replace('_', ' ').title()
            
            # Format value based on type
            if isinstance(value, float):
                if 0 <= value <= 1:  # Likely a percentage
                    formatted_value = f"{value*100:.1f}%"
                else:
                    formatted_value = f"{value:.2f}"
            else:
                formatted_value = str(value)
                
            print(f"  {formatted_key}: {formatted_value}")
            
    def display_pot_odds(self, pot: float, bet_to_call: float) -> None:
        """Display pot odds calculation."""
        if bet_to_call == 0:
            print("💡 Pot Odds: N/A (free to see)")
            return
            
        odds = pot / bet_to_call
        pot_odds_ratio = f"{odds:.1f}:1"
        
        # Calculate percentage needed to win
        percentage_needed = (1 / (odds + 1)) * 100
        
        print(f"💡 Pot Odds: {pot_odds_ratio}")
        print(f"   You need to win {percentage_needed:.0f}% of the time to break even")
        
    def display_hand_equity(self, equity: float) -> None:
        """Display hand equity percentage."""
        percentage = equity * 100
        print(f"📈 Hand Equity: {percentage:.1f}%")
        
        # Visual indicator using blocks
        blocks = int(percentage / 10)
        bar = '█' * blocks + '░' * (10 - blocks)
        print(f"   [{bar}]")
        
    def display_decision_suggestion(self, action: str, reason: str) -> None:
        """Display suggested action with reasoning."""
        print(f"\n💭 Suggested Action: {action}")
        print(f"   Reason: {reason}")
        
    def display_timer(self, time_remaining: int) -> None:
        """Display action timer."""
        print(f"⏱️  Time: {time_remaining}s", end='\r')
        
    def display_timing_warning(self, warning: str) -> None:
        """Display warning about timing tells."""
        print(f"\n⚠️  Timing Tell Detected:")
        print(f"   {warning}")
        print(f"   Try to take consistent time for all decisions")


class TableDisplay(Display):
    """
    Specialized display for poker table visualization.
    Extends base Display with table-specific rendering.
    """
    
    def display_table_state(self, table: Table, pot_size: float = 0,
                           current_bet: float = 0) -> None:
        """Display current table state with all players."""
        self.display_section_header("TABLE")
        
        print(f"  Pot: ${pot_size:.0f}  |  Current Bet: ${current_bet:.0f}")
        print()
        
        # Display dealer position
        print(f"  Dealer Button: Seat {table.dealer_position + 1}")
        
        # Display each player
        for i, player in enumerate(table.get_players_in_order()):
            if player:
                self._display_player_info(player, i + 1)
                
    def _display_player_info(self, player, seat_num: int) -> None:
        """Display individual player information."""
        status = []
        if player.folded:
            status.append("FOLDED")
        if player.all_in:
            status.append("ALL-IN")
            
        status_str = f" [{', '.join(status)}]" if status else ""
        
        print(f"  Seat {seat_num}: {player.name}")
        print(f"    Chips: ${player.bankroll:.0f}  |  Bet: ${player.current_bet:.0f}{status_str}")
        
    def display_community_cards(self, cards: List[Card]) -> None:
        """Display community cards (board)."""
        if not cards:
            return
            
        print("\n  Community Cards:")
        print("  ", end="")
        for card in cards:
            print(f"[{self._format_card(card)}]", end=" ")
        print("\n")
        
    def _format_card(self, card: Card) -> str:
        """Format a card for display with suit symbol."""
        # Using unicode suit symbols
        suit_symbols = {
            'Hearts': '♥',
            'Diamonds': '♦',
            'Spades': '♠',
            'Clubs': '♣'
        }
        
        rank_display = card.rank.name if card.rank.value >= 11 else str(card.rank.value)
        suit_symbol = suit_symbols.get(card.suit.name, card.suit.name[0])
        
        return f"{rank_display}{suit_symbol}"
        
    def display_pot_info(self, pot_size: float, current_bet: float = 0) -> None:
        """Display pot and bet information."""
        print(f"💰 Pot: ${pot_size:.0f}")
        if current_bet > 0:
            print(f"   Current Bet: ${current_bet:.0f}")
            
    def display_player_action(self, player_name: str, action: str, amount: float = 0) -> None:
        """Display a player's action."""
        if amount > 0:
            print(f"👤 {player_name} {action}s ${amount:.0f}")
        else:
            print(f"👤 {player_name} {action}s")


class HandDisplay(Display):
    """
    Specialized display for hand-related information.
    Shows hole cards, hand strength, and analysis.
    """
    
    def display_hole_cards(self, cards: List[Card], hidden: bool = False) -> None:
        """Display player's hole cards."""
        print("\n  Your Cards:")
        if hidden:
            print("  [??] [??]")
        else:
            print("  ", end="")
            for card in cards:
                print(f"[{self.format_card(card)}]", end=" ")
            print()
            
    def format_card(self, card: Card) -> str:
        """Format a single card for display."""
        suit_symbols = {
            'Hearts': '♥',
            'Diamonds': '♦',
            'Spades': '♠',
            'Clubs': '♣'
        }
        
        # Use short rank names for face cards
        rank_map = {
            14: 'A', 13: 'K', 12: 'Q', 11: 'J'
        }
        
        rank_display = rank_map.get(card.rank.value, str(card.rank.value))
        suit_symbol = suit_symbols.get(card.suit.name, card.suit.name[0])
        
        return f"{rank_display}{suit_symbol}"
        
    def display_hand_strength(self, description: str, equity: float) -> None:
        """Display hand strength with visual indicator."""
        print(f"\n  Hand Strength: {description}")
        
        # Visual equity bar
        percentage = equity * 100
        blocks = int(percentage / 10)
        bar = '█' * blocks + '░' * (10 - blocks)
        print(f"  Equity: [{bar}] {percentage:.0f}%")
        
    def display_hand_analysis(self, analysis: Dict[str, Any]) -> None:
        """Display detailed hand analysis."""
        print("\n📋 Hand Analysis:")
        
        if 'outs' in analysis:
            print(f"  Outs: {analysis['outs']}")
            
        if 'pot_odds' in analysis:
            print(f"  Pot Odds: {analysis['pot_odds']}")
            
        if 'recommendation' in analysis:
            print(f"  Recommendation: {analysis['recommendation']}")


class GameDisplay(TableDisplay, HandDisplay):
    """
    Combined display class for main game interface.
    Inherits from both TableDisplay and HandDisplay to provide
    complete game visualization capabilities.
    """
    
    def show_welcome_screen(self) -> None:
        """Display welcome screen with game title and info."""
        self.clear_screen()
        print("\n" + "="*70)
        print("   🃏  PyHoldem Pro - Terminal Texas Hold'em Poker  🃏")
        print("="*70)
        print("\n  Welcome to PyHoldem Pro!")
        print("  A comprehensive Texas Hold'em poker training platform")
        print("\n  Features:")
        print("  • Cash games and tournaments")
        print("  • Multiple AI opponents with unique playing styles")
        print("  • Training mode with hand analysis and feedback")
        print("  • Comprehensive statistics tracking")
        print("  • Educational content and strategy guides")
        print("\n" + "="*70 + "\n")
        input("  Press Enter to continue...")
        
    def show_goodbye_message(self) -> None:
        """Display goodbye message."""
        self.clear_screen()
        print("\n" + "="*70)
        print("   Thanks for playing PyHoldem Pro!")
        print("   See you at the tables! 🃏")
        print("="*70 + "\n")
        
    def show_player_menu(self) -> None:
        """Display player selection menu."""
        self.clear_screen()
        self.display_section_header("PLAYER MANAGEMENT")
        
    def show_header(self, title: str) -> None:
        """Display a header with title."""
        print("\n" + "="*70)
        print(f"  {title}")
        print("="*70 + "\n")
        
    def show_subheader(self, title: str) -> None:
        """Display a subheader."""
        print(f"\n{title}")
        print("-" * len(title))
        
    def show_error(self, message: str) -> None:
        """Display error message."""
        self.display_error(message)
        
    def show_success(self, message: str) -> None:
        """Display success message."""
        self.display_success(message)
        
    def show_player_list(self, players: List[Dict[str, Any]]) -> None:
        """Display list of players."""
        print("\nAvailable Players:")
        print("-" * 70)
        for i, player in enumerate(players, 1):
            print(f"  {i}. {player['name']}")
            print(f"     Bankroll: ${player['bankroll']:.0f}")
            if 'hands_played' in player:
                print(f"     Hands Played: {player['hands_played']}")
            print()
            
    def show_game_menu(self) -> None:
        """Display game menu."""
        self.clear_screen()
        self.display_section_header("GAME MENU")
