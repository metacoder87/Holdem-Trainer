from typing import Any, Dict, Iterable, List, Optional

from app.core.paths import get_data_file

from data.manager import DataManager


STREET_ORDER = ["preflop", "flop", "turn", "river"]


def list_hands(
    player_name: str,
    *,
    limit: int = 50,
    reverse: bool = True,
    won: Optional[bool] = None,
    min_pot: Optional[int] = None,
    max_pot: Optional[int] = None,
    street_at_least: Optional[str] = None,
    before_hand_number: Optional[int] = None,
    after_hand_number: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return hand records, optionally filtered.

    Filters operate on already-loaded records (per-player JSONL files). For
    larger histories we'd push these into the storage layer; for now JSONL
    sizes stay small enough that in-memory filtering is acceptable.

    Cursor pagination is via `before_hand_number` (newest-first) or
    `after_hand_number` (oldest-first). Both are exclusive bounds.
    """
    manager = DataManager(data_file=str(get_data_file()))

    has_filters = any(
        value is not None
        for value in (won, min_pot, max_pot, street_at_least, before_hand_number, after_hand_number)
    )
    raw_limit = limit if not has_filters else max(limit * 4, 200)
    records = manager.load_hand_history(player_name, limit=raw_limit, reverse=reverse)

    if before_hand_number is not None:
        cutoff = int(before_hand_number)
        records = [r for r in records if isinstance(r, dict) and int(r.get("hand_number") or 0) < cutoff]
    if after_hand_number is not None:
        cutoff = int(after_hand_number)
        records = [r for r in records if isinstance(r, dict) and int(r.get("hand_number") or 0) > cutoff]

    return list(_apply_filters(
        records,
        player_name=player_name,
        won=won,
        min_pot=min_pot,
        max_pot=max_pot,
        street_at_least=street_at_least,
    ))[:limit]


def _apply_filters(
    records: Iterable[Dict[str, Any]],
    *,
    player_name: str,
    won: Optional[bool],
    min_pot: Optional[int],
    max_pot: Optional[int],
    street_at_least: Optional[str],
) -> Iterable[Dict[str, Any]]:
    threshold = STREET_ORDER.index(street_at_least) if street_at_least in STREET_ORDER else None

    for record in records:
        if not isinstance(record, dict):
            continue

        pot = int(record.get("pot_total") or 0)
        if min_pot is not None and pot < int(min_pot):
            continue
        if max_pot is not None and pot > int(max_pot):
            continue

        if won is not None:
            winners = record.get("winners") or []
            hero_won = isinstance(winners, list) and player_name in winners
            if bool(won) != bool(hero_won):
                continue

        if threshold is not None:
            board = record.get("board") or []
            reached = 0  # preflop
            n = len(board)
            if n >= 3:
                reached = 1
            if n >= 4:
                reached = 2
            if n >= 5:
                reached = 3
            if reached < threshold:
                continue

        yield record


def get_hand(player_name: str, hand_number: int) -> Optional[Dict[str, Any]]:
    if hand_number <= 0:
        return None
    hands = list_hands(player_name, limit=200, reverse=False)
    for hand in hands:
        if int(hand.get("hand_number", 0) or 0) == int(hand_number):
            return hand
    return None


def get_replay(player_name: str, hand_number: int) -> Optional[Dict[str, Any]]:
    """Build an ordered street-by-street replay payload for one hand.

    Combines actions, decision points, and board-by-street snapshots into a
    single event stream so the UI can step through the hand without re-deriving
    structure from raw history records.
    """
    hand = get_hand(player_name, hand_number)
    if not hand:
        return None

    actions = list(hand.get("actions") or [])
    decisions = list(hand.get("decision_points") or [])
    board_by_street = hand.get("board_by_street") or {}
    meta = hand.get("meta") or {}

    decisions_by_street: Dict[str, List[Dict[str, Any]]] = {}
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        street = str(decision.get("betting_round", "preflop"))
        decisions_by_street.setdefault(street, []).append(decision)

    streets: List[Dict[str, Any]] = []
    for street in STREET_ORDER:
        street_actions = [a for a in actions if isinstance(a, dict) and a.get("betting_round") == street]
        if not street_actions and street != "preflop":
            continue
        streets.append(
            {
                "name": street,
                "board": list(board_by_street.get(street) or []) if street != "preflop" else [],
                "actions": street_actions,
                "decisions": decisions_by_street.get(street, []),
            }
        )

    return {
        "hand_number": hand.get("hand_number"),
        "started_at": hand.get("started_at"),
        "ended_at": hand.get("ended_at"),
        "hero_hole_cards": list(hand.get("hero_hole_cards") or []),
        "winners": list(hand.get("winners") or []),
        "pot_total": int(hand.get("pot_total") or 0),
        "meta": meta,
        "streets": streets,
        "summary": {
            "small_blind": meta.get("small_blind"),
            "big_blind": meta.get("big_blind"),
            "ante": meta.get("ante"),
            "blind_level": meta.get("blind_level"),
            "game_type": meta.get("game_type"),
            "limit_type": meta.get("limit_type"),
            "hero_won": meta.get("hero_won"),
        },
    }
