from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from pydantic import BaseModel

from app.services.training_service import (
    evaluate_drill,
    evaluate_quiz,
    generate_drill,
    generate_quiz,
    get_training_progress,
    load_training_content,
)

router = APIRouter()


@router.get("/training/content")
def training_content():
    return load_training_content()


@router.get("/training/quiz")
def training_quiz(
    quiz_type: str = Query(default="pot_odds"),
    player: Optional[str] = Query(default=None),
    pot_size: Optional[float] = Query(default=None),
    bet_to_call: Optional[float] = Query(default=None),
):
    return generate_quiz(quiz_type, player_name=player, pot_size=pot_size, bet_to_call=bet_to_call)


@router.get("/training/drill")
def training_drill(
    player: Optional[str] = Query(default=None),
    focus: Optional[str] = Query(default=None),
) -> dict:
    return generate_drill(player_name=player, focus=focus)


class QuizAnswer(BaseModel):
    quiz_id: str
    player: Optional[str] = None
    user_answer: Any
    tolerance: float = 0.05


@router.post("/training/quiz/evaluate")
def training_quiz_evaluate(payload: QuizAnswer) -> dict:
    try:
        return evaluate_quiz(
            payload.quiz_id,
            payload.user_answer,
            player_name=payload.player,
            tolerance=payload.tolerance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class DrillAnswer(BaseModel):
    drill_id: str
    player: Optional[str] = None
    user_answer: Any


@router.post("/training/drill/evaluate")
def training_drill_evaluate(payload: DrillAnswer) -> dict:
    try:
        return evaluate_drill(payload.drill_id, payload.user_answer, player_name=payload.player)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/training/progress")
def training_progress(player: Optional[str] = Query(default=None)) -> dict:
    return get_training_progress(player)
