from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from app.core.paths import get_data_file
from data.manager import DataManager

router = APIRouter(tags=["analytics"])

@router.get("/stats/sessions")
def get_player_sessions(
    player: str = Query(..., description="Player name"),
    limit: int = Query(20, le=100)
):
    """
    Get past game sessions for a player.
    """
    manager = DataManager(data_file=str(get_data_file()))
    return manager.get_sessions(player, limit=limit)
