#!/usr/bin/env python3
"""
PyHoldem Pro - Terminal Texas Hold'em Poker Game

Main entry point for the game application.
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from ui.display import GameDisplay
from ui.input_handler import InputHandler
from data.manager import DataManager
from game.game_engine import GameEngine


def main():
    """Main game entry point."""
    try:
        # Initialize display
        display = GameDisplay()
        display.show_welcome_screen()
        
        # Initialize data manager
        data_manager = DataManager()
        
        # Initialize input handler
        input_handler = InputHandler()
        
        # Main game loop
        while True:
            # Player selection/creation
            player = handle_player_selection(data_manager, input_handler, display)
            if not player:
                break  # User chose to exit
                
            # Game mode selection
            game_mode = handle_game_mode_selection(input_handler, display)
            if not game_mode:
                continue  # Back to player selection
                
            # Start game
            game_engine = GameEngine(player, data_manager, display, input_handler)
            game_engine.start_game(game_mode)
            
            # Ask if user wants to play again
            if not input_handler.get_yes_no_input("Would you like to play again?"):
                break
                
        display.show_goodbye_message()
        
    except KeyboardInterrupt:
        print("\n\nGame interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        print("Please report this issue if it persists.")
    finally:
        # Clean up resources if needed
        pass


def handle_player_selection(data_manager, input_handler, display):
    """Handle player selection or creation."""
    while True:
        display.show_player_menu()
        choice = input_handler.get_menu_choice(["Create New Player", "Select Existing Player", "Exit"])
        
        if choice == 1:
            # Create new player
            player = create_new_player(data_manager, input_handler, display)
            if player:
                return player
                
        elif choice == 2:
            # Select existing player
            player = select_existing_player(data_manager, input_handler, display)
            if player:
                return player
                
        elif choice == 3:
            # Exit
            return None
            
        else:
            display.show_error("Invalid choice. Please try again.")


def create_new_player(data_manager, input_handler, display):
    """Create a new player profile."""
    while True:
        display.clear_screen()
        display.show_header("Create New Player")
        
        # Get player name
        name = input_handler.get_text_input("Enter player name: ")
        if not name:
            display.show_error("Player name cannot be empty.")
            continue
            
        # Check if name already exists
        if data_manager.player_exists(name):
            display.show_error(f"Player '{name}' already exists.")
            continue
            
        # Get starting bankroll
        while True:
            try:
                bankroll = input_handler.get_number_input(
                    "Enter starting bankroll (minimum 1000): ", 
                    min_value=1000
                )
                break
            except ValueError as e:
                display.show_error(str(e))
                
        # Create player
        try:
            player_data = data_manager.create_player(name, bankroll)
            data_manager.save_players()
            display.show_success(f"Player '{name}' created successfully!")
            return player_data
        except Exception as e:
            display.show_error(f"Failed to create player: {e}")
            return None


def select_existing_player(data_manager, input_handler, display):
    """Select an existing player profile."""
    players = data_manager.list_players()
    
    if not players:
        display.show_error("No players found. Please create a new player first.")
        return None
        
    display.clear_screen()
    display.show_header("Select Player")
    display.show_player_list(players)
    
    # Get player selection
    try:
        choice = input_handler.get_number_input(
            f"Enter player number (1-{len(players)}) or 0 to go back: ",
            min_value=0,
            max_value=len(players)
        )
        
        if choice == 0:
            return None
            
        selected_player = players[choice - 1]
        display.show_success(f"Selected player: {selected_player['name']}")
        return selected_player
        
    except ValueError as e:
        display.show_error(str(e))
        return None


def handle_game_mode_selection(input_handler, display):
    """Handle game mode selection."""
    display.clear_screen()
    display.show_header("Game Mode Selection")
    
    # Game type selection
    game_types = ["Cash Game", "Tournament", "Back to Player Selection"]
    type_choice = input_handler.get_menu_choice(game_types)
    
    if type_choice == 3:  # Back
        return None
        
    game_type = "cash" if type_choice == 1 else "tournament"
    
    # Limit type selection
    display.show_subheader("Select Limit Type")
    limit_types = ["No Limit", "Limit", "Back"]
    limit_choice = input_handler.get_menu_choice(limit_types)
    
    if limit_choice == 3:  # Back
        return handle_game_mode_selection(input_handler, display)
        
    limit_type = "no_limit" if limit_choice == 1 else "limit"
    
    return {
        'type': game_type,
        'limit': limit_type
    }


if __name__ == "__main__":
    main()
