"""
Helper utilities for PyHoldem Pro.
Contains formatting, validation, and utility functions used across modules.
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta


def format_currency(amount: float, symbol: str = "$") -> str:
    """Format amount as currency with proper comma separation."""
    return f"{symbol}{amount:,.0f}"


def format_percentage(value: float, decimal_places: int = 1) -> str:
    """Format decimal as percentage."""
    return f"{value * 100:.{decimal_places}f}%"


def format_ratio(value: float, decimal_places: int = 1) -> str:
    """Format as ratio (e.g., 3.5:1)."""
    return f"{value:.{decimal_places}f}:1"


def format_time_elapsed(seconds: int) -> str:
    """Format seconds into readable time string."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def calculate_pot_odds_ratio(pot: float, bet: float) -> float:
    """Calculate pot odds as a ratio (avoiding division by zero)."""
    if bet == 0:
        return float('inf')
    return pot / bet


def calculate_required_equity(pot_odds: float) -> float:
    """Calculate required equity from pot odds."""
    if pot_odds == float('inf'):
        return 0.0
    return 1.0 / (pot_odds + 1.0)


def format_hand_range(range_str: str) -> str:
    """Format hand range string for display."""
    # Simple formatting, could be enhanced
    return range_str.upper().replace(',', ', ')


def truncate_string(text: str, max_length: int = 50) -> str:
    """Truncate string to max length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def calculate_bb_per_100(profit: float, hands: int, big_blind: float) -> float:
    """
    Calculate BB/100 hands (standard poker win rate metric).
    
    Args:
        profit: Total profit
        hands: Number of hands played
        big_blind: Big blind amount
        
    Returns:
        BB/100 hands
    """
    if hands == 0 or big_blind == 0:
        return 0.0
        
    # Convert to big blinds
    profit_in_bb = profit / big_blind
    
    # Calculate per 100 hands
    return (profit_in_bb / hands) * 100


def estimate_variance(win_rate: float, hands: int) -> float:
    """
    Estimate variance (rough approximation for user understanding).
    
    Args:
        win_rate: Win rate (BB/100)
        hands: Number of hands
        
    Returns:
        Estimated standard deviation
    """
    if hands < 10:
        return 0.0
        
    # Simplified variance calculation
    # Real variance is complex and game-dependent
    base_variance = 100  # Typical poker variance
    return base_variance / (hands ** 0.5)


def get_position_name(position: int, num_players: int) -> str:
    """
    Get readable position name based on seat and player count.
    
    Args:
        position: Seat position relative to dealer
        num_players: Total players
        
    Returns:
        Position name (BTN, CO, MP, etc.)
    """
    if num_players <= 2:
        return "BTN" if position == 0 else "BB"
        
    # Position names for full ring
    positions = {
        0: "BTN",  # Button
        1: "SB",   # Small Blind
        2: "BB",   # Big Blind
        3: "UTG",  # Under the Gun
        4: "MP",   # Middle Position
        5: "CO",   # Cutoff
    }
    
    return positions.get(position, f"Seat {position + 1}")


def validate_hand_range(range_string: str) -> bool:
    """
    Validate hand range string format (basic validation).
    
    Args:
        range_string: Range in standard notation
        
    Returns:
        True if valid format
    """
    # Basic validation - would need full parser for production
    if not range_string:
        return False
        
    # Check for valid characters (ranks, suits, operators)
    valid_chars = set('AKQJT98765432so+,-')
    return all(c in valid_chars for c in range_string.replace(' ', ''))


def categorize_hand_strength(equity: float) -> str:
    """
    Categorize hand strength based on equity.
    
    Args:
        equity: Hand equity (0-1)
        
    Returns:
        Strength category
    """
    if equity >= 0.80:
        return "Monster"
    elif equity >= 0.65:
        return "Strong"
    elif equity >= 0.50:
        return "Medium"
    elif equity >= 0.35:
        return "Marginal"
    else:
        return "Weak"


def calculate_m_ratio(stack: float, small_blind: float, big_blind: float) -> float:
    """
    Calculate M-ratio for tournament play (measure of stack health).
    
    Args:
        stack: Current stack size
        small_blind: Small blind amount
        big_blind: Big blind amount
        
    Returns:
        M-ratio
    """
    blinds_per_round = small_blind + big_blind
    if blinds_per_round == 0:
        return float('inf')
        
    return stack / blinds_per_round


def categorize_m_ratio(m: float) -> str:
    """
    Categorize M-ratio into zones (Harrington zones).
    
    Args:
        m: M-ratio value
        
    Returns:
        Zone name
    """
    if m >= 20:
        return "Green Zone (Comfortable)"
    elif m >= 10:
        return "Yellow Zone (Caution)"
    elif m >= 6:
        return "Orange Zone (Danger)"
    elif m >= 1:
        return "Red Zone (Critical)"
    else:
        return "Dead Zone"


def format_session_duration(start_time: datetime, end_time: datetime = None) -> str:
    """Format session duration."""
    if end_time is None:
        end_time = datetime.now()
        
    duration = end_time - start_time
    hours = duration.seconds // 3600
    minutes = (duration.seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def suggest_break(hands_played: int, session_start: datetime) -> bool:
    """
    Suggest break to user (preventing fatigue-induced mistakes).
    
    Args:
        hands_played: Hands played in session
        session_start: Session start time
        
    Returns:
        True if break suggested
    """
    duration = datetime.now() - session_start
    
    # Suggest break after 90 minutes or 200 hands
    if duration > timedelta(minutes=90):
        return True
    if hands_played > 200:
        return True
        
    return False
