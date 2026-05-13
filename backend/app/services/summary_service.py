from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.paths import get_data_file

from data.manager import DataManager


OPTIMAL = {
    "vpip": (0.20, 0.28, 0.24),
    "pfr": (0.15, 0.22, 0.18),
    "aggression_factor": (2.0, 3.5, 2.5),
}

WEAKNESS_LABELS = {
    "too_loose": "Tighten opening ranges",
    "too_tight": "Open wider in late position",
    "too_passive": "Increase value aggression",
    "too_aggressive": "Trim bluff frequency",
    "poor_pot_odds": "Pot odds + equity drills",
    "poor_position_play": "Position-based ranges",
    "weak_3bet_defense": "3-bet defense reps",
    "poor_bet_sizing": "Bet sizing calibration",
    "tilt_prone": "Reset and mindset training",
}

TOPIC_LABELS = {
    "starting_hands": "Preflop opening ranges",
    "preflop_hand_selection": "Preflop range discipline",
    "position_awareness": "Position leverage drills",
    "betting_for_value": "Thin value extraction",
    "aggression": "Aggression timing reps",
    "bet_sizing": "Sizing calibration",
    "pot_odds_calculation": "Pot odds speed drills",
    "drawing_hands": "Draws and semi-bluffs",
    "value_betting": "Value targets",
}


def build_summary(player_name: Optional[str] = None) -> Dict[str, Any]:
    record = _load_player_record(player_name)
    if not record:
        return _default_summary()

    last_session, prev_session = _get_sessions(record)

    vpip = _metric(last_session, "vpip", 0.0)
    pfr = _metric(last_session, "pfr", 0.0)
    agg = _metric(last_session, "aggression_factor", 0.0)
    decision = _metric(last_session, "decision_accuracy", 0.0)

    live_metrics = [
        _metric_block(
            "VPIP",
            _fmt_pct(vpip),
            _fmt_delta_pct(vpip, _metric(prev_session, "vpip", 0.0)),
            _tone_in_range(vpip, OPTIMAL["vpip"][0], OPTIMAL["vpip"][1]),
        ),
        _metric_block(
            "PFR",
            _fmt_pct(pfr),
            _fmt_delta_pct(pfr, _metric(prev_session, "pfr", 0.0)),
            _tone_in_range(pfr, OPTIMAL["pfr"][0], OPTIMAL["pfr"][1]),
        ),
        _metric_block(
            "AGG",
            f"{agg:.1f}",
            _fmt_delta_float(agg, _metric(prev_session, "aggression_factor", 0.0)),
            _tone_in_range(agg, OPTIMAL["aggression_factor"][0], OPTIMAL["aggression_factor"][1]),
        ),
        _metric_block(
            "DEC",
            _fmt_pct(decision),
            _fmt_delta_pct(decision, _metric(prev_session, "decision_accuracy", 0.0)),
            "good" if decision >= 0.65 else "warn",
        ),
    ]

    training_tracks = _build_training_tracks(record, last_session)
    focus_queue = _build_focus_queue(record)
    timeline = _build_timeline(record)

    return {
        "player": {
            "name": record.get("name", "Player"),
            "skill_level": record.get("skill_level"),
            "last_played": record.get("last_played"),
        },
        "live_metrics": live_metrics,
        "training_tracks": training_tracks,
        "focus_queue": focus_queue,
        "timeline": timeline,
    }


def list_players() -> List[Dict[str, Any]]:
    manager = _get_manager()
    players = manager.list_players(sort_by="last_played", reverse=True)
    return [
        {
            "name": player.get("name"),
            "bankroll": player.get("bankroll"),
            "last_played": player.get("last_played"),
            "skill_level": player.get("skill_level"),
        }
        for player in players
    ]


def get_player(player_name: str) -> Optional[Dict[str, Any]]:
    manager = _get_manager()
    player = manager.get_player(player_name)
    if not player:
        return None
    return {
        "name": player.get("name"),
        "bankroll": player.get("bankroll"),
        "last_played": player.get("last_played"),
        "skill_level": player.get("skill_level"),
        "sessions": player.get("sessions", []),
        "last_session": player.get("last_session"),
    }


def _get_manager() -> DataManager:
    return DataManager(data_file=str(get_data_file()))


def _load_player_record(player_name: Optional[str]) -> Optional[Dict[str, Any]]:
    manager = _get_manager()
    if player_name:
        record = manager.get_player(player_name)
        if record:
            return record
    players = manager.list_players(sort_by="last_played", reverse=True)
    return players[0] if players else None


def _get_sessions(record: Dict[str, Any]) -> List[Optional[Dict[str, Any]]]:
    sessions = _sessions_for_record(record)
    last_session = record.get("last_session") or (sessions[-1] if sessions else {})
    prev_session = sessions[-2] if len(sessions) >= 2 else {}
    return [last_session, prev_session]


def _sessions_for_record(record: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
    sessions = record.get("sessions") or []
    if not isinstance(sessions, list):
        sessions = []

    if not sessions and record.get("name"):
        try:
            sessions = _get_manager().get_sessions(str(record["name"]), limit=limit)
        except Exception:
            sessions = []

    records = [dict(session) for session in sessions if isinstance(session, dict)]
    records.sort(key=lambda s: s.get("updated_at") or s.get("ended_at") or s.get("started_at") or s.get("created_at") or "")
    return records[-limit:]


def _build_training_tracks(record: Dict[str, Any], last_session: Dict[str, Any]) -> List[Dict[str, Any]]:
    vpip = _metric(last_session, "vpip", 0.0)
    pfr = _metric(last_session, "pfr", 0.0)
    agg = _metric(last_session, "aggression_factor", 0.0)
    decision = _metric(last_session, "decision_accuracy", 0.0)
    quiz_accuracy = _metric(last_session, "quiz_accuracy", 0.0)
    hands_played = int(_metric(last_session, "hands_played", 0))

    preflop_score = 1 - (abs(vpip - OPTIMAL["vpip"][2]) + abs(pfr - OPTIMAL["pfr"][2])) / 0.5
    postflop_score = 1 - abs(agg - OPTIMAL["aggression_factor"][2]) / 3.0
    tournament_score = min(hands_played / 500.0, 1.0)
    range_score = quiz_accuracy if quiz_accuracy > 0 else decision

    return [
        {
            "title": "Preflop Mastery",
            "summary": "Ranges, position, open sizes, 3-bet defense",
            "cadence": "Daily drills",
            "intensity": "Core",
            "progress": _clamp_percent(preflop_score),
        },
        {
            "title": "Postflop Pressure",
            "summary": "Board texture, sizing, multi-street planning",
            "cadence": "Scenario lab",
            "intensity": "Advanced",
            "progress": _clamp_percent(postflop_score),
        },
        {
            "title": "Tournament Basics",
            "summary": "Stack depth, blind pressure, short-stack decisions",
            "cadence": "Event prep",
            "intensity": "Focused",
            "progress": _clamp_percent(tournament_score),
        },
        {
            "title": "Equity Basics",
            "summary": "Pot odds, outs, blockers, draw math",
            "cadence": "Math review",
            "intensity": "Core",
            "progress": _clamp_percent(range_score),
        },
    ]


def _build_focus_queue(record: Dict[str, Any]) -> List[str]:
    items: List[str] = []
    weaknesses = record.get("weaknesses") or []
    topics = record.get("recommended_topics") or []

    for weakness in weaknesses:
        label = WEAKNESS_LABELS.get(str(weakness).lower())
        if label:
            items.append(label)

    for topic in topics:
        label = TOPIC_LABELS.get(str(topic).lower())
        if label:
            items.append(label)

    if not items:
        items = [
            "Position-based range review",
            "Bet sizing calibration",
            "Turn barrel frequency",
            "River bluff selectivity",
        ]

    return _dedupe(items)[:4]


def _build_timeline(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    recent_hands = record.get("recent_hands") or []
    timeline: List[Dict[str, Any]] = []
    for hand in recent_hands[-3:]:
        started_at = hand.get("started_at", "")
        time_label = _format_time(started_at)
        hand_number = hand.get("hand_number", "?")
        meta = hand.get("meta", {})
        hero_won = meta.get("hero_won")
        result = "Won pot" if hero_won else "Lost pot"
        timeline.append(
            {
                "time": time_label,
                "label": f"Hand {hand_number}",
                "detail": result,
            }
        )

    if not timeline:
        timeline = [
            {"time": "00:00", "label": "Session start", "detail": "No recent hands yet"},
        ]

    return timeline


def _metric(session: Dict[str, Any], key: str, default: float) -> float:
    if not session:
        return default
    value = session.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _metric_block(label: str, value: str, delta: str, tone: str) -> Dict[str, str]:
    return {"label": label, "value": value, "delta": delta, "tone": tone}


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _fmt_delta_pct(value: float, prev: float) -> str:
    diff = value - prev
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff * 100:.0f}%"


def _fmt_delta_float(value: float, prev: float) -> str:
    diff = value - prev
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff:.1f}"


def _tone_in_range(value: float, low: float, high: float) -> str:
    return "good" if low <= value <= high else "warn"


def _clamp_percent(score: float) -> int:
    if score != score:
        return 0
    return max(0, min(100, int(round(score * 100))))


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    unique = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _format_time(timestamp: str) -> str:
    if not timestamp:
        return "00:00"
    try:
        return datetime.fromisoformat(timestamp).strftime("%H:%M")
    except ValueError:
        return "00:00"


def _default_summary() -> Dict[str, Any]:
    return {
        "player": {"name": "Guest", "skill_level": "rookie", "last_played": None},
        "live_metrics": [
            _metric_block("VPIP", "0%", "+0%", "warn"),
            _metric_block("PFR", "0%", "+0%", "warn"),
            _metric_block("AGG", "0.0", "+0.0", "warn"),
            _metric_block("DEC", "0%", "+0%", "warn"),
        ],
        "training_tracks": [
            {
                "title": "Preflop Mastery",
                "summary": "Ranges, position, open sizes, 3-bet defense",
                "cadence": "Daily drills",
                "intensity": "Core",
                "progress": 0,
            },
            {
                "title": "Postflop Pressure",
                "summary": "Board texture, sizing, multi-street planning",
                "cadence": "Scenario lab",
                "intensity": "Advanced",
                "progress": 0,
            },
            {
                "title": "Tournament Basics",
                "summary": "Stack depth, blind pressure, short-stack decisions",
                "cadence": "Event prep",
                "intensity": "Focused",
                "progress": 0,
            },
            {
                "title": "Equity Basics",
                "summary": "Pot odds, outs, blockers, draw math",
                "cadence": "Math review",
                "intensity": "Core",
                "progress": 0,
            },
        ],
        "focus_queue": [
            "Position-based range review",
            "Bet sizing calibration",
            "Turn barrel frequency",
            "River bluff selectivity",
        ],
        "timeline": [
            {"time": "00:00", "label": "Session start", "detail": "No recent hands yet"},
        ],
    }

def get_chart_data(player_name: str, metric: str = "vpip") -> List[Dict[str, Any]]:
    from app.services.analytics_service import get_chart_data as build_chart_data

    return build_chart_data(player_name, metric)


def get_analytics_report(player_name: str) -> Dict[str, Any]:
    from app.services.analytics_service import get_analytics_report as build_analytics_report

    return build_analytics_report(player_name)
