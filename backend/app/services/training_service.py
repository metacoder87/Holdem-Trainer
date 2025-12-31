from typing import Any, Dict, Optional

from app.core.paths import ensure_src_path

ensure_src_path()

from training.content_loader import ContentLoader
from training.trainer import PokerTrainer, QuizType


def load_training_content() -> Dict[str, Any]:
    loader = ContentLoader()
    return {
        "tips": loader.load_tips(),
        "vocabulary": loader.load_vocabulary(),
        "strategy_guides": loader.load_strategy_guides(),
        "cheat_sheets": loader.load_cheat_sheets(),
    }


def generate_quiz(
    quiz_type: str,
    *,
    pot_size: Optional[float] = None,
    bet_to_call: Optional[float] = None,
) -> Dict[str, Any]:
    trainer = PokerTrainer()
    trainer.enable_training()

    normalized = (quiz_type or "").lower().strip()
    mapping = {
        "pot_odds": QuizType.POT_ODDS,
        "required_equity": QuizType.REQUIRED_EQUITY,
        "implied_odds": QuizType.IMPLIED_ODDS,
        "bet_sizing": QuizType.BET_SIZING,
    }
    quiz_kind = mapping.get(normalized, QuizType.POT_ODDS)

    kwargs: Dict[str, Any] = {}
    if pot_size is not None:
        kwargs["pot_size"] = float(pot_size)
    if bet_to_call is not None:
        kwargs["bet_to_call"] = float(bet_to_call)

    if quiz_kind in {QuizType.POT_ODDS, QuizType.REQUIRED_EQUITY}:
        kwargs.setdefault("pot_size", 150)
        kwargs.setdefault("bet_to_call", 35)
    elif quiz_kind == QuizType.IMPLIED_ODDS:
        kwargs.setdefault("pot_size", 120)
        kwargs.setdefault("bet_to_call", 40)
    elif quiz_kind == QuizType.BET_SIZING:
        kwargs.setdefault("pot_size", 180)

    return trainer.generate_quiz(quiz_kind, **kwargs)


def evaluate_quiz(correct_answer: float, user_answer: float, *, tolerance: float = 0.05) -> Dict[str, Any]:
    trainer = PokerTrainer()
    return trainer.evaluate_answer(float(correct_answer), float(user_answer), tolerance=float(tolerance))
