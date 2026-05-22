from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.paths import get_data_file

from data.manager import DataManager
from stats.analyzer import PlayerAnalyzer
from training.progression_analyzer import ProgressionAnalyzer

from app.services.bayes_stats import (
    beta_binomial_posterior,
    bb100_credible_interval,
    bootstrap_ci,
    rate_excludes_target,
)
from app.services.variance_analytics import (
    adjust_session_profits,
    cumulative_lines,
    rolling_bb100,
    winrate_stats,
)
from app.services import icm_calculator


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
    """Look up a player record.

    Bug fix: when ``player_name`` is explicitly provided but doesn't match
    any persisted player, return ``None`` rather than silently falling
    back to the most recently played player. The previous behavior
    misled the Analytics page into showing Player A's stats while the
    user thought they were looking at Player B (or a brand-new
    profile). Only the *implicit* "no name provided" case falls back
    to the most-recent player.
    """
    manager = _manager()
    if player_name:
        return manager.get_player(player_name) or None
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


def get_chart_data(
    player_name: Optional[str],
    metric: str = "vpip",
    *,
    window: int = 1,
    include_adjusted: bool = False,
) -> List[Dict[str, Any]]:
    """Per-session chart data, optionally rolling and with EV-adjusted line.

    Each row carries:
      - ``label``: "Session N"
      - ``value``: raw display-formatted metric value
      - ``rolling_value``: rolling-window pooled value (BB/100 only) when
        ``window > 1``, else None
      - ``ev_value``: cumulative EV-adjusted line (for ``profit`` metric
        when ``include_adjusted=True``), else None
    """
    metric = (metric or "vpip").strip().lower()
    if metric not in SUPPORTED_METRICS:
        metric = "vpip"

    sessions = sessions_for_player(player_name)
    if not sessions:
        return []

    big_blind = 1
    try:
        big_blind = int(sessions[-1].get("big_blind") or 1)
    except (TypeError, ValueError):
        big_blind = 1

    # Rolling BB/100 only for the "winrate"/"profit" metrics. Others
    # are too noisy at the session level for rolling to add signal.
    rolling: List[Dict[str, Any]] = []
    if metric in {"profit", "winrate"} and window and window > 1:
        profits_bbs = [_metric(s, "profit", 0.0) / max(1, big_blind) for s in sessions]
        hands = [int(_metric(s, "hands_played", 0)) for s in sessions]
        rolling = rolling_bb100(profits_bbs, hands, window=int(window))

    # All-in EV-adjusted line: cumulative realized vs cumulative EV.
    cumulative: List[Dict[str, Any]] = []
    if include_adjusted and metric == "profit":
        annotated = adjust_session_profits(sessions, big_blind=big_blind)
        profits_bbs = [
            _metric(s, "profit", 0.0) / max(1, big_blind) for s in annotated
        ]
        luck = [s.get("luck_bb") for s in annotated]
        cumulative = cumulative_lines(profits_bbs, luck)

    out: List[Dict[str, Any]] = []
    for index, session in enumerate(sessions, start=1):
        row: Dict[str, Any] = {
            "label": f"Session {index}",
            "value": _display_value(metric, _metric(session, metric, 0.0)),
        }
        if rolling and index - 1 < len(rolling):
            row["rolling_value"] = round(rolling[index - 1]["value"], 2)
            row["window_hands"] = rolling[index - 1]["window_hands"]
        if cumulative and index - 1 < len(cumulative):
            ev_value = cumulative[index - 1]["ev"]
            row["realized_cumulative_bb"] = round(
                cumulative[index - 1]["realized"], 2
            )
            row["ev_cumulative_bb"] = (
                round(ev_value, 2) if ev_value is not None else None
            )
        out.append(row)
    return out


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


def _empty_ci_block(target_low: Optional[float] = None, target_high: Optional[float] = None) -> Dict[str, Any]:
    """Default Bayesian CI block for players with no data yet.

    Keeps the response shape stable so the frontend can render
    BayesianStatCard without conditional fallbacks.
    """
    payload = {
        "value": 0.0,
        "ci_lower": 0.0,
        "ci_upper": 0.0,
        "sample_size": 0,
        "small_sample": True,
    }
    if target_low is not None and target_high is not None:
        payload["target_low"] = float(target_low)
        payload["target_high"] = float(target_high)
        payload["position_vs_target"] = None
    return payload


def get_analytics_report(player_name: Optional[str]) -> Dict[str, Any]:
    record = load_player_record(player_name)
    if not record:
        return {
            "basic_stats": {},
            "playing_style": {
                "player_type": "Unknown",
                "vpip": 0,
                "pfr": 0,
                "aggression_factor": 0,
                # Empty Bayesian blocks keep the response shape stable
                # so the frontend can always render BayesianStatCard.
                "vpip_ci": _empty_ci_block(0.18, 0.28),
                "pfr_ci": _empty_ci_block(0.13, 0.22),
                "aggression_factor_ci": _empty_ci_block(),
            },
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

    # Bayesian credible intervals for the rate stats. Each becomes
    # a {value, ci_lower, ci_upper, sample_size, small_sample}
    # block that the frontend BayesianStatCard renders directly.
    # We reconstruct successes from rate * trials per session and
    # pool across sessions for the posterior.
    style = report.get("playing_style") or {}
    style["vpip_ci"] = _bayes_for_rate(
        sessions, "vpip", target_band=(0.18, 0.28)
    )
    style["pfr_ci"] = _bayes_for_rate(
        sessions, "pfr", target_band=(0.13, 0.22)
    )
    style["aggression_factor_ci"] = _bootstrap_for_metric(
        sessions, "aggression_factor"
    )
    report["playing_style"] = style

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


def _bayes_for_rate(
    sessions: List[Dict[str, Any]],
    metric: str,
    *,
    target_band: Optional[tuple] = None,
) -> Dict[str, Any]:
    """Build a credible interval block for a rate metric.

    Pool successes (rate * hands) and trials (hands) across sessions,
    then run Beta-Binomial. Stays correct when individual sessions
    have varying sample sizes.
    """
    total_trials = 0
    total_successes = 0
    for s in sessions:
        hands = int(_metric(s, "hands_played", 0))
        if hands <= 0:
            continue
        total_trials += hands
        rate = _metric(s, metric, 0.0)
        # Clamp rate to [0, 1] before computing successes; legacy data
        # occasionally has out-of-range artifacts.
        rate = max(0.0, min(1.0, rate))
        total_successes += int(round(rate * hands))
    posterior = beta_binomial_posterior(total_successes, total_trials)
    payload = posterior.as_dict()
    if target_band is not None:
        payload["position_vs_target"] = rate_excludes_target(
            posterior, target_band=target_band
        )
        payload["target_low"] = float(target_band[0])
        payload["target_high"] = float(target_band[1])
    return payload


def _bootstrap_for_metric(
    sessions: List[Dict[str, Any]],
    metric: str,
) -> Dict[str, Any]:
    """Bootstrap CI for a per-session continuous metric (e.g. agg factor)."""
    values = [
        _metric(s, metric, 0.0)
        for s in sessions
        if _metric(s, "hands_played", 0) > 0
    ]
    if not values:
        return {
            "value": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "sample_size": 0,
            "small_sample": True,
        }
    ci = bootstrap_ci(values, statistic="mean", iterations=500)
    return ci.as_dict()


def get_session_rows(player_name: str, limit: int = 20) -> List[Dict[str, Any]]:
    return sessions_for_player(player_name, limit=limit)


def _decision_ev_value(decision: Dict[str, Any], key: str) -> Optional[float]:
    value = decision.get(key)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def get_ev_leak_report(player_name: Optional[str], limit: int = 20) -> Dict[str, Any]:
    """Group priced decision mistakes by tactical context.

    `limit` caps the number of leak groups returned. The service scans up to
    500 recent hands so the grouped result is still meaningful when only a few
    decisions per hand carry EV metadata.
    """
    record = load_player_record(player_name)
    if not record:
        return {
            "player": player_name,
            "priced_decision_count": 0,
            "mistake_count": 0,
            "total_ev_loss_bb": 0.0,
            "total_ev_loss_chips": 0.0,
            "worst_group": None,
            "groups": [],
        }

    player = str(record.get("name") or player_name or "Guest")
    group_limit = max(1, min(int(limit or 20), 100))
    try:
        hands = _manager().load_hand_history(player, limit=500, reverse=True)
    except Exception:
        hands = []

    groups: Dict[tuple, Dict[str, Any]] = {}
    priced_count = 0
    mistake_count = 0
    total_loss_bb = 0.0
    total_loss_chips = 0.0

    for hand in hands:
        if not isinstance(hand, dict):
            continue
        hand_number = hand.get("hand_number")
        session_id = hand.get("session_id") or (hand.get("meta") or {}).get("session_id")
        decisions = hand.get("decision_points") or []
        if not isinstance(decisions, list):
            continue

        for decision in decisions:
            if not isinstance(decision, dict):
                continue
            ev_loss_bb = _decision_ev_value(decision, "ev_loss_bb")
            if ev_loss_bb is None:
                continue

            priced_count += 1
            ev_loss_chips = _decision_ev_value(decision, "ev_loss_chips") or 0.0
            if ev_loss_bb <= 0 and ev_loss_chips <= 0:
                continue

            mistake_count += 1
            total_loss_bb += max(0.0, ev_loss_bb)
            total_loss_chips += max(0.0, ev_loss_chips)

            opponent = decision.get("opponent") if isinstance(decision.get("opponent"), dict) else {}
            key = (
                str(decision.get("betting_round") or "unknown"),
                str(decision.get("hero_position") if decision.get("hero_position") is not None else "unknown"),
                str(decision.get("chosen_action") or "unknown"),
                str(decision.get("recommended_action") or "unknown"),
                str(opponent.get("type") or "unknown"),
            )
            group = groups.setdefault(
                key,
                {
                    "street": key[0],
                    "position": key[1],
                    "chosen_action": key[2],
                    "recommended_action": key[3],
                    "opponent_type": key[4],
                    "decision_count": 0,
                    "total_ev_loss_bb": 0.0,
                    "total_ev_loss_chips": 0.0,
                    "average_ev_loss_bb": 0.0,
                    "examples": [],
                },
            )
            group["decision_count"] += 1
            group["total_ev_loss_bb"] += max(0.0, ev_loss_bb)
            group["total_ev_loss_chips"] += max(0.0, ev_loss_chips)
            if len(group["examples"]) < 3:
                group["examples"].append(
                    {
                        "hand_number": hand_number,
                        "session_id": session_id,
                        "ev_loss_bb": round(max(0.0, ev_loss_bb), 4),
                        "quality": decision.get("quality"),
                    }
                )

    rows = []
    for group in groups.values():
        count = max(1, int(group["decision_count"]))
        group["total_ev_loss_bb"] = round(float(group["total_ev_loss_bb"]), 4)
        group["total_ev_loss_chips"] = round(float(group["total_ev_loss_chips"]), 4)
        group["average_ev_loss_bb"] = round(group["total_ev_loss_bb"] / count, 4)
        rows.append(group)

    rows.sort(key=lambda item: (item["total_ev_loss_bb"], item["decision_count"]), reverse=True)
    rows = rows[:group_limit]

    return {
        "player": player,
        "priced_decision_count": priced_count,
        "mistake_count": mistake_count,
        "total_ev_loss_bb": round(total_loss_bb, 4),
        "total_ev_loss_chips": round(total_loss_chips, 4),
        "worst_group": rows[0] if rows else None,
        "groups": rows,
    }


def get_regret_heatmap(
    player_name: Optional[str],
    *,
    scan_hands: int = 500,
) -> Dict[str, Any]:
    """Group priced EV losses by (street, position, spr_bucket).

    Track 3's "regret-by-spot" view. Where ``get_ev_leak_report``
    groups by action context, this view groups by the *structural*
    spot — which street, which seat, which stack-to-pot ratio band.
    The dominating cell tells you where leaks live in the strategy
    space, independent of which specific actions you took.

    Returns a heatmap-shaped payload::

        {
            "player": "...",
            "cells": [
                {"street": "flop", "position": 4, "spr_bucket": 2,
                 "decision_count": 12, "total_ev_loss_bb": -4.5,
                 "average_ev_loss_bb": -0.375,
                 "example_keys": [{"hand_number": 42, "decision_index": 3}, ...]},
                ...
            ],
            "max_loss_bb": -4.5,
            "totals": { "decisions": 142, "ev_loss_bb": -28.1 }
        }

    The frontend renders this as a colored grid. ``example_keys`` lets
    the user click a cell -> open one of the underlying decisions
    in the drill seeder.
    """
    record = load_player_record(player_name)
    if not record:
        return {
            "player": player_name,
            "cells": [],
            "max_loss_bb": 0.0,
            "totals": {"decisions": 0, "ev_loss_bb": 0.0},
        }

    player = str(record.get("name") or player_name or "Guest")
    try:
        hands = _manager().load_hand_history(player, limit=scan_hands, reverse=True)
    except Exception:
        hands = []

    cells: Dict[tuple, Dict[str, Any]] = {}
    total_decisions = 0
    total_loss = 0.0

    for hand in hands:
        if not isinstance(hand, dict):
            continue
        hand_number = hand.get("hand_number")
        decisions = hand.get("decision_points") or []
        if not isinstance(decisions, list):
            continue

        for idx, decision in enumerate(decisions):
            if not isinstance(decision, dict):
                continue
            ev_loss_bb = _decision_ev_value(decision, "ev_loss_bb")
            if ev_loss_bb is None:
                continue
            total_decisions += 1
            if ev_loss_bb <= 0:
                # Negative or zero means hero played optimally for
                # this priced decision; the cell records counts but
                # not loss.
                pass

            street = str(decision.get("betting_round") or "unknown").lower()
            position = decision.get("hero_position")
            try:
                position = int(position) if position is not None else None
            except (TypeError, ValueError):
                position = None
            # spr_bucket may be missing on legacy decisions; bucket
            # zero is reserved for "unknown" so the heatmap still
            # renders something.
            spr_bucket = decision.get("spr_bucket")
            try:
                spr_bucket = int(spr_bucket) if spr_bucket is not None else 0
            except (TypeError, ValueError):
                spr_bucket = 0

            key = (street, position, spr_bucket)
            cell = cells.setdefault(
                key,
                {
                    "street": street,
                    "position": position,
                    "spr_bucket": spr_bucket,
                    "decision_count": 0,
                    "total_ev_loss_bb": 0.0,
                    "example_keys": [],
                },
            )
            cell["decision_count"] += 1
            cell["total_ev_loss_bb"] += max(0.0, ev_loss_bb)
            total_loss += max(0.0, ev_loss_bb)
            if len(cell["example_keys"]) < 5:
                cell["example_keys"].append(
                    {
                        "hand_number": hand_number,
                        "decision_index": idx,
                        "ev_loss_bb": round(max(0.0, ev_loss_bb), 4),
                    }
                )

    rows: List[Dict[str, Any]] = []
    for cell in cells.values():
        n = max(1, int(cell["decision_count"]))
        cell["total_ev_loss_bb"] = round(float(cell["total_ev_loss_bb"]), 4)
        cell["average_ev_loss_bb"] = round(cell["total_ev_loss_bb"] / n, 4)
        rows.append(cell)
    rows.sort(key=lambda c: c["total_ev_loss_bb"], reverse=True)

    return {
        "player": player,
        "cells": rows,
        "max_loss_bb": rows[0]["total_ev_loss_bb"] if rows else 0.0,
        "totals": {
            "decisions": total_decisions,
            "ev_loss_bb": round(total_loss, 4),
        },
    }


def generate_drill_from_decision(
    player_name: Optional[str],
    *,
    hand_number: int,
    decision_index: int,
) -> Dict[str, Any]:
    """Seed a training drill from a specific recorded decision.

    Looks up the (hand_number, decision_index) pair in the player's
    history, extracts the board / hole cards / pot / position /
    recommended action, and asks ``training_service`` to produce a
    drill scenario tied to that exact spot. The user lands on the
    drill page with a pre-loaded scenario instead of a generic
    "weakness category" placeholder.

    Returns ``{"drill": <drill_dict>}`` on success or
    ``{"drill": None, "error": "..."}`` when the lookup fails.
    """
    record = load_player_record(player_name)
    if not record:
        return {"drill": None, "error": "Player not found."}
    player = str(record.get("name") or player_name or "Guest")

    try:
        hands = _manager().load_hand_history(player, limit=1000, reverse=True)
    except Exception:
        return {"drill": None, "error": "Hand history unavailable."}

    target_hand = None
    for hand in hands:
        if not isinstance(hand, dict):
            continue
        if int(hand.get("hand_number") or -1) == int(hand_number):
            target_hand = hand
            break
    if target_hand is None:
        return {"drill": None, "error": f"Hand {hand_number} not found."}

    decisions = target_hand.get("decision_points") or []
    if decision_index < 0 or decision_index >= len(decisions):
        return {"drill": None, "error": "Decision index out of range."}
    decision = decisions[decision_index]
    if not isinstance(decision, dict):
        return {"drill": None, "error": "Decision malformed."}

    # Delegate to training_service for actual drill assembly; we just
    # pass it the extracted scenario seed.
    from app.services import training_service

    try:
        drill = training_service.generate_drill_from_decision(
            player_name=player,
            decision=decision,
            hand_meta=target_hand.get("meta") or {},
            hand_number=int(hand_number),
            decision_index=int(decision_index),
        )
    except Exception as exc:  # noqa: BLE001
        return {"drill": None, "error": str(exc)}

    return {"drill": drill, "source": {"hand_number": int(hand_number), "decision_index": int(decision_index)}}


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


def get_variance_report(
    player_name: Optional[str],
    *,
    bankroll_bbs: Optional[float] = None,
) -> Dict[str, Any]:
    """Variance, all-in luck delta, risk-of-ruin, Kelly fraction.

    Inputs come from the player's session history. ``bankroll_bbs``
    is optional; when present, risk_of_ruin and kelly_fraction are
    computed against it. When absent, those fields are None.

    The "all_in_luck" block summarizes the cumulative realized minus
    EV-expected chip total across all priced decisions. Positive =
    hero ran above EV; negative = below.
    """
    record = load_player_record(player_name)
    if not record:
        return {
            "player": player_name,
            "winrate": None,
            "rolling_bb100": [],
            "ev_adjusted_lines": [],
            "all_in_luck": None,
            "session_count": 0,
        }

    name = str(record.get("name") or player_name or "Guest")
    sessions = sessions_for_player(name, limit=200)
    if not sessions:
        return {
            "player": name,
            "winrate": None,
            "rolling_bb100": [],
            "ev_adjusted_lines": [],
            "all_in_luck": None,
            "session_count": 0,
        }

    big_blind = 1
    try:
        big_blind = int(sessions[-1].get("big_blind") or 1)
    except (TypeError, ValueError):
        big_blind = 1

    profits_bbs = [_metric(s, "profit", 0.0) / max(1, big_blind) for s in sessions]
    hands = [int(_metric(s, "hands_played", 0)) for s in sessions]

    stats = winrate_stats(profits_bbs, hands, bankroll_bbs=bankroll_bbs)
    rolling = rolling_bb100(profits_bbs, hands, window=5)

    annotated = adjust_session_profits(sessions, big_blind=big_blind)
    luck_bbs = [s.get("luck_bb") for s in annotated]
    ev_lines = cumulative_lines(profits_bbs, luck_bbs)

    total_luck = 0.0
    counted_sessions = 0
    for v in luck_bbs:
        if v is not None:
            total_luck += float(v)
            counted_sessions += 1
    all_in_luck = (
        {
            "luck_bb_total": round(total_luck, 2),
            "sessions_with_data": counted_sessions,
        }
        if counted_sessions > 0
        else None
    )

    # Also fold in a BB/100 CI alongside the std-dev block - the UI
    # renders both together.
    bb100 = bb100_credible_interval(profits_bbs, hands)

    return {
        "player": name,
        "winrate": {
            **stats.as_dict(),
            "ci_lower": bb100.ci_lower,
            "ci_upper": bb100.ci_upper,
            "small_sample": bb100.small_sample,
        },
        "rolling_bb100": rolling,
        "ev_adjusted_lines": ev_lines,
        "all_in_luck": all_in_luck,
        "session_count": len(sessions),
    }


def get_icm_report(
    player_name: Optional[str],
    *,
    stacks: Optional[List[float]] = None,
    payouts: Optional[List[float]] = None,
    hero_index: int = 0,
) -> Dict[str, Any]:
    """ICM equities + risk premium for a tournament spot.

    Two input modes:

      1. **Explicit**: caller passes ``stacks`` and ``payouts``. The
         service computes Malmuth-Harville directly. This is the
         mode the API uses when the frontend supplies a hypothetical
         table.

      2. **Implicit**: ``stacks`` is None. The service tries to read
         the player's most recent tournament session's final-table
         state. If no tournament data exists, returns a placeholder.

    ``hero_index`` selects which seat is "you" for the risk premium
    calculation (defaults to seat 0).
    """
    if stacks is not None and payouts is not None:
        try:
            result = icm_calculator.malmuth_harville(stacks, payouts)
        except ValueError as exc:
            return {
                "player": player_name,
                "error": str(exc),
                "icm": None,
                "risk_premium": None,
            }
        # Risk premium for hero's seat with a representative all-in
        # delta of the hero's current stack (i.e. shove for stack).
        rp = None
        try:
            hero_stack = float(stacks[hero_index])
            if hero_stack > 0:
                rp = icm_calculator.risk_premium(
                    hero_index,
                    stacks,
                    payouts,
                    win_chip_delta=hero_stack,
                    lose_chip_delta=hero_stack,
                )
        except (IndexError, ValueError):
            rp = None
        return {
            "player": player_name,
            "icm": result.as_dict(),
            "hero_index": hero_index,
            "risk_premium": rp,
        }

    # Implicit: pull from most recent tournament session.
    record = load_player_record(player_name)
    if not record:
        return {
            "player": player_name,
            "icm": None,
            "risk_premium": None,
            "note": "No player record found.",
        }
    sessions = sessions_for_player(record.get("name"), limit=50)
    tourneys = [
        s for s in sessions if str(s.get("game_type") or "").lower() == "tournament"
    ]
    if not tourneys:
        return {
            "player": record.get("name"),
            "icm": None,
            "risk_premium": None,
            "note": "No tournament sessions yet. Use explicit stacks+payouts to inspect any spot.",
        }
    latest = tourneys[-1]
    stacks_payload = latest.get("final_stacks") or latest.get("stacks") or None
    payouts_payload = latest.get("payouts") or None
    if not stacks_payload or not payouts_payload:
        return {
            "player": record.get("name"),
            "icm": None,
            "risk_premium": None,
            "note": "Latest tournament didn't persist stack/payout data.",
        }
    return get_icm_report(
        player_name=record.get("name"),
        stacks=stacks_payload,
        payouts=payouts_payload,
        hero_index=int(latest.get("hero_index") or 0),
    )
