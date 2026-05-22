from typing import Any, Dict, List

from app.core.paths import get_data_file

from data.manager import DataManager


def _manager() -> DataManager:
    return DataManager(data_file=str(get_data_file()))


def list_players() -> List[Dict[str, Any]]:
    manager = _manager()
    players = manager.list_players(sort_by="last_played", reverse=True)
    return [
        {
            "name": player.get("name"),
            "bankroll": player.get("bankroll"),
            "last_played": player.get("last_played"),
            "skill_level": player.get("skill_level"),
        }
        for player in players
    ]


def update_bankroll(player_name: str, bankroll: int) -> Dict[str, Any]:
    manager = _manager()
    manager.update_player_bankroll(player_name, int(bankroll))
    player = manager.get_player(player_name) or {}
    return {
        "name": player.get("name", player_name),
        "bankroll": player.get("bankroll", bankroll),
        "last_played": player.get("last_played"),
        "skill_level": player.get("skill_level"),
    }


def create_player(player_name: str, bankroll: int) -> Dict[str, Any]:
    manager = _manager()
    player = manager.create_player(player_name, bankroll)
    return {
        "name": player.get("name"),
        "bankroll": player.get("bankroll"),
        "last_played": player.get("last_played"),
        "skill_level": player.get("skill_level"),
    }


def get_summary() -> Dict[str, Any]:
    manager = _manager()
    return manager.get_data_summary()
