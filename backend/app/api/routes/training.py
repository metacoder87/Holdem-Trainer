from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from pydantic import BaseModel

from app.services.drill_service import generate_drill, grade_drill, list_focus_areas
from app.services.summary_service import get_training_tracks
from app.services.training_service import evaluate_quiz, generate_quiz, load_training_content

router = APIRouter()


@router.get("/training/content")
def training_content():
    return load_training_content()


@router.get("/training/tracks")
def training_tracks(player: Optional[str] = Query(default=None)) -> dict:
    return get_training_tracks(player)


@router.get("/training/quiz")
def training_quiz(
    quiz_type: str = Query(default="pot_odds"),
    pot_size: Optional[float] = Query(default=None),
    bet_to_call: Optional[float] = Query(default=None),
    fold_equity: Optional[float] = Query(default=None),
):
    return generate_quiz(
        quiz_type,
        pot_size=pot_size,
        bet_to_call=bet_to_call,
        fold_equity=fold_equity,
    )


class QuizAnswer(BaseModel):
    correct_answer: float
    user_answer: float
    tolerance: float = 0.05
    player_name: Optional[str] = None
    quiz_type: Optional[str] = None


@router.post("/training/quiz/evaluate")
def training_quiz_evaluate(payload: QuizAnswer) -> dict:
    return evaluate_quiz(
        payload.correct_answer,
        payload.user_answer,
        tolerance=payload.tolerance,
        player_name=payload.player_name,
        quiz_type=payload.quiz_type,
    )


@router.get("/training/drills/focus-areas")
def training_drill_focus_areas() -> list:
    return list_focus_areas()


class DrillRequest(BaseModel):
    player_name: Optional[str] = None
    focus_area: Optional[str] = None
    difficulty: int = 2
    drill_id: Optional[str] = None


@router.post("/training/drills")
def training_create_drill(payload: DrillRequest) -> dict:
    try:
        return generate_drill(
            player_name=payload.player_name,
            focus_area=payload.focus_area,
            difficulty=payload.difficulty,
            drill_id=payload.drill_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class DrillAnswer(BaseModel):
    drill_id: str
    kind: str
    correct_action: str
    user_answer: str
    player_name: Optional[str] = None
    focus_area: Optional[str] = None


@router.post("/training/drills/answer")
def training_drill_answer(payload: DrillAnswer) -> dict:
    return grade_drill(
        drill_id=payload.drill_id,
        kind=payload.kind,
        correct_action=payload.correct_action,
        user_answer=payload.user_answer,
        player_name=payload.player_name,
        focus_area=payload.focus_area,
    )
