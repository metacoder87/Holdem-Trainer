"""
Test suite for UI components.
Tests display, input handling, and user interaction.
"""
import pytest
from unittest.mock import Mock, patch, call
from io import StringIO
from ui.display import Display, TableDisplay, HandDisplay
from ui.input_handler import InputHandler, ValidationError
from game.player import Player
from game.card import Card, Suit, Rank
from game.table import Table, TableType


class TestInputHandler:
    """Test cases for InputHandler class."""
    
    def test_input_handler_creation(self):
        """Test creating an input handler."""
        handler = InputHandler()
        assert handler is not None
        
    def test_get_number_input_valid(self):
        """Test getting valid number input."""
        handler = InputHandler()
        
        with patch('builtins.input', return_value='5'):
            result = handler.get_number_input("Enter number: ", 1, 10)
            assert result == 5
            
    def test_get_number_input_invalid_then_valid(self):
        """Test number input with retry on invalid."""
        handler = InputHandler()
        
        # Returns invalid values that fail validation
        with patch('builtins.input', side_effect=['abc', '15', '5']):
            result = handler.get_number_input("Enter number: ", 1, 10)
            assert result == 5
            
    def test_get_menu_choice(self):
        """Test getting menu choice."""
        handler = InputHandler()
        options = ['Fold', 'Call', 'Raise']
        
        with patch('builtins.input', return_value='2'):
            choice = handler.get_menu_choice(options)
            assert choice == 2
            
    def test_get_yes_no_input(self):
        """Test yes/no input."""
        handler = InputHandler()
        
        with patch('builtins.input', return_value='y'):
            result = handler.get_yes_no("Continue?")
            assert result is True
            
        with patch('builtins.input', return_value='n'):
            result = handler.get_yes_no("Continue?")
            assert result is False
            
    def test_validate_bet_amount(self):
        """Test bet amount validation."""
        handler = InputHandler()
        
        # Valid bet
        assert handler.validate_bet_amount(100, 50, 500) is True
        
        # Too low
        assert handler.validate_bet_amount(30, 50, 500) is False
        
        # Too high
        assert handler.validate_bet_amount(600, 50, 500) is False


class TestDisplay:
    """Test cases for Display class."""
    
    def test_display_creation(self):
        """Test creating a display."""
        display = Display()
        assert display is not None
        
    def test_clear_screen(self):
        """Test screen clearing."""
        display = Display()
        # Should not raise errors
        display.clear_screen()
        
    def test_display_title(self):
        """Test displaying title."""
        display = Display()
        with patch('sys.stdout', new=StringIO()) as fake_out:
            display.display_title()
            output = fake_out.getvalue()
            assert 'PyHoldem Pro' in output
            
    def test_display_message(self):
        """Test displaying message."""
        display = Display()
        with patch('sys.stdout', new=StringIO()) as fake_out:
            display.display_message("Test message")
            output = fake_out.getvalue()
            assert 'Test message' in output
            
    def test_display_error(self):
        """Test displaying error."""
        display = Display()
        with patch('sys.stdout', new=StringIO()) as fake_out:
            display.display_error("Error message")
            output = fake_out.getvalue()
            assert 'Error' in output or 'error' in output
            
    def test_display_section_header(self):
        """Test displaying section header."""
        display = Display()
        with patch('sys.stdout', new=StringIO()) as fake_out:
            display.display_section_header("Section Title")
            output = fake_out.getvalue()
            assert 'Section Title' in output


class TestTableDisplay:
    """Test cases for TableDisplay class."""
    
    def test_table_display_creation(self):
        """Test creating a table display."""
        display = TableDisplay()
        assert display is not None
        
    def test_display_table_state(self):
        """Test displaying table state."""
        display = TableDisplay()
        
        # Create mock table
        table = Table(TableType.CASH_GAME, max_players=6)
        player = Player("Test", 1000)
        table.add_player(player)
        
        # Should not raise errors
        with patch('sys.stdout', new=StringIO()):
            display.display_table_state(table, pot_size=100)
            
    def test_display_community_cards(self):
        """Test displaying community cards."""
        display = TableDisplay()
        
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.KING),
            Card(Suit.CLUBS, Rank.QUEEN)
        ]
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            display.display_community_cards(cards)
            output = fake_out.getvalue()
            # Should display cards
            assert len(output) > 0
            
    def test_display_pot_info(self):
        """Test displaying pot information."""
        display = TableDisplay()
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            display.display_pot_info(pot_size=250, current_bet=50)
            output = fake_out.getvalue()
            assert '250' in output
            
    def test_display_player_action(self):
        """Test displaying player action."""
        display = TableDisplay()
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            display.display_player_action("Alice", "raises", 100)
            output = fake_out.getvalue()
            assert 'Alice' in output
            assert 'raise' in output.lower()


class TestHandDisplay:
    """Test cases for HandDisplay class."""
    
    def test_hand_display_creation(self):
        """Test creating a hand display."""
        display = HandDisplay()
        assert display is not None
        
    def test_display_hole_cards(self):
        """Test displaying hole cards."""
        display = HandDisplay()
        
        cards = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.SPADES, Rank.KING)
        ]
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            display.display_hole_cards(cards)
            output = fake_out.getvalue()
            # Should show both cards
            assert len(output) > 0
            
    def test_format_card(self):
        """Test card formatting."""
        display = HandDisplay()
        
        card = Card(Suit.HEARTS, Rank.ACE)
        formatted = display.format_card(card)
        
        # Should include rank and suit indicator
        assert 'A' in formatted or 'Ace' in formatted
        # Suit can be symbol or letter (♥ or H)
        assert any(char in formatted for char in ['♥', 'H', 'Hearts'])
        
    def test_display_hand_strength(self):
        """Test displaying hand strength indicator."""
        display = HandDisplay()
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            display.display_hand_strength("Strong", 0.85)
            output = fake_out.getvalue()
            assert 'Strong' in output or 'strong' in output


class TestDisplayIntegration:
    """Test cases for integrated display functionality."""
    
    def test_full_table_display(self):
        """Test displaying complete table state."""
        table_display = TableDisplay()
        hand_display = HandDisplay()
        
        # Create game state
        table = Table(TableType.CASH_GAME, max_players=6)
        player1 = Player("Alice", 1000)
        player2 = Player("Bob", 800)
        table.add_player(player1)
        table.add_player(player2)
        
        community = [
            Card(Suit.HEARTS, Rank.ACE),
            Card(Suit.DIAMONDS, Rank.KING),
            Card(Suit.CLUBS, Rank.QUEEN)
        ]
        
        # Should display without errors
        with patch('sys.stdout', new=StringIO()):
            table_display.display_table_state(table, pot_size=200)
            table_display.display_community_cards(community)
            hand_display.display_hole_cards(player1.hole_cards)
            
    def test_action_menu_display(self):
        """Test displaying action menu."""
        display = Display()
        handler = InputHandler()
        
        options = ['Fold', 'Check', 'Call $50', 'Raise']
        
        with patch('sys.stdout', new=StringIO()):
            display.display_menu("Your action:", options)
            
    def test_statistics_display(self):
        """Test displaying player statistics."""
        display = Display()
        
        stats = {
            'hands_played': 100,
            'vpip': 0.25,
            'pfr': 0.18,
            'aggression': 2.3
        }
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            display.display_statistics(stats)
            output = fake_out.getvalue()
            assert '100' in output  # hands played


class TestInputValidation:
    """Test cases for input validation."""
    
    def test_validate_player_name(self):
        """Test player name validation."""
        handler = InputHandler()
        
        # Valid names
        assert handler.validate_player_name("Alice") is True
        assert handler.validate_player_name("Bob123") is True
        
        # Invalid names (empty, too short, special chars)
        assert handler.validate_player_name("") is False
        assert handler.validate_player_name("A") is False
        assert handler.validate_player_name("@#$%") is False
        
    def test_validate_bet_sizing(self):
        """Test bet size validation rules."""
        handler = InputHandler()
        
        # Minimum bet is big blind
        assert handler.validate_bet_amount(20, 10, 1000) is True
        
        # Below minimum
        assert handler.validate_bet_amount(5, 10, 1000) is False
        
        # All-in (equal to max)
        assert handler.validate_bet_amount(1000, 10, 1000) is True
        
        # Over max
        assert handler.validate_bet_amount(1500, 10, 1000) is False


class TestEquityDisplay:
    """Test cases for equity calculator display."""
    
    def test_display_pot_odds(self):
        """Test pot odds display."""
        display = Display()
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            display.display_pot_odds(pot=150, bet_to_call=50)
            output = fake_out.getvalue()
            # Should show 3:1 odds
            assert '3' in output
            
    def test_display_hand_equity(self):
        """Test hand equity display."""
        display = Display()
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            display.display_hand_equity(0.65)
            output = fake_out.getvalue()
            # Should show 65%
            assert '65' in output
            
    def test_display_decision_suggestion(self):
        """Test decision suggestion display."""
        display = Display()
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            display.display_decision_suggestion(
                "CALL",
                reason="You have 35% equity and getting 3:1 odds"
            )
            output = fake_out.getvalue()
            assert 'CALL' in output or 'call' in output


class TestTimingDisplay:
    """Test cases for decision timing display."""
    
    def test_display_timer(self):
        """Test action timer display."""
        display = Display()
        
        with patch('sys.stdout', new=StringIO()):
            display.display_timer(time_remaining=30)
            
    def test_display_timing_warning(self):
        """Test timing consistency warning."""
        display = Display()
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            display.display_timing_warning(
                "Your strong hands take 25s but weak hands take 5s"
            )
            output = fake_out.getvalue()
            assert len(output) > 0
