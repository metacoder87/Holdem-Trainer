"""
Input Handler module for user input processing.
Handles validation and parsing of user input.
"""
from typing import List, Optional
import re


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


class InputHandler:
    """
    Handles user input with validation.
    Provides methods for different types of input with retry logic.
    """
    
    def __init__(self):
        """Initialize input handler."""
        self.input_history: List[str] = []
                
    def get_menu_choice(self, options: List[str], prompt: str = "Choose an option") -> int:
        """
        Get menu selection from user.
        
        Args:
            options: List of menu options
            prompt: Input prompt
            
        Returns:
            Selected option number (1-indexed)
        """
        # Display the menu options
        print()
        for i, option in enumerate(options, 1):
            print(f"  {i}. {option}")
        print()
        
        max_option = len(options)
        # Make the prompt more informative
        if max_option == 1:
            full_prompt = f"{prompt} (enter 1): "
        else:
            full_prompt = f"{prompt} (1-{max_option}): "
        
        choice = int(self.get_number_input(full_prompt, min_value=1, max_value=max_option, integer_only=True))
        return choice
        
    def get_yes_no(self, prompt: str) -> bool:
        """
        Get yes/no response from user.
        
        Args:
            prompt: Question to ask
            
        Returns:
            True for yes, False for no
        """
        while True:
            response = input(f"{prompt} (y/n): ").strip().lower()
            self.input_history.append(response)
            
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            else:
                print("❌ Please enter 'y' or 'n'")
                
    def get_text_input(self, prompt: str, min_length: int = 1,
                      max_length: int = 50) -> str:
        """
        Get text input with length validation.
        
        Args:
            prompt: Message to display
            min_length: Minimum string length
            max_length: Maximum string length
            
        Returns:
            Validated text
        """
        while True:
            text = input(prompt).strip()
            self.input_history.append(text)
            
            if min_length <= len(text) <= max_length:
                return text
            else:
                print(f"❌ Please enter between {min_length} and {max_length} characters")
                
    def validate_bet_amount(self, amount: float, min_bet: float, max_bet: float) -> bool:
        """
        Validate a bet amount (enforcing min/max constraints).
        
        Args:
            amount: Bet amount to validate
            min_bet: Minimum allowed bet
            max_bet: Maximum allowed bet (player's stack)
            
        Returns:
            True if valid, False otherwise
        """
        return min_bet <= amount <= max_bet
        
    def validate_player_name(self, name: str) -> bool:
        """
        Validate player name (alphanumeric only, reasonable length).
        
        Args:
            name: Name to validate
            
        Returns:
            True if valid, False otherwise
        """
        if len(name) < 2:
            return False
            
        if len(name) > 20:
            return False
            
        # Allow letters, numbers, spaces, underscores
        return bool(re.match(r'^[a-zA-Z0-9_ ]+$', name))
        
    def get_bet_amount(self, min_bet: float, max_bet: float) -> float:
        """
        Get bet amount from user with validation.
        
        Args:
            min_bet: Minimum bet allowed
            max_bet: Maximum bet allowed (usually player's stack)
            
        Returns:
            Valid bet amount
        """
        while True:
            amount = self.get_number_input(
                f"Enter bet amount (${min_bet:.0f} - ${max_bet:.0f}): ",
                min_value=min_bet,
                max_value=max_bet,
                integer_only=True
            )
            
            if self.validate_bet_amount(amount, min_bet, max_bet):
                return amount
            else:
                print(f"❌ Bet must be between ${min_bet:.0f} and ${max_bet:.0f}")
                
    def confirm_action(self, action: str, amount: float = 0) -> bool:
        """
        Confirm a significant action (preventing misclicks).
        
        Args:
            action: Action to confirm
            amount: Optional amount
            
        Returns:
            True if confirmed
        """
        if amount > 0:
            return self.get_yes_no(f"Confirm {action} ${amount:.0f}?")
        else:
            return self.get_yes_no(f"Confirm {action}?")
            
    def wait_for_enter(self, message: str = "Press Enter to continue...") -> None:
        """Wait for user to press Enter."""
        input(message)
        self.input_history.append("")
        
    def get_input_with_timeout(self, prompt: str, timeout: int = 30) -> Optional[str]:
        """
        Get input with timeout (for decision timing analysis).
        Note: Basic implementation, real timeout requires threading/signal
        
        Args:
            prompt: Input prompt
            timeout: Timeout in seconds
            
        Returns:
            User input or None if timeout
        """
        # Simplified version without actual timeout (would require threading)
        # Real implementation would use signal.alarm or threading.Timer
        return input(prompt).strip()
        
    def get_yes_no_input(self, prompt: str) -> bool:
        """
        Alias for get_yes_no for compatibility.
        
        Args:
            prompt: Question to ask
            
        Returns:
            True for yes, False for no
        """
        return self.get_yes_no(prompt)
        
    def get_number_input(self, prompt: str, min_value: Optional[float] = None, 
                        max_value: Optional[float] = None, integer_only: bool = False) -> float:
        """
        Get numeric input with optional range validation (simplified signature).
        
        Args:
            prompt: Message to display
            min_value: Optional minimum value
            max_value: Optional maximum value
            integer_only: If True, only accept integer inputs
            
        Returns:
            Validated number
        """
        min_val = min_value if min_value is not None else float('-inf')
        max_val = max_value if max_value is not None else float('inf')
        
        while True:
            try:
                user_input = input(prompt).strip()
                if not user_input:
                    print("❌ Please enter a number.")
                    continue
                    
                self.input_history.append(user_input)
                
                # Parse as integer or float based on requirement
                if integer_only:
                    # Check for decimal point
                    if '.' in user_input:
                        print("❌ Please enter a whole number (no decimals).")
                        continue
                    value = int(user_input)
                else:
                    value = float(user_input)
                    
                # Validate range
                if min_val <= value <= max_val:
                    return value
                else:
                    if min_value is not None and max_value is not None:
                        if integer_only:
                            print(f"❌ Please enter a whole number between {int(min_val)} and {int(max_val)}")
                        else:
                            print(f"❌ Please enter a number between {min_val} and {max_val}")
                    elif min_value is not None:
                        print(f"❌ Please enter a number >= {min_val}")
                    elif max_value is not None:
                        print(f"❌ Please enter a number <= {max_val}")
                    
            except ValueError:
                if integer_only:
                    print("❌ Invalid input. Please enter a whole number.")
                else:
                    print("❌ Invalid input. Please enter a valid number.")
            except KeyboardInterrupt:
                print("\n\nGame interrupted by user.")
                raise
