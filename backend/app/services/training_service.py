from typing import Any, Dict, Optional

from app.core.paths import ensure_src_path, get_data_file

ensure_src_path()

from data.manager import DataManager
from training.adaptive_trainer import AdaptiveTrainer
from training.content_loader import ContentLoader
from training.progression_analyzer import WeaknessType
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


def _weakness_from_value(value: str) -> Optional[WeaknessType]:
    normalized = (value or "").strip().lower()
    for weakness in WeaknessType:
        if weakness.value == normalized:
            return weakness
    return None


def generate_drill(player_name: Optional[str] = None, focus: Optional[str] = None) -> Dict[str, Any]:
    manager = DataManager(data_file=str(get_data_file()))
    record = manager.get_player(player_name) if player_name else None

    weaknesses = []
    if focus:
        weakness = _weakness_from_value(focus)
        if weakness:
            weaknesses.append(weakness)

    if not weaknesses and isinstance(record, dict):
        for value in record.get("weaknesses") or []:
            weakness = _weakness_from_value(str(value))
            if weakness:
                weaknesses.append(weakness)

    if not weaknesses:
        weaknesses = [WeaknessType.POOR_POT_ODDS]

    player = player_name or (record.get("name") if isinstance(record, dict) else None) or "Guest"
    trainer = AdaptiveTrainer(player)
    configuration = trainer.configure_from_weaknesses(weaknesses)
    focus_weakness = weaknesses[0]

    return {
        "player": player,
        "focus_area": focus_weakness.value,
        "configuration": configuration,
        "scenario": trainer.create_practice_scenario(focus_weakness),
        "quiz": trainer.generate_targeted_quiz(focus_weakness),
        "curriculum": trainer.generate_personalized_curriculum(weaknesses),
    }
