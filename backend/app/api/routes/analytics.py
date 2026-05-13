from fastapi import APIRouter, Query

from app.services.analytics_service import get_session_rows

router = APIRouter(tags=["analytics"])

@router.get("/stats/sessions")
def get_player_sessions(
    player: str = Query(..., description="Player name"),
    limit: int = Query(20, le=100)
):
    """
    Get past game sessions for a player.
    """
    return get_session_rows(player, limit=limit)
