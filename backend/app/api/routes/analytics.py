from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.analytics_service import (
    get_analytics_summary,
    get_career,
    get_ev_summary,
    get_leaks,
    get_session_report,
)

router = APIRouter()


@router.get("/analytics/summary")
def analytics_summary(player: Optional[str] = Query(default=None)) -> dict:
    return get_analytics_summary(player)


@router.get("/analytics/leaks")
def analytics_leaks(player: Optional[str] = Query(default=None)) -> dict:
    return get_leaks(player)


@router.get("/analytics/career")
def analytics_career(player: Optional[str] = Query(default=None)) -> dict:
    return get_career(player)


@router.get("/analytics/ev")
def analytics_ev(player: Optional[str] = Query(default=None)) -> dict:
    return get_ev_summary(player)


# Important: declare /latest before /{session_index} so FastAPI's path matcher
# tries the literal first; otherwise "latest" would 422 against the int param.
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
