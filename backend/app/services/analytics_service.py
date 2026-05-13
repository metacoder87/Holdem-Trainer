from typing import Any, Dict, List, Optional

from app.core.paths import ensure_src_path, get_data_file

ensure_src_path()

from data.manager import DataManager
from training.analyzer import SessionReviewer
from training.career_tracker import CareerTracker
from training.progression_analyzer import ProgressionAnalyzer, WeaknessType


WEAKNESS_DESCRIPTIONS = {
    WeaknessType.TOO_LOOSE: {
        "title": "VPIP too high",
        "fix": "Tighten opening ranges, especially out of position.",
    },
    WeaknessType.TOO_TIGHT: {
        "title": "VPIP too low",
        "fix": "Open wider on the button and cutoff against tight blinds.",
    },
    WeaknessType.TOO_PASSIVE: {
        "title": "Aggression too low",
        "fix": "Raise more for value and add light 3-bets in late position.",
    },
    WeaknessType.TOO_AGGRESSIVE: {
        "title": "Aggression too high",
        "fix": "Trim bluff frequency and pick better spots for thin value.",
    },
    WeaknessType.POOR_POT_ODDS: {
        "title": "Pot odds calculation",
        "fix": "Drill required-equity quizzes; revisit chasing-draws math.",
    },
    WeaknessType.POOR_POSITION_PLAY: {
        "title": "Position play",
        "fix": "Review button vs blinds and SB vs BB heads-up nodes.",
    },
    WeaknessType.WEAK_3BET_DEFENSE: {
        "title": "3-bet defense",
        "fix": "Build a defensive 4-bet and call range for early-position 3-bets.",
    },
    WeaknessType.POOR_BET_SIZING: {
        "title": "Bet sizing",
        "fix": "Calibrate sizes by board texture and SPR.",
    },
    WeaknessType.TILT_PRONE: {
        "title": "Mental game",
        "fix": "Add a session reset routine after consecutive losing pots.",
    },
}

SEVERITY_RANK = ["low", "medium", "high"]


def _manager() -> DataManager:
    return DataManager(data_file=str(get_data_file()))


def _resolve_player(player_name: Optional[str]) -> Optional[Dict[str, Any]]:
    manager = _manager()
    if player_name:
        record = manager.get_player(player_name)
        if record:
            return record
    players = manager.list_players(sort_by="last_played", reverse=True)
    return players[0] if players else None


def _aggregate_metrics(record: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate per-session metrics, weighted by hands played.

    `None`/missing values are excluded rather than coerced to 0.0 (which was
    flagging brand-new players as having near-zero pot-odds accuracy).
    """
    sessions = [s for s in (record.get("sessions") or []) if isinstance(s, dict)]
    last_session = record.get("last_session") or (sessions[-1] if sessions else {})

    def weighted_avg(metric: str) -> Optional[float]:
        weighted_sum = 0.0
        weight = 0.0
        for session in sessions:
            value = session.get(metric)
            if value is None:
                continue
            try:
                v = float(value)
            except (TypeError, ValueError):
                continue
            hands = int(session.get("hands_played") or 0) or 1
            weighted_sum += v * hands
            weight += hands
        if weight > 0:
            return weighted_sum / weight
        # Fall back to last_session if no session-level data
        value = last_session.get(metric)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def total(metric: str) -> int:
        return sum(int(s.get(metric) or 0) for s in sessions)

    total_hands = total("hands_played")
    pot_odds_samples = total("pot_odds_quizzes")
    decision_samples = total("decisions_total")

    return {
        "vpip": weighted_avg("vpip") or 0.0,
        "pfr": weighted_avg("pfr") or 0.0,
        "aggression_factor": weighted_avg("aggression_factor") or 0.0,
        "decision_accuracy": weighted_avg("decision_accuracy"),
        "quiz_accuracy": weighted_avg("quiz_accuracy"),
        "total_hands": float(total_hands),
        "pot_odds_accuracy": weighted_avg("pot_odds_accuracy"),
        # Sample counts let downstream code suppress severity flags below
        # statistical-meaningful thresholds.
        "_hands_sample": total_hands,
        "_pot_odds_samples": pot_odds_samples,
        "_decision_samples": decision_samples,
    }


def _trend(sessions: List[Dict[str, Any]], metric: str, window: int = 10) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    for session in sessions[-window:]:
        if not isinstance(session, dict):
            continue
        value = session.get(metric)
        if value is None:
            continue
        points.append(
            {
                "started_at": session.get("started_at"),
                "value": float(value),
            }
        )
    return points


MIN_HANDS_FOR_LEAK_DETECTION = 50


def _ev_summary_from_hand_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate EV stats across the player's recent hand records.

    Each `decision_point` may carry `ev_loss_chips` / `ev_loss_bb` written by
    the engine (item 2.4). Only postflop facing-bet spots are graded, so this
    is a subset of all decisions. We aggregate:
      - total chips bled
      - total BB bled
      - count of graded decisions
      - top-3 biggest individual mistakes (with street + line)
    """
    total_chips = 0.0
    total_bb = 0.0
    graded = 0
    samples: List[Dict[str, Any]] = []

    for record in records:
        if not isinstance(record, dict):
            continue
        for decision in record.get("decision_points") or []:
            if not isinstance(decision, dict):
                continue
            if "ev_loss_chips" not in decision:
                continue
            loss_chips = float(decision.get("ev_loss_chips") or 0.0)
            loss_bb = float(decision.get("ev_loss_bb") or 0.0)
            total_chips += loss_chips
            total_bb += loss_bb
            graded += 1
            if loss_chips < 0:
                samples.append(
                    {
                        "hand_number": record.get("hand_number"),
                        "betting_round": decision.get("betting_round"),
                        "chosen_action": decision.get("chosen_action"),
                        "ev_loss_chips": round(loss_chips, 2),
                        "ev_loss_bb": round(loss_bb, 3),
                        "equity": decision.get("equity"),
                        "required_equity": decision.get("required_equity"),
                    }
                )

    samples.sort(key=lambda s: s["ev_loss_chips"])  # most negative first
    avg_loss_bb_per_decision = total_bb / graded if graded > 0 else 0.0

    return {
        "total_chips": round(total_chips, 2),
        "total_bb": round(total_bb, 3),
        "graded_decisions": graded,
        "avg_loss_bb_per_decision": round(avg_loss_bb_per_decision, 4),
        "top_leaks": samples[:5],
    }


def get_ev_summary(player_name: Optional[str]) -> Dict[str, Any]:
    """Build EV summary from the last 200 hands of the player's history.

    Reads the JSONL hand store directly so we don't have to keep `decisions`
    in the player record's rolling `recent_hands` cache forever.
    """
    record = _resolve_player(player_name)
    if not record:
        return {"player": None, "ev": _ev_summary_from_hand_records([])}
    name = record.get("name")
    manager = _manager()
    hands: List[Dict[str, Any]] = []
    try:
        hands = manager.load_hand_history(name, limit=200, reverse=False) or []
    except Exception:
        # Fall back to recent_hands cache if JSONL read fails.
        cached = record.get("recent_hands") or []
        if isinstance(cached, list):
            hands = [h for h in cached if isinstance(h, dict)]
    return {
        "player": {"name": name, "skill_level": record.get("skill_level")},
        "ev": _ev_summary_from_hand_records(hands),
    }


def _public_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Strip private (`_`-prefixed) keys before exposing metrics on the wire."""
    return {key: value for key, value in metrics.items() if not key.startswith("_")}


def get_analytics_summary(player_name: Optional[str]) -> Dict[str, Any]:
    record = _resolve_player(player_name)
    if not record:
        return {
            "player": None,
            "metrics": {},
            "trends": {},
            "session_count": 0,
        }

    metrics = _aggregate_metrics(record)
    sessions = [s for s in (record.get("sessions") or []) if isinstance(s, dict)]

    return {
        "player": {
            "name": record.get("name"),
            "skill_level": record.get("skill_level"),
        },
        "metrics": _public_metrics(metrics),
        "session_count": len(sessions),
        "samples": {
            "hands": int(metrics.get("_hands_sample", 0)),
            "decisions": int(metrics.get("_decision_samples", 0)),
            "pot_odds_quizzes": int(metrics.get("_pot_odds_samples", 0)),
        },
        "trends": {
            "vpip": _trend(sessions, "vpip"),
            "pfr": _trend(sessions, "pfr"),
            "aggression_factor": _trend(sessions, "aggression_factor"),
            "decision_accuracy": _trend(sessions, "decision_accuracy"),
            "profit": _trend(sessions, "profit"),
        },
    }


def _classify_severity(weakness: WeaknessType, metrics: Dict[str, Any]) -> str:
    vpip = metrics.get("vpip") or 0.0
    pfr = metrics.get("pfr") or 0.0
    af = metrics.get("aggression_factor") or 0.0
    pot_odds_accuracy = metrics.get("pot_odds_accuracy")
    pot_odds_samples = int(metrics.get("_pot_odds_samples", 0) or 0)

    if weakness == WeaknessType.TOO_LOOSE and vpip > 0.45:
        return "high"
    if weakness == WeaknessType.TOO_TIGHT and vpip < 0.10:
        return "high"
    if weakness == WeaknessType.TOO_PASSIVE and (pfr < 0.05 or af < 0.8):
        return "high"
    if weakness == WeaknessType.TOO_AGGRESSIVE and af > 5.0:
        return "high"
    if (
        weakness == WeaknessType.POOR_POT_ODDS
        and pot_odds_accuracy is not None
        and pot_odds_samples >= 10
        and pot_odds_accuracy < 0.3
    ):
        return "high"
    return "medium"


def get_leaks(player_name: Optional[str]) -> Dict[str, Any]:
    record = _resolve_player(player_name)
    if not record:
        return {"player": None, "leaks": []}

    metrics = _aggregate_metrics(record)

    # Don't flag leaks on tiny samples; brand-new players otherwise show up as
    # having multiple "high severity" weaknesses on default zero metrics.
    if int(metrics.get("_hands_sample", 0)) < MIN_HANDS_FOR_LEAK_DETECTION:
        return {
            "player": {
                "name": record.get("name"),
                "skill_level": record.get("skill_level"),
            },
            "leaks": [],
            "recommended_topics": [],
            "note": (
                f"Play at least {MIN_HANDS_FOR_LEAK_DETECTION} hands for leak "
                "analysis. Sample is too small to draw conclusions yet."
            ),
        }

    # Pass sample counts into the analyzer too so its own thresholds gate on
    # them. identify_weaknesses keys on `pot_odds_samples` (see progression
    # analyzer); set it explicitly here.
    analyzer_metrics = dict(metrics)
    analyzer_metrics["pot_odds_samples"] = metrics.get("_pot_odds_samples", 0)
    analyzer = ProgressionAnalyzer()
    weaknesses = analyzer.identify_weaknesses(analyzer_metrics)
    topics = analyzer.suggest_study_topics(weaknesses)

    seen: List[WeaknessType] = []
    leaks: List[Dict[str, Any]] = []
    for weakness in weaknesses:
        if weakness in seen:
            continue
        seen.append(weakness)
        info = WEAKNESS_DESCRIPTIONS.get(weakness, {})
        severity = _classify_severity(weakness, metrics)
        leaks.append(
            {
                "id": weakness.value,
                "title": info.get("title", weakness.value.replace("_", " ").title()),
                "severity": severity,
                "fix": info.get("fix", ""),
            }
        )

    leaks.sort(key=lambda leak: SEVERITY_RANK.index(leak["severity"]) if leak["severity"] in SEVERITY_RANK else 1, reverse=True)

    return {
        "player": {
            "name": record.get("name"),
            "skill_level": record.get("skill_level"),
        },
        "leaks": leaks,
        "recommended_topics": topics,
    }


def get_career(player_name: Optional[str]) -> Dict[str, Any]:
    """Build a career report from the player's session log.

    Wraps `CareerTracker.generate_career_report` so the API can expose
    long-term aggregates + milestones the CLI's "Career Report" branch has
    been using for a while.
    """
    record = _resolve_player(player_name)
    if not record:
        return {"player": None, "career_metrics": None, "session_count": 0, "milestones": []}

    sessions = [s for s in (record.get("sessions") or []) if isinstance(s, dict)]
    tracker = CareerTracker(player_name=record.get("name", "Player"))

    for session in sessions:
        session_copy = dict(session)
        # CareerTracker expects `profit` (not `net_result`); both can appear
        # depending on the path that wrote them.
        session_copy.setdefault("profit", session_copy.get("net_result", 0))
        try:
            tracker.record_session(session_copy)
        except Exception:
            continue

    report = tracker.generate_career_report()
    return {
        "player": {
            "name": record.get("name"),
            "skill_level": record.get("skill_level"),
        },
        "career_metrics": report.get("career_metrics"),
        "session_count": len(sessions),
        "trends": report.get("trends"),
        "milestones": report.get("milestones") or [],
        "skill_progression": report.get("skill_progression"),
    }


def get_session_report(
    player_name: Optional[str], session_index: Optional[int] = None
) -> Dict[str, Any]:
    """Build a SessionReviewer report for a specific session.

    Args:
        player_name: Player whose history to inspect. None = first profile
            found, mirroring the rest of analytics.
        session_index: 0-based index into the player's `sessions` list. None
            picks the most recent (`last_session`).

    Returns 404-shaped payload `{ "session": None, ... }` when the session
    can't be resolved; the route turns that into a 404.
    """
    record = _resolve_player(player_name)
    if not record:
        return {"session": None, "report": None}

    sessions = [s for s in (record.get("sessions") or []) if isinstance(s, dict)]
    if session_index is None:
        target = record.get("last_session") or (sessions[-1] if sessions else None)
        resolved_index = len(sessions) - 1 if sessions else None
    else:
        if session_index < 0 or session_index >= len(sessions):
            return {"session": None, "report": None}
        target = sessions[session_index]
        resolved_index = session_index

    if not isinstance(target, dict):
        return {"session": None, "report": None}

    # SessionReviewer expects `net_result` (not the persisted `profit`).
    session_for_review = dict(target)
    session_for_review["net_result"] = int(
        session_for_review.get("net_result") or session_for_review.get("profit", 0) or 0
    )

    reviewer = SessionReviewer()
    try:
        report = reviewer.generate_session_report(session_for_review)
    except Exception as exc:  # noqa: BLE001
        return {"session": target, "report": None, "error": str(exc)}

    return {
        "player": {
            "name": record.get("name"),
            "skill_level": record.get("skill_level"),
        },
        "session_index": resolved_index,
        "session": target,
        "report": report,
    }
