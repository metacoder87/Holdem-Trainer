"""Stateless drill engine.

Generates a drill from a player's identified weakness (or a caller-supplied
focus area), then grades the answer. Grades are optionally persisted to the
player's `practice_history` so the adaptive trainer can use them across
sessions. This wraps `AdaptiveTrainer.create_practice_scenario` with the
extra structure (pot/bet/outs/options/correct_action) the UI needs to render
an answerable scenario.
"""
from __future__ import annotations

import hashlib
import random
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.paths import ensure_src_path, get_data_file

ensure_src_path()

from data.manager import DataManager
from training.progression_analyzer import ProgressionAnalyzer, WeaknessType


SUPPORTED_WEAKNESSES = [
    WeaknessType.POOR_POT_ODDS,
    WeaknessType.TOO_PASSIVE,
    WeaknessType.TOO_LOOSE,
    WeaknessType.POOR_BET_SIZING,
    WeaknessType.WEAK_3BET_DEFENSE,
]

DEFAULT_WEAKNESS = WeaknessType.POOR_POT_ODDS


def _score_focus_for_spaced_repetition(
    practice_stats: Dict[str, Any],
    candidates: List[WeaknessType],
) -> Optional[WeaknessType]:
    """Pick the focus area most in need of practice.

    Scoring (higher = needs practice more):
      - Lower accuracy -> higher score (cap 1.0 contribution)
      - Stale = haven't seen this focus area in many drills -> higher score
      - Never seen -> very high score (we should expose new material)

    Returns None if no candidate accumulates a positive score, which signals
    the caller to fall back to the analytics-based heuristic.
    """
    by_focus = practice_stats.get("by_focus") if isinstance(practice_stats, dict) else None
    if not isinstance(by_focus, dict):
        return None

    scores: Dict[WeaknessType, float] = {}
    for candidate in candidates:
        bucket = by_focus.get(candidate.value) or {}
        total = int(bucket.get("total", 0) or 0)
        if total == 0:
            # Surface unseen material aggressively.
            scores[candidate] = 1.5
            continue
        accuracy = float(bucket.get("accuracy", 0.0) or 0.0)
        # Lower accuracy = higher score, capped at 1.0
        accuracy_pressure = max(0.0, 1.0 - accuracy)
        # Staleness: pretend stalest of the candidates contributes +1.
        last_seen = bucket.get("last_seen")
        scores[candidate] = (last_seen, accuracy_pressure, total)  # type: ignore[assignment]

    # Build a comparable score: (1.0 - accuracy) + staleness_rank * 0.5.
    timestamps = [
        s[0] for s in scores.values()
        if isinstance(s, tuple) and s[0] is not None
    ]
    timestamps.sort()
    timestamp_rank = {ts: idx for idx, ts in enumerate(timestamps)}

    final: Dict[WeaknessType, float] = {}
    for candidate, raw in scores.items():
        if isinstance(raw, float):
            final[candidate] = raw
            continue
        last_seen, acc_pressure, _ = raw  # type: ignore[misc]
        stale_rank = 0
        if timestamps and last_seen in timestamp_rank and len(timestamps) > 1:
            # Oldest -> rank 0, normalize to [0, 1]
            stale_rank = 1.0 - (timestamp_rank[last_seen] / (len(timestamps) - 1))
        final[candidate] = acc_pressure + 0.5 * stale_rank

    if not final:
        return None
    best = max(final.items(), key=lambda kv: kv[1])
    return best[0] if best[1] > 0 else None


def _resolve_weakness(focus: Optional[str], player_name: Optional[str]) -> WeaknessType:
    if focus:
        try:
            weakness = WeaknessType(focus)
        except ValueError as exc:
            raise ValueError(f"Unknown focus area: {focus}") from exc
        if weakness in SUPPORTED_WEAKNESSES:
            return weakness
        raise ValueError(f"Drill engine does not support focus area: {focus}")

    if player_name:
        manager = DataManager(data_file=str(get_data_file()))
        record = manager.get_player(player_name) or {}

        # 1) Spaced-repetition: prefer the weakest/stalest focus area the
        #    player has actually practiced. Once a player has touched at
        #    least one drill, this takes over from the analytics heuristic
        #    so we keep them rotating through the material instead of
        #    grinding the same focus area on every visit.
        practice_stats = record.get("practice_stats") or {}
        sr_pick = _score_focus_for_spaced_repetition(practice_stats, SUPPORTED_WEAKNESSES)
        if sr_pick is not None:
            return sr_pick

        # 2) Fallback: identify the player's biggest weakness from
        #    in-session metrics.
        sessions = record.get("sessions") or []
        last_session = record.get("last_session") or (sessions[-1] if sessions else {})
        analyzer = ProgressionAnalyzer()
        metrics = {
            "vpip": float(last_session.get("vpip") or 0.0),
            "pfr": float(last_session.get("pfr") or 0.0),
            "aggression_factor": float(last_session.get("aggression_factor") or 0.0),
            "fold_to_3bet": float(last_session.get("fold_to_3bet") or 0.0),
            "pot_odds_accuracy": float(last_session.get("pot_odds_accuracy") or 0.0)
            if last_session.get("pot_odds_accuracy") is not None
            else 0.0,
        }
        weaknesses = [w for w in analyzer.identify_weaknesses(metrics) if w in SUPPORTED_WEAKNESSES]
        if weaknesses:
            return weaknesses[0]

    return DEFAULT_WEAKNESS


def _generate_pot_odds_drill(difficulty: int, rng: random.Random) -> Dict[str, Any]:
    pot = rng.randint(60, 240)
    bet = rng.randint(20, max(20, int(pot * 0.7)))
    required_equity = bet / (pot + bet)
    outs = rng.choice([4, 8, 9, 12, 15])
    cards_to_come = rng.choice([1, 2])
    estimated_equity = min(0.95, outs * (4 if cards_to_come == 2 else 2) / 100.0)
    correct_action = "call" if estimated_equity >= required_equity else "fold"

    return {
        "kind": "pot_odds",
        "scenario": (
            f"Turn decision. Pot is ${pot}; opponent bets ${bet}. "
            f"You have {outs} outs with {cards_to_come} card{'s' if cards_to_come == 2 else ''} to come."
        ),
        "options": ["call", "fold"],
        "correct_action": correct_action,
        "context": {
            "pot": pot,
            "bet_to_call": bet,
            "required_equity_pct": round(required_equity * 100, 1),
            "estimated_equity_pct": round(estimated_equity * 100, 1),
            "outs": outs,
            "cards_to_come": cards_to_come,
        },
        "difficulty": difficulty,
    }


def _generate_bet_sizing_drill(difficulty: int, rng: random.Random) -> Dict[str, Any]:
    pot = rng.choice([60, 100, 150, 220])
    target_pct = rng.choice([0.5, 0.66, 0.75])
    correct_amount = int(round(pot * target_pct / 5)) * 5

    return {
        "kind": "bet_sizing",
        "scenario": (
            f"You have top pair, good kicker on a dry flop. Pot is ${pot}. "
            "You're first to act against one opponent. What sizing do you use for value?"
        ),
        "options": [str(int(pot * x)) for x in (0.25, 0.5, 0.66, 1.0)],
        "correct_action": str(correct_amount),
        "context": {
            "pot": pot,
            "target_fraction": target_pct,
            "ideal_amount": correct_amount,
        },
        "difficulty": difficulty,
    }


def _generate_hand_selection_drill(difficulty: int, rng: random.Random) -> Dict[str, Any]:
    hands = [
        ("AKs", "raise"), ("QQ", "raise"), ("AJo", "raise"),
        ("JTs", "fold" if difficulty < 3 else "raise"),
        ("87s", "fold"), ("J9o", "fold"), ("K2o", "fold"),
        ("88", "raise"), ("65s", "fold"),
    ]
    hand, correct = rng.choice(hands)

    return {
        "kind": "hand_selection",
        "scenario": f"UTG opens to 3bb. You hold {hand} in middle position. Action is on you.",
        "options": ["raise", "call", "fold"],
        "correct_action": correct,
        "context": {"hand": hand, "position": "middle"},
        "difficulty": difficulty,
    }


def _generate_3bet_defense_drill(difficulty: int, rng: random.Random) -> Dict[str, Any]:
    spots = [
        ("AQo", "call"),
        ("KQs", "call"),
        ("99", "call"),
        ("AJo", "fold" if difficulty >= 3 else "call"),
        ("KJs", "fold"),
        ("T9s", "fold"),
        ("AA", "raise"),
        ("KK", "raise"),
    ]
    hand, correct = rng.choice(spots)

    return {
        "kind": "3bet_defense",
        "scenario": f"You opened from CO with {hand}. BTN 3-bets. Action is on you.",
        "options": ["raise", "call", "fold"],
        "correct_action": correct,
        "context": {"hand": hand, "position": "co"},
        "difficulty": difficulty,
    }


WEAKNESS_TO_GENERATOR = {
    WeaknessType.POOR_POT_ODDS: _generate_pot_odds_drill,
    WeaknessType.TOO_PASSIVE: _generate_bet_sizing_drill,
    WeaknessType.POOR_BET_SIZING: _generate_bet_sizing_drill,
    WeaknessType.TOO_LOOSE: _generate_hand_selection_drill,
    WeaknessType.WEAK_3BET_DEFENSE: _generate_3bet_defense_drill,
}


def _seed_from_drill_id(drill_id: str) -> int:
    """Deterministic 64-bit seed derived from a drill_id string."""
    digest = hashlib.sha256(drill_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def generate_drill(
    *,
    player_name: Optional[str] = None,
    focus_area: Optional[str] = None,
    difficulty: int = 2,
    drill_id: Optional[str] = None,
) -> Dict[str, Any]:
    weakness = _resolve_weakness(focus_area, player_name)
    generator = WEAKNESS_TO_GENERATOR[weakness]

    # If the caller provides a drill_id we replay the same scenario; otherwise
    # mint a fresh one and seed from it so the scenario is fully reproducible
    # given just the drill_id.
    resolved_id = drill_id or uuid.uuid4().hex
    rng = random.Random(_seed_from_drill_id(resolved_id))

    drill = generator(int(difficulty), rng)
    drill["drill_id"] = resolved_id
    drill["focus_area"] = weakness.value
    return drill


def grade_drill(
    *,
    drill_id: str,
    kind: str,
    correct_action: str,
    user_answer: str,
    player_name: Optional[str] = None,
    focus_area: Optional[str] = None,
) -> Dict[str, Any]:
    """Grade a drill answer and optionally persist it to practice_history.

    The frontend echoes back drill_id/kind/correct_action so we don't need to
    keep drill state on the server. When a player_name is supplied we append
    the result to that player's `practice_history` so the adaptive trainer
    can use it across sessions.
    """
    expected = str(correct_action).strip().lower()
    submitted = str(user_answer).strip().lower()
    correct = expected == submitted

    feedback = "Correct! Nice line." if correct else f"Suggested action: {expected}."
    response: Dict[str, Any] = {
        "drill_id": drill_id,
        "kind": kind,
        "correct": correct,
        "user_answer": submitted,
        "correct_action": expected,
        "feedback": feedback,
        "persisted": False,
    }

    if player_name:
        try:
            _record_practice_event(
                player_name=player_name,
                drill_id=drill_id,
                kind=kind,
                correct=correct,
                focus_area=focus_area,
            )
            response["persisted"] = True
        except Exception as exc:  # noqa: BLE001
            response["persist_error"] = str(exc)

    return response


def _record_practice_event(
    *,
    player_name: str,
    drill_id: str,
    kind: str,
    correct: bool,
    focus_area: Optional[str],
) -> None:
    """Append a drill result to the player's practice_history."""
    manager = DataManager(data_file=str(get_data_file()))
    record = manager.get_player(player_name)
    if not record:
        return

    history = record.get("practice_history") or []
    if not isinstance(history, list):
        history = []

    event = {
        "drill_id": drill_id,
        "kind": kind,
        "weakness_type": focus_area,
        "correct": bool(correct),
        "recorded_at": datetime.now().isoformat(),
    }
    history = list(history)
    history.append(event)
    if len(history) > 500:
        history = history[-500:]

    # Top-level totals + per-focus-area accuracy breakdown so the spaced
    # repetition scheduler in _resolve_weakness has cheap lookups.
    correct_count = 0
    by_focus: Dict[str, Dict[str, Any]] = {}
    for entry in history:
        if not isinstance(entry, dict):
            continue
        if entry.get("correct"):
            correct_count += 1
        focus = entry.get("weakness_type") or "unknown"
        bucket = by_focus.setdefault(focus, {"total": 0, "correct": 0, "last_seen": None})
        bucket["total"] = int(bucket.get("total", 0)) + 1
        if entry.get("correct"):
            bucket["correct"] = int(bucket.get("correct", 0)) + 1
        # Track the most recent attempt timestamp for staleness scoring.
        ts = entry.get("recorded_at")
        if ts and (bucket["last_seen"] is None or str(ts) > str(bucket["last_seen"])):
            bucket["last_seen"] = ts
    for bucket in by_focus.values():
        total = bucket["total"]
        bucket["accuracy"] = (bucket["correct"] / total) if total else 0.0

    total = len(history)
    practice_stats = {
        "total": total,
        "correct": correct_count,
        "accuracy": (correct_count / total) if total else 0.0,
        "by_focus": by_focus,
    }

    manager.update_player_stats(
        player_name,
        {
            "practice_history": history,
            "practice_stats": practice_stats,
        },
    )
    manager.save_players()


def list_focus_areas() -> List[Dict[str, str]]:
    return [
        {"id": w.value, "label": w.value.replace("_", " ").title()}
        for w in SUPPORTED_WEAKNESSES
    ]
