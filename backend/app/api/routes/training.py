from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from pydantic import BaseModel, Field

from app.services.training_service import (
    evaluate_drill,
    evaluate_quiz,
    generate_drill,
    generate_quiz,
    get_adaptive_progression,
    get_training_progress,
    load_training_content,
    next_bandit_topic,
    record_bandit_outcome,
    record_scenario_elo,
    review_srs_card,
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


# ---------- Track 4: Adaptive engine endpoints ----------


@router.get("/training/progression")
def training_progression(player: Optional[str] = Query(default=None)) -> dict:
    """Bandit + SRS + Elo snapshot for the progression dashboard.

    Returns ``{bandit[], next_topic, srs:{due_count, due_card_ids},
    elo:{player_rating, attempts}}``. Stable shape so the UI can
    rely on these keys without conditional checks.
    """
    return get_adaptive_progression(player)


@router.get("/training/progression/next-topic")
def training_progression_next_topic(
    player: Optional[str] = Query(default=None),
) -> dict:
    """Thompson-sample the next drill topic.

    Read-only — does NOT update the bandit posterior. Pure preview
    of what the bandit would pull right now.
    """
    return next_bandit_topic(player)


class BanditOutcomePayload(BaseModel):
    player: str = Field(..., min_length=1)
    topic: str = Field(..., min_length=1)
    correct: bool


@router.post("/training/progression/bandit-result")
def training_progression_bandit_result(payload: BanditOutcomePayload) -> dict:
    """Record a topic outcome and return the updated bandit snapshot."""
    return record_bandit_outcome(
        player_name=payload.player,
        topic=payload.topic,
        correct=payload.correct,
    )


class SrsReviewPayload(BaseModel):
    player: str = Field(..., min_length=1)
    card_id: str = Field(..., min_length=1)
    quality: int = Field(..., ge=0, le=5)


@router.post("/training/progression/srs-review")
def training_progression_srs_review(payload: SrsReviewPayload) -> dict:
    """SM-2 review for a memorized card. Quality is 0-5."""
    return review_srs_card(
        player_name=payload.player,
        card_id=payload.card_id,
        quality=payload.quality,
    )


class ScenarioOutcomePayload(BaseModel):
    player: str = Field(..., min_length=1)
    scenario_id: str = Field(..., min_length=1)
    player_won: bool


@router.post("/training/progression/scenario-result")
def training_progression_scenario_result(payload: ScenarioOutcomePayload) -> dict:
    """Update the Elo rating between player and a named scenario."""
    return record_scenario_elo(
        player_name=payload.player,
        scenario_id=payload.scenario_id,
        player_won=payload.player_won,
    )
