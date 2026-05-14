from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.analytics_service import (
    get_career_report,
    get_session_report,
    get_session_rows,
)

router = APIRouter(tags=["analytics"])


@router.get("/stats/sessions")
def get_player_sessions(
    player: str = Query(..., description="Player name"),
    limit: int = Query(20, le=100),
):
    """Past game sessions for a player (newest last)."""
    return get_session_rows(player, limit=limit)


@router.get("/analytics/career")
def analytics_career(player: Optional[str] = Query(default=None)) -> dict:
    """Career aggregates + milestones across the player's full session log."""
    return get_career_report(player)


# /latest is declared BEFORE /{session_index} so FastAPI's path matcher tries
# the literal "latest" first instead of trying to parse it as an int.
@router.get("/analytics/sessions/latest")
def analytics_latest_session_report(
    player: Optional[str] = Query(default=None),
) -> dict:
    payload = get_session_report(player, None)
    if not payload.get("report"):
        raise HTTPException(status_code=404, detail="No session data yet")
    return payload


@router.get("/analytics/sessions/{session_index}")
def analytics_session_report(
    session_index: int,
    player: Optional[str] = Query(default=None),
) -> dict:
    payload = get_session_report(player, session_index)
    if not payload.get("report"):
        raise HTTPException(status_code=404, detail="Session report unavailable")
    return payload
