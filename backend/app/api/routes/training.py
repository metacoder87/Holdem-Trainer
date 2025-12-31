from typing import Optional

from fastapi import APIRouter, Query

from pydantic import BaseModel

from app.services.training_service import evaluate_quiz, generate_quiz, load_training_content

router = APIRouter()


@router.get("/training/content")
def training_content():
    return load_training_content()


@router.get("/training/quiz")
def training_quiz(
    quiz_type: str = Query(default="pot_odds"),
    pot_size: Optional[float] = Query(default=None),
    bet_to_call: Optional[float] = Query(default=None),
):
    return generate_quiz(quiz_type, pot_size=pot_size, bet_to_call=bet_to_call)


class QuizAnswer(BaseModel):
    correct_answer: float
    user_answer: float
    tolerance: float = 0.05


@router.post("/training/quiz/evaluate")
def training_quiz_evaluate(payload: QuizAnswer) -> dict:
    return evaluate_quiz(
        payload.correct_answer,
        payload.user_answer,
        tolerance=payload.tolerance,
    )
