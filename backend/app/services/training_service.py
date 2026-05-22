from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
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


def _update_progress(
    manager: DataManager,
    player_name: str,
    mutator: Callable[[Dict[str, Any], Dict[str, Any]], Any],
) -> Any:
    def update_record(record: Dict[str, Any]) -> Any:
        progress = _coerce_progress(record)
        result = mutator(progress, record)
        record["training_progress"] = progress
        return result

    return manager.update_player_record(player_name, update_record)


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
        if key
        not in {
            "correct_answer",
            "correct_percentage",
            "acceptable_range",
            "explanation",
            "pot",
            "bet",
        }
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

    manager = _manager()
    record = _ensure_player(manager, player_name)
    player = _player_name(record.get("name") or player_name)

    private_quiz = trainer.generate_quiz(quiz_kind, **kwargs)
    quiz_id = uuid4().hex
    private_quiz.update(
        {
            "quiz_id": quiz_id,
            "player": player,
            "generated_at": _now(),
        }
    )

    def store_quiz(progress: Dict[str, Any], _record: Dict[str, Any]) -> None:
        pending = progress.setdefault("pending_quizzes", {})
        pending[quiz_id] = private_quiz
        progress["pending_quizzes"] = _trim_mapping(pending)

    _update_progress(manager, player, store_quiz)

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
    quiz_id_text = str(quiz_id)

    def evaluate(progress: Dict[str, Any], _record: Dict[str, Any]) -> Dict[str, Any]:
        pending = progress.setdefault("pending_quizzes", {})
        quiz = pending.pop(quiz_id_text, None)
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
            "quiz_id": quiz_id_text,
            "quiz_type": quiz.get("type"),
            "question": quiz.get("question"),
            "user_answer": result.get("user_answer", user_answer),
            "correct_answer": result.get("correct_answer", quiz.get("correct_answer")),
            "correct": correct,
            "created_at": _now(),
        }
        _append_attempt(progress, "quiz_attempts", attempt)
        progress["pending_quizzes"] = pending

        stats = _attempt_stats(progress.get("quiz_attempts") or [])
        result.update(
            {
                "quiz_id": quiz_id_text,
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

    return _update_progress(manager, player, evaluate)


def _weakness_from_value(value: str) -> Optional[WeaknessType]:
    normalized = (value or "").strip().lower()
    for weakness in WeaknessType:
        if weakness.value == normalized:
            return weakness
    return None


def _draw_hit_probability(outs: int, cards_to_come: int) -> float:
    outs = max(0, int(outs or 0))
    if outs <= 0:
        return 0.0
    if cards_to_come >= 2:
        first_deck = 47
        second_deck = 46
        return 1 - ((first_deck - outs) / first_deck) * ((second_deck - outs) / second_deck)
    return outs / 46


def _coherent_drill_quiz(
    weakness: WeaknessType,
    scenario: Dict[str, Any],
    fallback_quiz: Dict[str, Any],
) -> Dict[str, Any]:
    situation = str(scenario.get("situation") or "Review the current poker spot")
    pot_size = float(scenario.get("pot_size") or 0)
    quiz = {} if weakness == WeaknessType.POOR_POT_ODDS else dict(fallback_quiz or {})

    if weakness == WeaknessType.POOR_POT_ODDS:
        bet_to_call = float(scenario.get("bet_to_call") or 0)
        outs = int(scenario.get("outs") or 0)
        cards_to_come = 1 if "turn" in situation.lower() else 2
        required_equity = bet_to_call / (pot_size + bet_to_call) if bet_to_call > 0 else 0.0
        draw_equity = _draw_hit_probability(outs, cards_to_come)
        answer = "call" if draw_equity >= required_equity else "fold"
        street = "turn" if cards_to_come == 1 else "flop"
        scenario["recommended_actions"] = [
            f"{answer} at this price",
            "calculate pot odds before continuing",
            "compare draw equity to required equity",
        ]
        scenario["learning_point"] = (
            f"Calling needs about {required_equity * 100:.0f}% equity; "
            f"{outs} outs on the {street} has about {draw_equity * 100:.0f}%."
        )
        quiz.update(
            {
                "question": (
                    f"{situation}. Pot is ${pot_size:.0f}, villain bets ${bet_to_call:.0f}, "
                    f"and you have {outs} outs. What is the best default line?"
                ),
                "type": "pot_odds",
                "correct_answer": answer,
                "explanation": scenario["learning_point"],
            }
        )
    else:
        expected_by_weakness = {
            WeaknessType.TOO_PASSIVE: ("bet", "value betting"),
            WeaknessType.TOO_LOOSE: ("fold", "early-position hand selection"),
            WeaknessType.TOO_TIGHT: ("raise", "late-position opening"),
            WeaknessType.TOO_AGGRESSIVE: ("check", "bluff selection"),
            WeaknessType.POOR_POSITION_PLAY: ("position", "equity realization"),
            WeaknessType.WEAK_3BET_DEFENSE: ("continue", "3-bet defense"),
            WeaknessType.POOR_BET_SIZING: ("large", "wet-board value sizing"),
            WeaknessType.TILT_PRONE: ("pause", "session reset"),
        }
        answer, concept = expected_by_weakness.get(weakness, ("review", "the current leak"))
        quiz.update(
            {
                "question": (
                    f"{situation}. Pot is ${pot_size:.0f}. Which default line or concept "
                    f"best addresses this spot?"
                ),
                "correct_answer": answer,
                "explanation": str(scenario.get("learning_point") or f"Focus on {concept}."),
            }
        )

    quiz.setdefault("type", weakness.value)
    quiz.setdefault("difficulty", 1)
    quiz["weakness_type"] = weakness.value
    quiz["scenario_key"] = weakness.value
    return quiz


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
    scenario = dict(trainer.create_practice_scenario(focus_weakness))
    quiz = _coherent_drill_quiz(
        focus_weakness,
        scenario,
        trainer.generate_targeted_quiz(focus_weakness),
    )

    payload = {
        "drill_id": uuid4().hex,
        "player": player,
        "focus_area": focus_weakness.value,
        "generated_at": _now(),
        "configuration": configuration,
        "scenario": scenario,
        "quiz": quiz,
        "curriculum": trainer.generate_personalized_curriculum(weaknesses),
    }

    def store_drill(progress: Dict[str, Any], _record: Dict[str, Any]) -> None:
        pending = progress.setdefault("pending_drills", {})
        pending[payload["drill_id"]] = payload
        progress["pending_drills"] = _trim_mapping(pending)

    _update_progress(manager, player, store_drill)
    return _public_drill(payload)


def generate_drill_from_decision(
    *,
    player_name: str,
    decision: Dict[str, Any],
    hand_meta: Optional[Dict[str, Any]] = None,
    hand_number: int,
    decision_index: int,
) -> Dict[str, Any]:
    """Build a drill seeded from one specific recorded decision.

    Unlike ``generate_drill`` which produces a generic scenario for
    a weakness type, this variant fills the scenario fields directly
    from the historical decision: same board, same hole cards, same
    pot, same position. The user can then re-play the exact spot.

    The drill is registered in the player's pending_drills so the
    existing ``evaluate_drill`` flow grades the answer the same way
    it grades a regular drill.

    Args:
        player_name: persisted player name (already resolved upstream).
        decision: the captured decision_point dict.
        hand_meta: optional ``hand["meta"]`` block for context.
        hand_number: the source hand's hand_number.
        decision_index: which decision in that hand.

    Returns:
        Public drill payload (same shape as ``generate_drill``).
    """
    manager = _manager()
    record = _ensure_player(manager, player_name)
    player = _player_name(player_name or (record.get("name") if isinstance(record, dict) else None))

    hand_meta = hand_meta or {}
    pot_total = int(decision.get("pot_total") or 0)
    call_amount = int(decision.get("to_call") or 0)
    hero_stack = int(decision.get("hero_stack") or 0)
    big_blind = int(hand_meta.get("big_blind") or 1)
    spr = float(decision.get("spr") or (hero_stack / pot_total if pot_total > 0 else 0.0))
    chosen = str(decision.get("chosen_action") or "").lower()
    recommended = str(decision.get("recommended_action") or "").lower() or chosen
    quality = str(decision.get("quality") or "ungraded")
    equity = decision.get("equity")
    required_equity = decision.get("required_equity")
    opponent = decision.get("opponent") if isinstance(decision.get("opponent"), dict) else {}

    # Choose a weakness focus that matches the leak type so any
    # ``evaluate_drill`` downstream still updates the mastery counter
    # for the right bucket.
    if quality in {"suboptimal", "mistake", "bad"}:
        if recommended in {"fold"}:
            focus_weakness = WeaknessType.TOO_LOOSE
        elif recommended in {"raise", "bet"}:
            focus_weakness = WeaknessType.TOO_PASSIVE
        elif recommended == "call":
            focus_weakness = WeaknessType.POOR_POT_ODDS
        else:
            focus_weakness = WeaknessType.POOR_POT_ODDS
    else:
        focus_weakness = WeaknessType.POOR_POT_ODDS

    trainer = AdaptiveTrainer(player)
    configuration = trainer.configure_from_weaknesses([focus_weakness])

    # Build scenario with REAL decision fields rather than synthetic
    # placeholders.
    scenario = {
        "scenario_id": uuid4().hex,
        "street": str(decision.get("betting_round") or "flop"),
        "position": int(decision.get("hero_position") or 0),
        "hole_cards": list(decision.get("hero_hole_cards") or []),
        "board": list(decision.get("board") or []),
        "pot_size": pot_total,
        "call_amount": call_amount,
        "hero_stack": hero_stack,
        "big_blind": big_blind,
        "spr": round(float(spr), 3),
        "opponent_type": str(opponent.get("type") or "unknown"),
        "opponent_name": str(opponent.get("name") or "Villain"),
        "equity_estimate": equity,
        "required_equity": required_equity,
        "recommended_actions": [recommended] if recommended else [],
        "previous_choice": chosen,
        "previous_quality": quality,
        "source": {
            "kind": "from_decision",
            "hand_number": int(hand_number),
            "decision_index": int(decision_index),
        },
    }

    # Generate a coherent quiz keyed off the spot type. For "call vs
    # fold" decisions we ask for the action; for "check vs raise" we
    # ask the same. Fallback to the trainer's targeted quiz so the
    # grading rubric stays identical.
    quiz = _coherent_drill_quiz(
        focus_weakness,
        scenario,
        trainer.generate_targeted_quiz(focus_weakness),
    )
    if recommended and quiz.get("correct_answer") is None:
        quiz["correct_answer"] = recommended

    payload = {
        "drill_id": uuid4().hex,
        "player": player,
        "focus_area": focus_weakness.value,
        "generated_at": _now(),
        "configuration": configuration,
        "scenario": scenario,
        "quiz": quiz,
        "curriculum": trainer.generate_personalized_curriculum([focus_weakness]),
        "from_decision": {
            "hand_number": int(hand_number),
            "decision_index": int(decision_index),
        },
    }

    def store_drill(progress: Dict[str, Any], _record: Dict[str, Any]) -> None:
        pending = progress.setdefault("pending_drills", {})
        pending[payload["drill_id"]] = payload
        progress["pending_drills"] = _trim_mapping(pending)

    _update_progress(manager, player, store_drill)
    return _public_drill(payload)


def evaluate_drill(drill_id: str, user_answer: Any, *, player_name: Optional[str] = None) -> Dict[str, Any]:
    manager = _manager()
    record = _ensure_player(manager, player_name)
    player = _player_name(record.get("name") or player_name)
    drill_id_text = str(drill_id)

    def evaluate(progress: Dict[str, Any], _record: Dict[str, Any]) -> Dict[str, Any]:
        pending = progress.setdefault("pending_drills", {})
        drill = pending.pop(drill_id_text, None)
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
            "drill_id": drill_id_text,
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

        # Track 4: also feed the adaptive engine. The drill outcome
        # updates (a) the bandit posterior for the focus topic and
        # (b) the Elo rating against the scenario id (if any).
        try:
            from app.services import adaptive_engine

            state = adaptive_engine.AdaptiveState.from_dict(
                progress.get(adaptive_engine._ADAPTIVE_KEY)
            )
            state.record_topic_result(focus_area, correct=bool(correct))
            scenario_id = (
                str(scenario.get("scenario_id") or scenario.get("source", {}).get("kind") or "")
                if isinstance(scenario, dict)
                else ""
            )
            if scenario_id:
                state.record_scenario_outcome(scenario_id, player_won=bool(correct))
            adaptive_engine.save_state(progress, state)
            adaptive_summary = adaptive_engine.progression_summary(state)
        except Exception:
            adaptive_summary = None

        feedback = (
            "Correct. Keep reinforcing this spot."
            if correct
            else "Not quite. Review the recommended line and run another rep."
        )
        return {
            "drill_id": drill_id_text,
            "focus_area": focus_area,
            "correct": correct,
            "feedback": feedback,
            "user_answer": user_answer,
            "correct_answer": expected,
            "explanation": quiz.get("explanation") or scenario.get("learning_point", ""),
            "recommended_actions": scenario.get("recommended_actions", []),
            "progress": _public_progress(progress),
            "adaptive": adaptive_summary,
        }

    return _update_progress(manager, player, evaluate)


def get_training_progress(player_name: Optional[str] = None) -> Dict[str, Any]:
    manager = _manager()
    record = _ensure_player(manager, player_name)
    progress = _coerce_progress(record)
    return {
        "player": _player_name(record.get("name") or player_name),
        **_public_progress(progress),
    }


# ---------- Track 4: adaptive engine integration ----------

from app.services import adaptive_engine  # noqa: E402  (deliberate late import)


def get_adaptive_progression(
    player_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Summary of bandit/SRS/Elo state for the progression dashboard."""
    manager = _manager()
    record = _ensure_player(manager, player_name)
    state = adaptive_engine.load_state(record)
    summary = adaptive_engine.progression_summary(state)
    summary["player"] = _player_name(record.get("name") or player_name)
    return summary


def next_bandit_topic(player_name: Optional[str] = None) -> Dict[str, Any]:
    """Pick the next drill topic via Thompson sampling.

    Returns the chosen topic plus the full bandit snapshot so the
    frontend can show why this topic was selected (CIs + pull
    counts).
    """
    manager = _manager()
    record = _ensure_player(manager, player_name)
    state = adaptive_engine.load_state(record)
    topic = state.pick_topic()
    return {
        "player": _player_name(record.get("name") or player_name),
        "topic": topic,
        "bandit": [a.to_dict() for a in state.bandit.values()],
    }


def record_bandit_outcome(
    *,
    player_name: str,
    topic: str,
    correct: bool,
) -> Dict[str, Any]:
    """Update the Beta posterior for a topic after one drill attempt."""
    manager = _manager()
    _ensure_player(manager, player_name)
    player = _player_name(player_name)

    def mutator(progress: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
        state = adaptive_engine.AdaptiveState.from_dict(progress.get(adaptive_engine._ADAPTIVE_KEY))
        state.record_topic_result(topic, correct=bool(correct))
        adaptive_engine.save_state(progress, state)
        return adaptive_engine.progression_summary(state)

    summary = _update_progress(manager, player, mutator)
    summary["player"] = player
    return summary


def review_srs_card(
    *,
    player_name: str,
    card_id: str,
    quality: int,
) -> Dict[str, Any]:
    """Run an SM-2 review for a memorized card."""
    manager = _manager()
    _ensure_player(manager, player_name)
    player = _player_name(player_name)

    def mutator(progress: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
        state = adaptive_engine.AdaptiveState.from_dict(progress.get(adaptive_engine._ADAPTIVE_KEY))
        state.review_card(card_id, quality=int(quality))
        adaptive_engine.save_state(progress, state)
        return adaptive_engine.progression_summary(state)

    summary = _update_progress(manager, player, mutator)
    summary["player"] = player
    return summary


def record_scenario_elo(
    *,
    player_name: str,
    scenario_id: str,
    player_won: bool,
) -> Dict[str, Any]:
    """Apply an Elo update after a scenario drill outcome."""
    manager = _manager()
    _ensure_player(manager, player_name)
    player = _player_name(player_name)

    def mutator(progress: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
        state = adaptive_engine.AdaptiveState.from_dict(progress.get(adaptive_engine._ADAPTIVE_KEY))
        state.record_scenario_outcome(scenario_id, player_won=bool(player_won))
        adaptive_engine.save_state(progress, state)
        return adaptive_engine.progression_summary(state)

    summary = _update_progress(manager, player, mutator)
    summary["player"] = player
    return summary
