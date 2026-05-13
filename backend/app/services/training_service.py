from datetime import datetime
from typing import Any, Dict, Optional

from app.core.paths import ensure_src_path, get_data_file

ensure_src_path()

from data.manager import DataManager
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
    fold_equity: Optional[float] = None,
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

    if quiz_kind == QuizType.REQUIRED_EQUITY and fold_equity is not None:
        kwargs["fold_equity"] = float(fold_equity)

    return trainer.generate_quiz(quiz_kind, **kwargs)


def evaluate_quiz(
    correct_answer: float,
    user_answer: float,
    *,
    tolerance: float = 0.05,
    player_name: Optional[str] = None,
    quiz_type: Optional[str] = None,
) -> Dict[str, Any]:
    trainer = PokerTrainer()
    result = trainer.evaluate_answer(
        float(correct_answer), float(user_answer), tolerance=float(tolerance)
    )

    if player_name:
        try:
            _record_quiz_result(
                player_name=player_name,
                quiz_type=quiz_type or "unknown",
                correct=bool(result.get("correct")),
                correct_answer=float(correct_answer),
                user_answer=float(user_answer),
            )
            result["persisted"] = True
        except Exception as exc:  # noqa: BLE001
            result["persisted"] = False
            result["persist_error"] = str(exc)
    else:
        result["persisted"] = False

    return result


def _record_quiz_result(
    *,
    player_name: str,
    quiz_type: str,
    correct: bool,
    correct_answer: float,
    user_answer: float,
) -> None:
    """Append a quiz attempt to the player's quiz_history + update stats.

    History is capped at 500 most recent attempts. `quiz_stats` is an aggregate
    that downstream analytics (per-topic mastery) can read without scanning the
    whole list.
    """
    manager = DataManager(data_file=str(get_data_file()))
    record = manager.get_player(player_name)
    if not record:
        return

    history = record.get("quiz_history") or []
    if not isinstance(history, list):
        history = []
    history = list(history)
    history.append(
        {
            "quiz_type": quiz_type,
            "correct": bool(correct),
            "correct_answer": float(correct_answer),
            "user_answer": float(user_answer),
            "recorded_at": datetime.now().isoformat(),
        }
    )
    if len(history) > 500:
        history = history[-500:]

    stats = record.get("quiz_stats") or {}
    if not isinstance(stats, dict):
        stats = {}
    stats = dict(stats)

    total = int(stats.get("total", 0)) + 1
    correct_total = int(stats.get("correct", 0)) + (1 if correct else 0)
    stats["total"] = total
    stats["correct"] = correct_total
    stats["accuracy"] = correct_total / total if total else 0.0

    by_topic = stats.get("by_topic")
    if not isinstance(by_topic, dict):
        by_topic = {}
    by_topic = dict(by_topic)
    bucket = by_topic.get(quiz_type) or {"total": 0, "correct": 0}
    bucket = {
        "total": int(bucket.get("total", 0)) + 1,
        "correct": int(bucket.get("correct", 0)) + (1 if correct else 0),
    }
    bucket["accuracy"] = bucket["correct"] / bucket["total"] if bucket["total"] else 0.0
    by_topic[quiz_type] = bucket
    stats["by_topic"] = by_topic

    manager.update_player_stats(
        player_name,
        {"quiz_history": history, "quiz_stats": stats},
    )
    manager.save_players()
