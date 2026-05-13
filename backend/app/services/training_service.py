from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.paths import ensure_src_path, get_data_file

ensure_src_path()

from data.manager import DataManager
from training.adaptive_trainer import AdaptiveTrainer
from training.content_loader import ContentLoader
from training.progression_analyzer import WeaknessType
from training.trainer import PokerTrainer, QuizType


MAX_ATTEMPTS = 200
MAX_PENDING = 50


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _manager() -> DataManager:
    return DataManager(data_file=str(get_data_file()))


def _player_name(value: Optional[str]) -> str:
    normalized = str(value or "Guest").strip()
    return normalized or "Guest"


def _ensure_player(manager: DataManager, player_name: Optional[str]) -> Dict[str, Any]:
    player = _player_name(player_name)
    record = manager.get_player(player)
    if record:
        return record

    try:
        record = manager.create_player(player, 10000)
        manager.save_players()
        return record
    except ValueError:
        return manager.get_player(player) or {"name": player}


def _default_progress() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "quiz_attempts": [],
        "drill_attempts": [],
        "pending_quizzes": {},
        "pending_drills": {},
        "weakness_history": {},
        "mastery_progress": {},
        "study_recommendations": [],
    }


def _coerce_progress(record: Dict[str, Any]) -> Dict[str, Any]:
    raw = record.get("training_progress")
    progress = _default_progress()
    if isinstance(raw, dict):
        progress.update(raw)

    for key in ("quiz_attempts", "drill_attempts", "study_recommendations"):
        if not isinstance(progress.get(key), list):
            progress[key] = []
    for key in ("pending_quizzes", "pending_drills", "weakness_history", "mastery_progress"):
        if not isinstance(progress.get(key), dict):
            progress[key] = {}
    return progress


def _save_progress(manager: DataManager, player_name: str, progress: Dict[str, Any]) -> None:
    manager.update_player_stats(player_name, {"training_progress": progress})
    manager.save_players()


def _attempt_stats(attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(attempts)
    correct = sum(1 for attempt in attempts if bool(attempt.get("correct")))
    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else None,
    }


def _public_progress(progress: Dict[str, Any]) -> Dict[str, Any]:
    quiz_attempts = list(progress.get("quiz_attempts") or [])[-MAX_ATTEMPTS:]
    drill_attempts = list(progress.get("drill_attempts") or [])[-MAX_ATTEMPTS:]
    return {
        "schema_version": progress.get("schema_version", 1),
        "quiz_attempts": quiz_attempts,
        "drill_attempts": drill_attempts,
        "weakness_history": dict(progress.get("weakness_history") or {}),
        "mastery_progress": dict(progress.get("mastery_progress") or {}),
        "study_recommendations": list(progress.get("study_recommendations") or []),
        "quiz_stats": _attempt_stats(quiz_attempts),
        "drill_stats": _attempt_stats(drill_attempts),
    }


def _trim_mapping(mapping: Dict[str, Any], limit: int = MAX_PENDING) -> Dict[str, Any]:
    if len(mapping) <= limit:
        return mapping
    items = sorted(
        mapping.items(),
        key=lambda item: str((item[1] or {}).get("generated_at", "")) if isinstance(item[1], dict) else "",
    )
    return dict(items[-limit:])


def _sanitize_quiz(quiz: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in quiz.items()
        if key not in {"correct_answer", "correct_percentage", "acceptable_range", "explanation"}
    }


def _sanitize_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in scenario.items()
        if key not in {"recommended_actions", "learning_point", "correct_answer"}
    }


def _public_drill(payload: Dict[str, Any]) -> Dict[str, Any]:
    public = dict(payload)
    public["scenario"] = _sanitize_scenario(payload.get("scenario") or {})
    public["quiz"] = _sanitize_quiz(payload.get("quiz") or {})
    return public


def _append_attempt(progress: Dict[str, Any], key: str, attempt: Dict[str, Any]) -> None:
    attempts = progress.setdefault(key, [])
    if not isinstance(attempts, list):
        attempts = []
        progress[key] = attempts
    attempts.append(attempt)
    if len(attempts) > MAX_ATTEMPTS:
        del attempts[:-MAX_ATTEMPTS]


def _update_weakness_progress(
    progress: Dict[str, Any],
    focus_area: str,
    *,
    correct: bool,
    recommendations: Optional[List[str]] = None,
) -> None:
    weakness_history = progress.setdefault("weakness_history", {})
    if not isinstance(weakness_history, dict):
        weakness_history = {}
        progress["weakness_history"] = weakness_history

    entry = weakness_history.setdefault(
        focus_area,
        {"attempts": 0, "correct": 0, "accuracy": None, "last_practiced": None},
    )
    entry["attempts"] = int(entry.get("attempts", 0) or 0) + 1
    entry["correct"] = int(entry.get("correct", 0) or 0) + (1 if correct else 0)
    entry["accuracy"] = entry["correct"] / entry["attempts"] if entry["attempts"] else None
    entry["last_practiced"] = _now()

    mastery = progress.setdefault("mastery_progress", {})
    if not isinstance(mastery, dict):
        mastery = {}
        progress["mastery_progress"] = mastery
    mastery[focus_area] = int(round((entry["accuracy"] or 0) * 100))

    if recommendations:
        existing = list(progress.get("study_recommendations") or [])
        for item in recommendations:
            if item not in existing:
                existing.append(item)
        progress["study_recommendations"] = existing[-20:]


def _normalize_answer(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _evaluate_text_answer(expected: Any, user_answer: Any) -> bool:
    expected_text = _normalize_answer(expected)
    answer_text = _normalize_answer(user_answer)
    if not expected_text or not answer_text:
        return False
    if expected_text == answer_text:
        return True
    expected_words = {part for part in expected_text.replace("_", " ").split() if len(part) > 2}
    return any(word in answer_text for word in expected_words)


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
    player_name: Optional[str] = None,
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

    private_quiz = trainer.generate_quiz(quiz_kind, **kwargs)
    quiz_id = uuid4().hex
    private_quiz.update(
        {
            "quiz_id": quiz_id,
            "player": _player_name(player_name),
            "generated_at": _now(),
        }
    )

    manager = _manager()
    record = _ensure_player(manager, player_name)
    player = _player_name(record.get("name") or player_name)
    progress = _coerce_progress(record)
    pending = progress.setdefault("pending_quizzes", {})
    pending[quiz_id] = private_quiz
    progress["pending_quizzes"] = _trim_mapping(pending)
    _save_progress(manager, player, progress)

    return _sanitize_quiz(private_quiz)


def evaluate_quiz(
    quiz_id: str,
    user_answer: Any,
    *,
    player_name: Optional[str] = None,
    tolerance: float = 0.05,
) -> Dict[str, Any]:
    manager = _manager()
    record = _ensure_player(manager, player_name)
    player = _player_name(record.get("name") or player_name)
    progress = _coerce_progress(record)
    pending = progress.setdefault("pending_quizzes", {})
    quiz = pending.pop(str(quiz_id), None)
    if not isinstance(quiz, dict):
        raise ValueError("Quiz not found or already evaluated.")

    trainer = PokerTrainer()
    result = trainer.evaluate_answer(
        float(quiz.get("correct_answer", 0)),
        user_answer,
        tolerance=float(tolerance),
    )
    correct = bool(result.get("correct"))
    attempt = {
        "quiz_id": quiz_id,
        "quiz_type": quiz.get("type"),
        "question": quiz.get("question"),
        "user_answer": result.get("user_answer", user_answer),
        "correct_answer": result.get("correct_answer", quiz.get("correct_answer")),
        "correct": correct,
        "created_at": _now(),
    }
    _append_attempt(progress, "quiz_attempts", attempt)
    progress["pending_quizzes"] = pending
    _save_progress(manager, player, progress)

    stats = _attempt_stats(progress.get("quiz_attempts") or [])
    result.update(
        {
            "quiz_id": quiz_id,
            "quiz_type": quiz.get("type"),
            "explanation": quiz.get("explanation", ""),
            "performance_stats": {
                "total_quizzes": stats["total"],
                "correct_answers": stats["correct"],
                "accuracy": stats["accuracy"],
            },
        }
    )
    return result


def _weakness_from_value(value: str) -> Optional[WeaknessType]:
    normalized = (value or "").strip().lower()
    for weakness in WeaknessType:
        if weakness.value == normalized:
            return weakness
    return None


def generate_drill(player_name: Optional[str] = None, focus: Optional[str] = None) -> Dict[str, Any]:
    manager = _manager()
    record = _ensure_player(manager, player_name)

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

    player = _player_name(player_name or (record.get("name") if isinstance(record, dict) else None))
    trainer = AdaptiveTrainer(player)
    configuration = trainer.configure_from_weaknesses(weaknesses)
    focus_weakness = weaknesses[0]

    payload = {
        "drill_id": uuid4().hex,
        "player": player,
        "focus_area": focus_weakness.value,
        "generated_at": _now(),
        "configuration": configuration,
        "scenario": trainer.create_practice_scenario(focus_weakness),
        "quiz": trainer.generate_targeted_quiz(focus_weakness),
        "curriculum": trainer.generate_personalized_curriculum(weaknesses),
    }

    progress = _coerce_progress(record)
    pending = progress.setdefault("pending_drills", {})
    pending[payload["drill_id"]] = payload
    progress["pending_drills"] = _trim_mapping(pending)
    _save_progress(manager, player, progress)
    return _public_drill(payload)


def evaluate_drill(drill_id: str, user_answer: Any, *, player_name: Optional[str] = None) -> Dict[str, Any]:
    manager = _manager()
    record = _ensure_player(manager, player_name)
    player = _player_name(record.get("name") or player_name)
    progress = _coerce_progress(record)
    pending = progress.setdefault("pending_drills", {})
    drill = pending.pop(str(drill_id), None)
    if not isinstance(drill, dict):
        raise ValueError("Drill not found or already evaluated.")

    quiz = drill.get("quiz") if isinstance(drill.get("quiz"), dict) else {}
    scenario = drill.get("scenario") if isinstance(drill.get("scenario"), dict) else {}
    expected = quiz.get("correct_answer")
    if expected is None:
        expected_actions = scenario.get("recommended_actions")
        expected = expected_actions[0] if isinstance(expected_actions, list) and expected_actions else ""

    if isinstance(expected, (int, float)):
        try:
            user_value = float(user_answer)
            correct = abs(float(expected) - user_value) <= max(abs(float(expected)) * 0.2, 1.0)
        except (TypeError, ValueError):
            correct = False
    else:
        correct = _evaluate_text_answer(expected, user_answer)

    focus_area = str(drill.get("focus_area") or "general")
    curriculum = drill.get("curriculum") if isinstance(drill.get("curriculum"), dict) else {}
    recommendations: List[str] = []
    modules = curriculum.get("modules", []) if isinstance(curriculum.get("modules"), list) else []
    for module in modules:
        if isinstance(module, dict):
            recommendations.extend(str(topic) for topic in module.get("topics", []) if topic)

    attempt = {
        "drill_id": drill_id,
        "focus_area": focus_area,
        "question": quiz.get("question") or scenario.get("situation"),
        "user_answer": user_answer,
        "correct_answer": expected,
        "correct": correct,
        "created_at": _now(),
    }
    _append_attempt(progress, "drill_attempts", attempt)
    _update_weakness_progress(progress, focus_area, correct=correct, recommendations=recommendations)
    progress["pending_drills"] = pending
    _save_progress(manager, player, progress)

    feedback = "Correct. Keep reinforcing this spot." if correct else "Not quite. Review the recommended line and run another rep."
    return {
        "drill_id": drill_id,
        "focus_area": focus_area,
        "correct": correct,
        "feedback": feedback,
        "user_answer": user_answer,
        "correct_answer": expected,
        "explanation": quiz.get("explanation") or scenario.get("learning_point", ""),
        "recommended_actions": scenario.get("recommended_actions", []),
        "progress": _public_progress(progress),
    }


def get_training_progress(player_name: Optional[str] = None) -> Dict[str, Any]:
    manager = _manager()
    record = _ensure_player(manager, player_name)
    progress = _coerce_progress(record)
    return {
        "player": _player_name(record.get("name") or player_name),
        **_public_progress(progress),
    }
