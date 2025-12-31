from typing import List

from fastapi import APIRouter, HTTPException

from app.services.summary_service import get_player, list_players

router = APIRouter()


@router.get("/players")
def players_index() -> List[dict]:
    return list_players()


@router.get("/players/{player_name}")
def player_detail(player_name: str) -> dict:
    player = get_player(player_name)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player
