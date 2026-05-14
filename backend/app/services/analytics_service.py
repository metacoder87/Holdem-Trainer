from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.paths import get_data_file

from data.manager import DataManager
from stats.analyzer import PlayerAnalyzer
from training.progression_analyzer import ProgressionAnalyzer


PERCENT_METRICS = {"vpip", "pfr", "decision_accuracy", "quiz_accuracy", "pot_odds_accuracy", "winrate"}
SUPPORTED_METRICS = {
    "vpip": "VPIP",
    "pfr": "PFR",
    "aggression_factor": "Aggression Factor",
    "decision_accuracy": "Decision Accuracy",
    "quiz_accuracy": "Quiz Accuracy",
    "profit": "Profit",
    "hands_played": "Hands Played",
    "winrate": "Win Rate",
}


def _manager() -> DataManager:
    return DataManager(data_file=str(get_data_file()))


def load_player_record(player_name: Optional[str]) -> Optional[Dict[str, Any]]:
    manager = _manager()
    if player_name:
        record = manager.get_player(player_name)
        if record:
            return record
    players = manager.list_players(sort_by="last_played", reverse=True)
    return players[0] if players else None


def sessions_for_player(player_name: Optional[str], limit: int = 100) -> List[Dict[str, Any]]:
    record = load_player_record(player_name)
    if not record:
        return []

    sessions = record.get("sessions") or []
    if not isinstance(sessions, list):
        sessions = []

    if record.get("name"):
        try:
            persisted = _manager().get_sessions(str(record["name"]), limit=limit)
            if persisted:
                sessions = persisted
        except Exception:
            pass

    rows = [dict(session) for session in sessions if isinstance(session, dict)]
    rows.sort(key=lambda s: s.get("updated_at") or s.get("ended_at") or s.get("started_at") or s.get("created_at") or "")
    return rows[-limit:]


def _metric(session: Dict[str, Any], key: str, default: float = 0.0) -> float:
    value = session.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _display_value(metric: str, value: float) -> float:
    if metric in PERCENT_METRICS:
        return round(value * 100, 1)
    if metric == "aggression_factor":
        return round(value, 2)
    if metric in {"profit", "hands_played"}:
        return int(round(value))
    return round(value, 2)


def get_chart_data(player_name: Optional[str], metric: str = "vpip") -> List[Dict[str, Any]]:
    metric = (metric or "vpip").strip().lower()
    if metric not in SUPPORTED_METRICS:
        metric = "vpip"

    data = []
    for index, session in enumerate(sessions_for_player(player_name), start=1):
        data.append(
            {
                "label": f"Session {index}",
                "value": _display_value(metric, _metric(session, metric, 0.0)),
            }
        )
    return data


def _weighted_average(sessions: List[Dict[str, Any]], metric: str) -> float:
    total_hands = 0
    weighted = 0.0
    for session in sessions:
        hands = int(_metric(session, "hands_played", 0))
        if hands <= 0:
            continue
        total_hands += hands
        weighted += _metric(session, metric, 0.0) * hands
    return weighted / total_hands if total_hands else 0.0


def get_analytics_report(player_name: Optional[str]) -> Dict[str, Any]:
    record = load_player_record(player_name)
    if not record:
        return {
            "basic_stats": {},
            "playing_style": {"player_type": "Unknown", "vpip": 0, "pfr": 0, "aggression_factor": 0},
            "performance_metrics": {},
            "recommendations": ["Play tracked hands to generate analytics."],
            "strategy_score": 0,
            "metric_options": SUPPORTED_METRICS,
        }

    sessions = sessions_for_player(record.get("name"))
    total_hands = sum(int(_metric(session, "hands_played", 0)) for session in sessions)
    total_profit = sum(_metric(session, "profit", 0.0) for session in sessions)
    latest = sessions[-1] if sessions else {}

    agg_stats = {
        "games_played": len(sessions),
        "games_won": record.get("games_won", 0),
        "total_winnings": total_profit if sessions else record.get("total_winnings", 0),
        "vpip": _weighted_average(sessions, "vpip"),
        "pfr": _weighted_average(sessions, "pfr"),
        "aggression_factor": _weighted_average(sessions, "aggression_factor"),
    }

    analyzer = PlayerAnalyzer()
    report = analyzer.generate_player_report(agg_stats)
    progression = ProgressionAnalyzer()
    metrics_for_progress = {
        "total_hands": total_hands,
        "vpip": agg_stats["vpip"],
        "pfr": agg_stats["pfr"],
        "aggression_factor": agg_stats["aggression_factor"],
        "pot_odds_accuracy": _metric(latest, "pot_odds_accuracy", 1.0),
    }
    weaknesses = progression.identify_weaknesses(metrics_for_progress)
    topics = progression.suggest_study_topics(weaknesses)

    vpip_diff = abs(agg_stats["vpip"] - 0.24)
    pfr_diff = abs(agg_stats["pfr"] - 0.18)
    agg_diff = abs(agg_stats["aggression_factor"] - 2.5) / 3 if agg_stats["aggression_factor"] else 0.5
    score = 100 - (vpip_diff * 100 + pfr_diff * 100 + agg_diff * 20)

    recommendations = list(report.get("recommendations") or [])
    for weakness in weaknesses:
        label = weakness.value.replace("_", " ")
        recommendation = f"Run drills for {label}"
        if recommendation not in recommendations:
            recommendations.append(recommendation)

    report.update(
        {
            "recommendations": recommendations,
            "strategy_score": max(0, min(100, int(score))),
            "metric_options": SUPPORTED_METRICS,
            "performance_metrics": {
                "total_hands": total_hands,
                "total_profit": total_profit,
                "latest_decision_accuracy": latest.get("decision_accuracy"),
                "latest_quiz_accuracy": latest.get("quiz_accuracy"),
                "study_topics": topics,
            },
        }
    )
    return report


def get_session_rows(player_name: str, limit: int = 20) -> List[Dict[str, Any]]:
    return sessions_for_player(player_name, limit=limit)


def get_career_report(player_name: Optional[str]) -> Dict[str, Any]:
    """Wrap CareerTracker so the long-term aggregates + milestones become
    an HTTP endpoint instead of CLI-only output.

    Returns a 200-shaped payload even when the player has no sessions yet;
    the route does not 404 on an empty career so the frontend can render a
    placeholder.
    """
    from training.career_tracker import CareerTracker  # lazy import: keeps
    # `app.services.analytics_service` import cheap when career isn't used.

    record = load_player_record(player_name)
    if not record:
        return {
            "player": None,
            "career_metrics": None,
            "session_count": 0,
            "milestones": [],
        }

    name = record.get("name") or "Player"
    sessions = sessions_for_player(name, limit=200)

    tracker = CareerTracker(player_name=name)
    for session in sessions:
        snapshot = dict(session)
        # CareerTracker expects `profit`; some persistence paths write
        # `net_result` instead. Normalize so both work.
        snapshot.setdefault("profit", snapshot.get("net_result", 0))
        try:
            tracker.record_session(snapshot)
        except Exception:
            continue

    report = tracker.generate_career_report()
    return {
        "player": {
            "name": name,
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
    """Run SessionReviewer.generate_session_report against one session.

    `session_index` is 0-based into the player's sessions list, or None to
    pick the most recent (last_session). Returns `{ ..., "report": None }`
    when no session can be resolved; the route turns that into a 404.
    """
    from training.analyzer import SessionReviewer  # lazy import

    record = load_player_record(player_name)
    if not record:
        return {"player": None, "session": None, "report": None}

    sessions = sessions_for_player(record.get("name") or "", limit=200)
    if session_index is None:
        target = sessions[-1] if sessions else (record.get("last_session") or None)
        resolved_index = (len(sessions) - 1) if sessions else None
    else:
        if session_index < 0 or session_index >= len(sessions):
            return {"player": None, "session": None, "report": None}
        target = sessions[session_index]
        resolved_index = session_index

    if not isinstance(target, dict):
        return {"player": None, "session": None, "report": None}

    # SessionReviewer reads `net_result`; persisted sessions sometimes write
    # `profit` instead. Normalize.
    session_for_review = dict(target)
    session_for_review["net_result"] = int(
        session_for_review.get("net_result")
        or session_for_review.get("profit", 0)
        or 0
    )

    reviewer = SessionReviewer()
    try:
        report = reviewer.generate_session_report(session_for_review)
    except Exception as exc:  # noqa: BLE001
        return {
            "player": {
                "name": record.get("name"),
                "skill_level": record.get("skill_level"),
            },
            "session": target,
            "report": None,
            "error": str(exc),
        }

    return {
        "player": {
            "name": record.get("name"),
            "skill_level": record.get("skill_level"),
        },
        "session_index": resolved_index,
        "session": target,
        "report": report,
    }
