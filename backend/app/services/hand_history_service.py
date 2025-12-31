from typing import Any, Dict, List, Optional

from app.core.paths import get_data_file

from data.manager import DataManager


def list_hands(player_name: str, *, limit: int = 50, reverse: bool = True) -> List[Dict[str, Any]]:
    manager = DataManager(data_file=str(get_data_file()))
    return manager.load_hand_history(player_name, limit=limit, reverse=reverse)


def get_hand(player_name: str, hand_number: int) -> Optional[Dict[str, Any]]:
    if hand_number <= 0:
        return None
    hands = list_hands(player_name, limit=200, reverse=False)
    for hand in hands:
        if int(hand.get("hand_number", 0) or 0) == int(hand_number):
            return hand
    return None
