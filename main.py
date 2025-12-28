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
from game.player import Player
from training.content_loader import ContentLoader
from training.trainer import PokerTrainer, QuizType
from training.adaptive_trainer import AdaptiveTrainer
from training.progression_analyzer import WeaknessType
from training.career_tracker import CareerTracker
from training.analyzer import SessionReviewer


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

            if game_mode.get("type") == "training":
                run_training_session(player, data_manager, input_handler, display)
                continue
                
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
            
            # Convert player_data dict to Player object
            player = Player(player_data['name'], player_data['bankroll'])
            return player
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
        choice = int(input_handler.get_number_input(
            f"Enter player number (1-{len(players)}) or 0 to go back: ",
            min_value=0,
            max_value=len(players),
            integer_only=True
        ))
        
        if choice == 0:
            return None
            
        selected_player_data = players[choice - 1]
        display.show_success(f"Selected player: {selected_player_data['name']}")
        
        # Convert player_data dict to Player object
        player = Player(selected_player_data['name'], selected_player_data['bankroll'])
        return player
        
    except ValueError as e:
        display.show_error(str(e))
        return None


def handle_game_mode_selection(input_handler, display):
    """Handle game mode selection."""
    display.clear_screen()
    display.show_header("Game Mode Selection")
    
    # Game type selection
    game_types = ["Cash Game", "Tournament", "Training Session", "Back to Player Selection"]
    type_choice = input_handler.get_menu_choice(game_types)
    
    if type_choice == 4:  # Back
        return None

    if type_choice == 3:
        return {"type": "training"}

    game_type = "cash" if type_choice == 1 else "tournament"
    
    # Limit type selection
    display.show_subheader("Select Limit Type")
    limit_types = ["No Limit", "Limit", "Back"]
    limit_choice = input_handler.get_menu_choice(limit_types)
    
    if limit_choice == 3:  # Back
        return handle_game_mode_selection(input_handler, display)
        
    limit_type = "no_limit" if limit_choice == 1 else "limit"

    training_enabled = input_handler.get_yes_no_input("Enable in-game training (quizzes/tips)?")
    hud_enabled = False
    post_hand_feedback = False
    if training_enabled:
        hud_enabled = input_handler.get_yes_no_input("Enable HUD (opponent stats / pot odds)?")
        post_hand_feedback = input_handler.get_yes_no_input("Enable post-hand feedback?")
    
    return {
        'type': game_type,
        'limit': limit_type,
        'training': training_enabled,
        'in_game_quizzes': training_enabled,
        'hud': hud_enabled,
        'post_hand_feedback': post_hand_feedback,
    }


def run_training_session(player: Player, data_manager, input_handler, display) -> None:
    """Run a standalone training session (quizzes + study prompts)."""
    display.clear_screen()
    display.show_header("Training Session")

    import random

    player_record = {}
    if data_manager:
        try:
            record = data_manager.get_player(player.name)
            if isinstance(record, dict):
                player_record = record
        except Exception:
            player_record = {}

    skill_level = player_record.get("skill_level", "unknown")
    weaknesses = player_record.get("weaknesses", [])
    recommended_topics = player_record.get("recommended_topics", [])
    sessions = player_record.get("sessions", []) if isinstance(player_record.get("sessions"), list) else []
    recent_hands = (
        player_record.get("recent_hands", []) if isinstance(player_record.get("recent_hands"), list) else []
    )

    if weaknesses:
        print(f"Current skill level: {skill_level}")
        print(f"Focus areas: {', '.join(weaknesses)}")
        if recommended_topics:
            print(f"Recommended topics: {', '.join(recommended_topics)}")
    else:
        print("No personalized analysis yet. Play some hands to generate your first profile.")

    trainer = PokerTrainer()
    trainer.enable_training()
    content = ContentLoader()
    reviewer = SessionReviewer()

    weakness_enums = []
    if isinstance(weaknesses, list):
        for w in weaknesses:
            try:
                weakness_enums.append(WeaknessType(str(w)))
            except Exception:
                continue

    adaptive = AdaptiveTrainer(player.name)
    # Restore prior practice history/difficulty if present.
    existing_practice = player_record.get("practice_history")
    if isinstance(existing_practice, list):
        adaptive.practice_history = list(existing_practice)
    try:
        adaptive.current_difficulty = int(player_record.get("training_difficulty", adaptive.current_difficulty))
    except Exception:
        pass

    practice_events_this_session = 0

    while True:
        print("\nWhat would you like to do?")
        choice = input_handler.get_menu_choice(
            [
                "Personalized Drill (from your weaknesses)",
                "Quick Quiz (Pot Odds)",
                "Quick Quiz (Mixed Fundamentals)",
                "Practice Scenario (from your weaknesses)",
                "Review Recent Hands",
                "Session Review (Last Session)",
                "Career Report",
                "Show Random Tip",
                "Export Default Study Content Files",
                "Back",
            ]
        )

        if choice == 10:
            return

        if choice == 8:
            tip = content.get_random_tip()
            print("\n" + "-" * 70)
            print(f"Tip: {tip.get('title', '')}")
            print(tip.get("content", ""))
            print("-" * 70)
            continue

        if choice == 9:
            content.save_content_files()
            display.show_success("Saved default educational content to `educational_content/`.")
            continue

        if choice == 7:
            career = CareerTracker(player.name)
            for s in sessions:
                if not isinstance(s, dict):
                    continue
                session_copy = dict(s)
                session_copy["profit"] = session_copy.get("profit", session_copy.get("net_result", 0))
                career.record_session(session_copy)

            metrics = career.get_career_metrics()
            print("\n" + "-" * 70)
            print("📈 Career Report")
            print(f"  Sessions: {metrics.total_sessions}  |  Hands: {metrics.total_hands}")
            print(f"  Avg VPIP: {metrics.avg_vpip*100:.1f}%  |  Avg PFR: {metrics.avg_pfr*100:.1f}%")
            print(f"  Avg AF: {metrics.avg_aggression_factor:.2f}")
            print(f"  Total Profit: ${metrics.total_profit:.0f}")
            milestones = career.get_milestones()
            if milestones:
                print("  Milestones:")
                for m in milestones[-3:]:
                    print(f"    - {m.get('type')} (hands: {m.get('total_hands')})")
            print("-" * 70)
            continue

        if choice == 6:
            last_session = player_record.get("last_session")
            if not isinstance(last_session, dict):
                last_session = sessions[-1] if sessions and isinstance(sessions[-1], dict) else None
            if not isinstance(last_session, dict):
                print("No session data available yet. Play a few hands first.")
                continue

            session_for_review = dict(last_session)
            session_for_review["net_result"] = int(session_for_review.get("profit", 0) or 0)
            report = reviewer.generate_session_report(session_for_review)

            print("\n" + "-" * 70)
            summary = report.get("session_summary", {})
            grade = report.get("overall_grade", {})
            print("🧾 Last Session Review")
            print(f"  Hands: {summary.get('hands_played', 0)}")
            print(f"  Net: ${summary.get('net_result', 0):.0f}  |  BB/100: {summary.get('bb_per_100', 0):.1f}")
            print(f"  Grade: {grade.get('letter', '?')} ({grade.get('percentage', 0):.1f}%)")

            leaks = report.get("identified_leaks", []) or []
            if leaks:
                print("\nLeaks to work on:")
                for leak in leaks[:3]:
                    print(f"  - {leak.get('description', '')}")

            recs = report.get("recommendations", []) or []
            if recs:
                print("\nTop fixes:")
                for rec in recs[:3]:
                    print(f"  - {rec.get('action', '')}")
                    if rec.get("specific"):
                        print(f"    {rec.get('specific')}")
            print("-" * 70)
            continue

        if choice == 5:
            stored_hands = []
            if data_manager:
                try:
                    load_fn = getattr(data_manager, "load_hand_history", None)
                    if callable(load_fn):
                        stored_hands = load_fn(player.name, limit=50, reverse=True) or []
                except Exception:
                    stored_hands = []

            hands_for_review = []
            if stored_hands:
                hands_for_review = [h for h in stored_hands if isinstance(h, dict)]
            elif recent_hands:
                hands_for_review = [h for h in list(recent_hands)[-50:] if isinstance(h, dict)]
                hands_for_review.reverse()  # newest-first

            if not hands_for_review:
                print("No hand history saved yet. Play a few hands first.")
                continue

            show_count = min(10, len(hands_for_review))
            hands_slice = hands_for_review[:show_count]
            print("\nHands:")
            for i, hand in enumerate(hands_slice, 1):
                hand_no = hand.get("hand_number", "?")
                pot_total = hand.get("pot_total", 0)
                winners = hand.get("winners", [])
                winners_str = ", ".join(winners) if isinstance(winners, list) else str(winners)
                print(f"  {i}. Hand {hand_no} | Pot ${pot_total:.0f} | Winners: {winners_str}")

            choice_idx = int(
                input_handler.get_number_input(
                    f"View which hand (1-{show_count})? 0 to go back: ",
                    min_value=0,
                    max_value=show_count,
                    integer_only=True,
                )
            )
            if choice_idx == 0:
                continue

            selected = hands_slice[choice_idx - 1]
            view_mode = input_handler.get_menu_choice(
                [
                    "Quick view (print full hand)",
                    "Replay (street-by-street)",
                    "Back",
                ],
                "How would you like to view it",
            )
            if view_mode == 3:
                continue

            try:
                from training.hand_replayer import HandReplayer

                replayer = HandReplayer(hero_name=player.name)
                mode = "print" if view_mode == 1 else "street"
                replayer.replay(selected, input_handler=input_handler, mode=mode)
            except Exception as e:
                print(f"Failed to replay hand: {e}")

            continue

        if choice in (1, 4) and not weakness_enums:
            print("No weaknesses on file yet. Play a session to generate personalized recommendations.")
            continue

        if choice in (1, 4):
            weakness_labels = [w.value.replace("_", " ").title() for w in weakness_enums] + ["Back"]
            weakness_choice = input_handler.get_menu_choice(weakness_labels, "Choose a focus area") - 1
            if weakness_choice == len(weakness_labels) - 1:
                continue
            weakness = weakness_enums[weakness_choice]

            if choice == 4:
                scenario = adaptive.create_practice_scenario(weakness)
                print("\n" + "-" * 70)
                print("🎯 Practice Scenario")
                for k, v in scenario.items():
                    print(f"{k.replace('_', ' ').title()}: {v}")
                print("-" * 70)
                adaptive.track_practice_result(
                    {"weakness_type": weakness.value, "correct": True, "time_taken": 0}
                )
                practice_events_this_session += 1
                continue

            # Personalized drill (quiz) based on weakness
            if weakness == WeaknessType.POOR_POT_ODDS:
                pot_size = int(input_handler.get_number_input("Pot size (50-500)? ", 50, 500, integer_only=True))
                bet_to_call = int(
                    input_handler.get_number_input(
                        "Bet to call (10-250)? ", 10, min(250, pot_size), integer_only=True
                    )
                )
                quiz = trainer.generate_quiz(QuizType.POT_ODDS, pot_size=pot_size, bet_to_call=bet_to_call)
                print("\n" + "-" * 70)
                print(quiz["question"])
                user_answer = input_handler.get_number_input("Your answer (%): ", 0, 100, integer_only=True)
                result = trainer.evaluate_answer(quiz["correct_answer"], user_answer, tolerance=0.05)
                print(result["feedback"])
                print(quiz["explanation"])
                print("-" * 70)
                adaptive.track_practice_result(
                    {"weakness_type": weakness.value, "correct": bool(result.get("correct")), "time_taken": 0}
                )
                practice_events_this_session += 1
                continue

            if weakness in (WeaknessType.TOO_PASSIVE, WeaknessType.POOR_BET_SIZING):
                pot_size = int(input_handler.get_number_input("Pot size (50-500)? ", 50, 500, integer_only=True))
                quiz = trainer.generate_quiz(QuizType.BET_SIZING, pot_size=pot_size)
                print("\n" + "-" * 70)
                print(quiz["question"])
                user_answer = input_handler.get_number_input(
                    "Your answer ($): ", 0, max(1, pot_size * 3), integer_only=True
                )
                result = trainer.evaluate_answer(float(quiz["correct_answer"]), float(user_answer), tolerance=0.2)
                print(result["feedback"])
                print(quiz["explanation"])
                print("-" * 70)
                adaptive.track_practice_result(
                    {"weakness_type": weakness.value, "correct": bool(result.get("correct")), "time_taken": 0}
                )
                practice_events_this_session += 1
                continue

            # Fallback: scenario-based training (reflection).
            scenario = adaptive.create_practice_scenario(weakness)
            print("\n" + "-" * 70)
            print("🎯 Scenario Drill")
            print(f"Weakness focus: {weakness.value}")
            for k, v in scenario.items():
                print(f"{k.replace('_', ' ').title()}: {v}")
            print("-" * 70)
            adaptive.track_practice_result({"weakness_type": weakness.value, "correct": True, "time_taken": 0})
            practice_events_this_session += 1
            continue

        num_questions = int(
            input_handler.get_number_input(
                "How many questions (1-20)? ",
                min_value=1,
                max_value=20,
                integer_only=True,
            )
        )

        for _ in range(num_questions):
            if choice == 1:
                quiz_type = QuizType.POT_ODDS
            else:
                quiz_type = trainer.get_random_quiz_type()

            # Generate values for quizzes.
            if quiz_type in (QuizType.POT_ODDS, QuizType.REQUIRED_EQUITY, QuizType.IMPLIED_ODDS):
                pot_size = int(input_handler.get_number_input("Pot size (50-500)? ", 50, 500, integer_only=True))
                bet_to_call = int(
                    input_handler.get_number_input(
                        "Bet to call (10-250)? ", 10, min(250, pot_size), integer_only=True
                    )
                )
                quiz = trainer.generate_quiz(quiz_type, pot_size=pot_size, bet_to_call=bet_to_call)
                print("\n" + "-" * 70)
                print(quiz["question"])
                user_answer = input_handler.get_number_input("Your answer (%): ", 0, 100, integer_only=True)
                result = trainer.evaluate_answer(quiz["correct_answer"], user_answer, tolerance=0.05)
                print(result["feedback"])
                print(quiz["explanation"])
                print("-" * 70)
            elif quiz_type == QuizType.BET_SIZING:
                pot_size = int(input_handler.get_number_input("Pot size (50-500)? ", 50, 500, integer_only=True))
                quiz = trainer.generate_quiz(quiz_type, pot_size=pot_size)
                print("\n" + "-" * 70)
                print(quiz["question"])
                user_answer = input_handler.get_number_input(
                    "Your answer ($): ", 0, max(1, pot_size * 3), integer_only=True
                )
                result = trainer.evaluate_answer(float(quiz["correct_answer"]), float(user_answer), tolerance=0.2)
                print(result["feedback"])
                print(quiz["explanation"])
                print("-" * 70)
            else:
                # Unsupported quiz types fall back to tips.
                tip = content.get_random_tip()
                print("\n" + "-" * 70)
                print(f"Tip: {tip.get('title', '')}")
                print(tip.get("content", ""))
                print("-" * 70)

        summary = trainer.get_performance_summary()
        print("\nTraining summary:")
        print(f"  Accuracy: {summary['accuracy']:.1f}%  |  Grade: {summary['grade']}")
        print(f"  Message: {summary['message']}")

        if data_manager:
            try:
                updates = {"training_quiz_summary": summary}
                if practice_events_this_session > 0:
                    updates.update(
                        {
                            "practice_history": adaptive.practice_history,
                            "practice_stats": adaptive.get_practice_statistics(),
                            "training_difficulty": adaptive.current_difficulty,
                        }
                    )
                data_manager.update_player_stats(player.name, updates)
                data_manager.save_player(player)
            except Exception:
                pass

if __name__ == "__main__":
    main()
