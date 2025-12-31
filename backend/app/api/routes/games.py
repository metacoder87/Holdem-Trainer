from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.game_service import (
    create_session,
    get_hand_state,
    get_session,
    list_modes,
    simulate_hand,
    start_hand,
    submit_input,
)

router = APIRouter()


class SessionCreate(BaseModel):
    player_name: Optional[str] = None
    game_type: Optional[str] = "cash"
    limit_type: Optional[str] = "no_limit"
    small_blind: Optional[int] = None
    big_blind: Optional[int] = None
    starting_chips: Optional[int] = None
    buy_in: Optional[int] = None
    opponents: Optional[int] = None
    training: Optional[bool] = None
    in_game_quizzes: Optional[bool] = None
    hud: Optional[bool] = None
    post_hand_feedback: Optional[bool] = None


class HandInput(BaseModel):
    choice: Optional[int] = None
    value: Optional[Any] = None


@router.get("/games/modes")
def game_modes():
    return list_modes()


@router.post("/games/sessions")
def game_sessions_create(payload: SessionCreate) -> dict:
    try:
        session = create_session(payload.dict(exclude_none=True))
        return session
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/games/sessions/{session_id}")
def game_session_detail(session_id: str) -> dict:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/games/sessions/{session_id}/hand/start")
def game_session_start_hand(session_id: str) -> dict:
    try:
        return start_hand(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/games/sessions/{session_id}/hand")
def game_session_hand_state(session_id: str) -> dict:
    try:
        return get_hand_state(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/games/sessions/{session_id}/hand/input")
def game_session_hand_input(session_id: str, payload: HandInput) -> dict:
    value = payload.choice if payload.choice is not None else payload.value
    if value is None:
        raise HTTPException(status_code=422, detail="Input value is required")
    try:
        return submit_input(session_id, value)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/games/sessions/{session_id}/demo-hand")
def game_session_demo(session_id: str) -> dict:
    try:
        return simulate_hand(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
