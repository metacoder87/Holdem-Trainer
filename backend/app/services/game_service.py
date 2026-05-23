import contextlib
import io
import json
import math
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.paths import ensure_src_path, get_data_file

ensure_src_path()

from data.manager import DataManager
from game.game_engine import GameEngine
from game.player import Player

from app.services import gto_advisor


class AutoInputHandler:
    def get_menu_choice(self, options: List[str], prompt: str = "") -> int:
        for index, option in enumerate(options, start=1):
            label = option.lower()
            if "call" in label or "check" in label:
                return index
        return 1 if options else 1

    def get_number_input(
        self,
        prompt: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        integer_only: bool = False,
    ) -> float:
        if min_value is not None:
            return float(int(min_value) if integer_only else min_value)
        return 0.0

    def get_yes_no_input(self, prompt: str) -> bool:
        return False


class SetupInputHandler:
    def __init__(self, opponents: int):
        self._opponents = max(1, int(opponents or 1))

    def get_menu_choice(self, options: List[str], prompt: str = "") -> int:
        return 1

    def get_number_input(
        self,
        prompt: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        integer_only: bool = False,
    ) -> float:
        value = float(self._opponents)
        if min_value is not None:
            value = max(float(min_value), value)
        if max_value is not None:
            value = min(float(max_value), value)
        if integer_only:
            return float(int(value))
        return float(value)

    def get_yes_no_input(self, prompt: str) -> bool:
        return False


@dataclass
class InputRequest:
    kind: str
    prompt: str
    options: Optional[List[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    integer_only: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "prompt": self.prompt,
            "options": list(self.options) if self.options is not None else None,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "integer_only": self.integer_only,
        }


def _parse_number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a number")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value.strip())
    raise ValueError("Unsupported number input")


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(int(value))
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"y", "yes", "true", "1"}:
            return True
        if normalized in {"n", "no", "false", "0"}:
            return False
    raise ValueError("Unsupported boolean input")


class ApiInputHandler:
    def __init__(self) -> None:
        self._queue: "queue.Queue[Any]" = queue.Queue()
        self._lock = threading.Lock()
        self._pending: Optional[InputRequest] = None
        self._last_error: Optional[str] = None
        self._version = 0
        self.on_pending_change = None

    def submit(self, value: Any) -> None:
        self._queue.put(value)

    def version(self) -> int:
        with self._lock:
            return self._version

    def pending_request(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._pending.to_dict() if self._pending else None

    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._last_error

    def clear_pending(self) -> None:
        with self._lock:
            self._pending = None
            self._last_error = None
            self._version += 1
        if callable(self.on_pending_change):
            self.on_pending_change(None)

    def _set_error(self, message: str) -> None:
        with self._lock:
            self._last_error = message
            self._version += 1

    def _set_pending(self, request: InputRequest) -> None:
        with self._lock:
            self._pending = request
            self._last_error = None
            self._version += 1
        if callable(self.on_pending_change):
            self.on_pending_change(request.to_dict())

    def _wait_for(self, request: InputRequest, parser, validator, error_message: str) -> Any:
        self._set_pending(request)
        while True:
            raw = self._queue.get()
            try:
                value = parser(raw)
            except (TypeError, ValueError):
                self._set_error("Invalid input format.")
                continue
            if not validator(value):
                self._set_error(error_message)
                continue
            self.clear_pending()
            return value

    def get_menu_choice(self, options: List[str], prompt: str = "Choose an option") -> int:
        total = len(options)
        request = InputRequest(
            kind="menu",
            prompt=prompt,
            options=list(options),
            min_value=1,
            max_value=total,
            integer_only=True,
        )

        def validator(value: float) -> bool:
            return value.is_integer() and 1 <= int(value) <= total

        value = self._wait_for(request, _parse_number, validator, f"Select 1-{total}.")
        return int(value)

    def get_number_input(
        self,
        prompt: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        integer_only: bool = False,
    ) -> float:
        request = InputRequest(
            kind="number",
            prompt=prompt,
            min_value=min_value,
            max_value=max_value,
            integer_only=integer_only,
        )

        def validator(value: float) -> bool:
            if integer_only and not value.is_integer():
                return False
            if min_value is not None and value < float(min_value):
                return False
            if max_value is not None and value > float(max_value):
                return False
            return True

        error_message = "Enter a valid number."
        if min_value is not None and max_value is not None:
            error_message = f"Enter a value between {min_value} and {max_value}."
        elif min_value is not None:
            error_message = f"Enter a value >= {min_value}."
        elif max_value is not None:
            error_message = f"Enter a value <= {max_value}."

        value = self._wait_for(request, _parse_number, validator, error_message)
        if integer_only:
            return float(int(value))
        return float(value)

    def get_yes_no_input(self, prompt: str) -> bool:
        request = InputRequest(kind="yes_no", prompt=prompt)
        value = self._wait_for(request, _parse_bool, lambda _: True, "Enter yes or no.")
        return bool(value)


@dataclass
class LiveSession:
    id: str
    player_name: str
    game_type: str
    limit_type: str
    config: Dict[str, Any]
    engine: GameEngine
    input_handler: ApiInputHandler
    status: str = "ready"
    thread: Optional[threading.Thread] = None
    last_hand: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None
    terminal_reason: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _coach_cache_key: Optional[str] = field(default=None, repr=False)
    _coach_cache_val: Optional[Dict[str, Any]] = field(default=None, repr=False)
    _snapshot_timer: Optional[threading.Timer] = field(default=None, repr=False)
    _snapshot_lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _snapshot_reason: Optional[str] = field(default=None, repr=False)
    _snapshot_deleted: bool = field(default=False, repr=False)

    def touch(self) -> None:
        self.updated_at = time.time()

    def public_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "player_name": self.player_name,
            "game_type": self.game_type,
            "limit_type": self.limit_type,
            "status": self.status,
            "terminal_reason": self.terminal_reason,
            "config": self.config,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def schedule_snapshot(self, reason: str, *, sync: bool = False) -> None:
        if self._snapshot_deleted:
            return
        with self._snapshot_lock:
            self._snapshot_reason = reason
            if self._snapshot_timer is not None:
                self._snapshot_timer.cancel()
                self._snapshot_timer = None
            if sync:
                _persist_live_snapshot(self, reason)
                return
            self._snapshot_timer = threading.Timer(0.05, _persist_live_snapshot, args=(self, reason))
            self._snapshot_timer.daemon = True
            self._snapshot_timer.start()

    def flush_snapshot(self, reason: str = "flush") -> None:
        with self._snapshot_lock:
            if self._snapshot_timer is not None:
                self._snapshot_timer.cancel()
                self._snapshot_timer = None
        if not self._snapshot_deleted:
            _persist_live_snapshot(self, reason)


SESSIONS: Dict[str, LiveSession] = {}
SESSIONS_LOCK = threading.RLock()


def cleanup_sessions(now: Optional[float] = None) -> int:
    """Remove completed idle sessions from memory after the configured TTL."""
    current_time = time.time() if now is None else now
    expired: List[str] = []
    with SESSIONS_LOCK:
        for session_id, session in SESSIONS.items():
            active_thread = session.thread and session.thread.is_alive()
            if active_thread:
                continue
            if current_time - session.updated_at > settings.SESSION_TTL_SECONDS:
                expired.append(session_id)
        for session_id in expired:
            SESSIONS.pop(session_id, None)
    return len(expired)


def list_modes() -> List[Dict[str, Any]]:
    return [
        {
            "id": "cash_no_limit",
            "label": "Cash Game (No Limit)",
            "description": "Standard cash game with dynamic stack sizes.",
            "defaults": {"small_blind": 10, "big_blind": 20, "opponents": 3},
        },
        {
            "id": "cash_limit",
            "label": "Cash Game (Limit)",
            "description": "Fixed-limit betting with capped raises.",
            "defaults": {"small_blind": 10, "big_blind": 20, "opponents": 3},
        },
        {
            "id": "tournament",
            "label": "Tournament",
            "description": "Single-table tournament with blind levels.",
            "defaults": {"buy_in": 1000, "starting_chips": 10000, "opponents": 5},
        },
    ]


def _build_engine(
    *,
    player_name: str,
    game_type: str,
    limit_type: str,
    config: Dict[str, Any],
) -> LiveSession:
    manager = DataManager(data_file=str(get_data_file()))
    record = manager.get_player(player_name)
    if not record:
        try:
            record = manager.create_player(player_name, 10000)
        except ValueError:
            record = manager.get_player(player_name) or {}

    bankroll = int(record.get("bankroll", 10000) or 10000)
    buy_in = int(config.get("buy_in", 1000) or 1000)
    if game_type == "tournament" and bankroll < buy_in:
        raise ValueError("Insufficient bankroll for tournament buy-in.")
    human = Player(player_name, bankroll)

    opponents = int(config.get("opponents", 3) or 3)
    setup_handler = SetupInputHandler(opponents)
    engine = GameEngine(human, data_manager=manager, display=None, input_handler=setup_handler)
    engine._test_mode = True
    # Forward villain selection to the engine *before* start_game so
    # the AI roster picks the right style at table setup.
    villain_style = str(config.get("villain_style") or "balanced").lower()
    if villain_style not in {"balanced", "gto"}:
        villain_style = "balanced"
    engine.villain_style = villain_style

    game_config: Dict[str, Any] = {
        "type": game_type,
        "limit": limit_type,
        "small_blind": int(config.get("small_blind", 10) or 10),
        "big_blind": int(config.get("big_blind", 20) or 20),
        "buy_in": buy_in,
        "starting_chips": int(config.get("starting_chips", 10000) or 10000),
        "max_players": opponents + 1,
        "training": bool(config.get("training", False)),
        "in_game_quizzes": bool(config.get("in_game_quizzes", config.get("training", False))),
        "hud": bool(config.get("hud", False)),
        "post_hand_feedback": bool(config.get("post_hand_feedback", False)),
    }

    engine.start_game(game_config)

    if engine.table is None:
        raise ValueError("Failed to initialize session")

    api_input = ApiInputHandler()
    engine.input_handler = api_input

    session_id = uuid.uuid4().hex
    setattr(engine, "external_session_id", session_id)
    return LiveSession(
        id=session_id,
        player_name=player_name,
        game_type=game_type,
        limit_type=limit_type,
        config=config,
        engine=engine,
        input_handler=api_input,
    )


def create_session(payload: Dict[str, Any]) -> Dict[str, Any]:
    cleanup_sessions()
    player_name = payload.get("player_name") or "Guest"
    game_type = payload.get("game_type") or "cash"
    limit_type = payload.get("limit_type") or "no_limit"

    session = _build_engine(
        player_name=player_name,
        game_type=game_type,
        limit_type=limit_type,
        config=payload,
    )
    _attach_session_hooks(session)
    with SESSIONS_LOCK:
        SESSIONS[session.id] = session
    
    # Persist session creation
    try:
        if session.engine.data_manager:
            session.engine.data_manager.create_session(session.public_dict())
    except Exception:
        # Don't fail game if stats fail
        pass
    session.flush_snapshot("create")

    return session.public_dict()


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    session = _get_live_session_or_restore(session_id)
    if not session:
        return None
    with session.lock:
        session.touch()
        return session.public_dict()


def _get_live_session(session_id: str) -> Optional[LiveSession]:
    with SESSIONS_LOCK:
        return SESSIONS.get(session_id)


def _input_request_from_dict(payload: Dict[str, Any]) -> Optional[InputRequest]:
    if not isinstance(payload, dict) or not payload.get("kind"):
        return None
    return InputRequest(
        kind=str(payload.get("kind")),
        prompt=str(payload.get("prompt") or ""),
        options=list(payload.get("options")) if isinstance(payload.get("options"), list) else None,
        min_value=payload.get("min_value"),
        max_value=payload.get("max_value"),
        integer_only=bool(payload.get("integer_only", False)),
    )


def _attach_session_hooks(session: LiveSession) -> None:
    session.engine.set_state_change_callback(lambda reason: session.schedule_snapshot(str(reason)))
    session.input_handler.on_pending_change = lambda _pending: session.schedule_snapshot("pending_input", sync=True)


def _build_live_snapshot(session: LiveSession, reason: str) -> Dict[str, Any]:
    with session.lock:
        pending = session.input_handler.pending_request()
        state_status = _derive_status(session)
        engine = session.engine
        snapshot = {
            "schema_version": 1,
            "session_id": session.id,
            "id": session.id,
            "player_name": session.player_name,
            "game_type": session.game_type,
            "limit_type": session.limit_type,
            "config": dict(session.config),
            "status": state_status,
            "terminal_reason": session.terminal_reason,
            "last_error": session.last_error,
            "last_hand": session.last_hand,
            "pending_input": pending,
            "updated_at": time.time(),
            "persist_reason": reason,
            "deleted": bool(session._snapshot_deleted),
            "engine": engine.to_snapshot(),
            "tournament": {
                "buy_in": getattr(engine, "_tournament_buy_in", None),
                "starting_chips": getattr(engine, "_tournament_starting_chips", None),
                "total_players": getattr(engine, "_tournament_total_players", None),
                "prize_pool": getattr(engine, "_tournament_prize_pool", None),
                "cash_bankroll_after_buy_in": getattr(engine, "_tournament_cash_bankroll_after_buy_in", None),
                "elimination_order": list(getattr(engine, "_tournament_elimination_order", []) or []),
            },
        }
        return snapshot


def _persist_live_snapshot(session: LiveSession, reason: str = "snapshot") -> None:
    try:
        snapshot = _build_live_snapshot(session, reason)
        manager = session.engine.data_manager or DataManager(data_file=str(get_data_file()))
        manager.update_session(
            session.id,
            {
                "id": session.id,
                "player_name": session.player_name,
                "game_type": session.game_type,
                "limit_type": session.limit_type,
                "status": snapshot["status"],
                "terminal_reason": snapshot.get("terminal_reason"),
                "live_snapshot": snapshot,
                "updated_at": snapshot["updated_at"],
            },
        )
    except Exception:
        return


def _restore_live_session(session_id: str) -> Optional[LiveSession]:
    manager = DataManager(data_file=str(get_data_file()))
    get_by_id = getattr(manager, "get_session_by_id", None)
    if not callable(get_by_id):
        return None
    record = get_by_id(session_id)
    if not isinstance(record, dict):
        return None
    snapshot = record.get("live_snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("deleted"):
        return None

    api_input = ApiInputHandler()
    pending = snapshot.get("pending_input") if isinstance(snapshot.get("pending_input"), dict) else None
    if pending:
        request = _input_request_from_dict(pending)
        if request is not None:
            with api_input._lock:
                api_input._pending = request

    engine = GameEngine.restore_from_snapshot(snapshot, data_manager=manager, input_handler=api_input)
    setattr(engine, "external_session_id", session_id)
    session = LiveSession(
        id=session_id,
        player_name=str(snapshot.get("player_name") or record.get("player_name") or "Guest"),
        game_type=str(snapshot.get("game_type") or record.get("game_type") or "cash"),
        limit_type=str(snapshot.get("limit_type") or record.get("limit_type") or "no_limit"),
        config=dict(snapshot.get("config") or record.get("config") or {}),
        engine=engine,
        input_handler=api_input,
        status=str(snapshot.get("status") or record.get("status") or "ready"),
        last_hand=snapshot.get("last_hand") if isinstance(snapshot.get("last_hand"), dict) else None,
        last_error=snapshot.get("last_error"),
        terminal_reason=snapshot.get("terminal_reason"),
        created_at=float(record.get("created_at") or time.time()) if isinstance(record.get("created_at"), (int, float)) else time.time(),
        updated_at=float(snapshot.get("updated_at") or time.time()) if isinstance(snapshot.get("updated_at"), (int, float)) else time.time(),
    )
    _attach_session_hooks(session)
    with SESSIONS_LOCK:
        SESSIONS[session.id] = session
    return session


def _get_live_session_or_restore(session_id: str) -> Optional[LiveSession]:
    session = _get_live_session(session_id)
    if session:
        return session
    return _restore_live_session(session_id)


def _get_terminal_reason(session: LiveSession) -> Optional[str]:
    reason_fn = getattr(session.engine, "get_game_over_reason", None)
    if callable(reason_fn):
        try:
            return reason_fn()
        except Exception:
            return None
    return None


def _refresh_terminal_state(session: LiveSession) -> Optional[str]:
    if session.thread and session.thread.is_alive():
        return session.terminal_reason

    reason = _get_terminal_reason(session)
    session.terminal_reason = reason
    if reason:
        session.status = "game_over"
    return reason


def _derive_status(session: LiveSession) -> str:
    if session.last_error:
        return "error"
    if session.input_handler.pending_request():
        return "awaiting_input"
    if session.terminal_reason or _get_terminal_reason(session):
        session.terminal_reason = session.terminal_reason or _get_terminal_reason(session)
        return "game_over"
    engine_state = getattr(getattr(session.engine, "game_state", None), "value", None)
    if engine_state == "hand_complete" and session.engine.session_tracker.hand_history:
        return "hand_complete"
    active_thread = session.thread and session.thread.is_alive()
    if active_thread:
        return "in_hand"
    if session.last_hand:
        return "hand_complete"
    return "idle"


def _wait_for_update(session: LiveSession, timeout: float = 1.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if session.input_handler.pending_request():
            return
        if session.thread and not session.thread.is_alive():
            return
        time.sleep(0.01)


def _wait_for_input_progress(session: LiveSession, prior_version: int, timeout: float = 1.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if session.input_handler.version() != prior_version:
            return
        if session.thread and not session.thread.is_alive():
            return
        time.sleep(0.01)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def _decision_line(decision: Dict[str, Any]) -> str:
    street = str(decision.get("betting_round") or "hand").replace("_", " ")
    chosen = str(decision.get("chosen_action") or "unknown")
    recommended = str(decision.get("recommended_action") or "review")
    return f"{street}: chose {chosen}, recommended {recommended}"


def _build_worst_decision(decision: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "betting_round": decision.get("betting_round"),
        "chosen_action": decision.get("chosen_action"),
        "recommended_action": decision.get("recommended_action"),
        "quality": decision.get("quality"),
        "equity": _safe_float(decision.get("equity")),
        "required_equity": _safe_float(decision.get("required_equity")),
        "line": _decision_line(decision),
    }
    gto = decision.get("gto")
    if isinstance(gto, dict):
        payload["gto"] = gto
    return payload


def _pick_worst_with_gto(decisions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pick the decision with the largest negative GTO EV-delta, if any.

    Falls back to None when no decision has parseable GTO data. This
    lets the coach prefer GTO-grounded leaks over heuristic ones when
    both are present.
    """
    best: Optional[Dict[str, Any]] = None
    best_delta = 0.0
    for d in decisions:
        gto = d.get("gto") if isinstance(d, dict) else None
        if not isinstance(gto, dict):
            continue
        delta = gto.get("ev_delta_bb")
        if not isinstance(delta, (int, float)):
            continue
        if delta < best_delta:
            best_delta = float(delta)
            best = d
    return best


def _build_coach_notes(session: LiveSession, hand: Dict[str, Any]) -> Dict[str, Any]:
    meta = hand.get("meta") if isinstance(hand.get("meta"), dict) else {}
    winners = hand.get("winners") if isinstance(hand.get("winners"), list) else []
    hero_name = str(meta.get("hero_name") or session.player_name)
    hero_won = bool(meta.get("hero_won")) if "hero_won" in meta else hero_name in winners

    raw_decisions = hand.get("decision_points") if isinstance(hand.get("decision_points"), list) else []
    decisions = [item for item in raw_decisions if isinstance(item, dict)]
    weak_decisions = [
        item
        for item in decisions
        if str(item.get("quality") or "").lower() in {"suboptimal", "mistake", "bad"}
    ]

    # Prefer a GTO-grounded leak (largest negative ev_delta_bb) over
    # the first heuristic mistake. Fall back to the heuristic if no
    # decision in this hand had cached GTO data.
    gto_worst = _pick_worst_with_gto(decisions)
    worst = gto_worst or (weak_decisions[0] if weak_decisions else None)

    if not decisions:
        grade = "B"
        takeaway = "No tracked decision point was tagged; review the replay for the full line."
    elif not weak_decisions and not gto_worst:
        grade = "A"
        takeaway = "No major decision leak was tagged in this hand."
    elif len(weak_decisions) == 1:
        grade = "B"
        takeaway = "One decision drifted from the recommended line."
    else:
        grade = "C"
        takeaway = "Multiple decisions drifted from the recommended line."

    if worst:
        analysis = worst.get("analysis") if isinstance(worst.get("analysis"), dict) else {}
        takeaway = str(analysis.get("reasoning") or analysis.get("advice") or takeaway)

    pot_total = int(_safe_float(hand.get("pot_total") or meta.get("pot_total")))
    outcome = "won" if hero_won else "lost"
    headline = f"{hero_name} {outcome} a ${pot_total} pot with {len(decisions)} tracked decision(s)."

    # Surface GTO summary at the coach_notes level for direct UI access.
    gto_summary = None
    if worst is not None:
        gto = worst.get("gto") if isinstance(worst.get("gto"), dict) else None
        if gto:
            gto_summary = {
                "gto_action": gto.get("gto_action"),
                "gto_frequency": gto.get("gto_frequency"),
                "hero_action": gto.get("hero_action"),
                "hero_frequency": gto.get("hero_frequency"),
                "ev_delta_bb": gto.get("ev_delta_bb"),
                "action_breakdown": gto.get("action_breakdown"),
                "spot_signature": gto.get("spot_signature"),
            }

    return {
        "hero_won": hero_won,
        "headline": headline,
        "hand_grade": grade,
        "takeaway": takeaway,
        "worst_decision": _build_worst_decision(worst) if worst else None,
        "decision_count": len(decisions),
        "gto_summary": gto_summary,
    }


def _enrich_decisions_with_gto(session: LiveSession, hand: Dict[str, Any]) -> None:
    """Annotate each decision_point in ``hand`` with cached GTO advice.

    Runs once per hand at hand completion. Each decision gets a
    ``decision["gto"]`` field that is either a payload dict (cache
    hit + parseable spot) or ``None`` (cache miss / unsupported
    street / corrupt data). The advisor never raises — at worst
    every decision is annotated ``None``, which the UI renders as
    "no GTO data".
    """
    decisions = hand.get("decision_points")
    if not isinstance(decisions, list):
        return

    big_blind = 1
    try:
        big_blind = int(getattr(session.engine, "big_blind", 1) or 1)
    except Exception:
        big_blind = 1

    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        # Skip if already annotated (idempotent for replay re-renders).
        if "gto" in decision:
            continue
        try:
            decision["gto"] = gto_advisor.gto_advice(decision, big_blind=big_blind)
        except Exception:
            decision["gto"] = None


def _prepare_last_hand(session: LiveSession, hand: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(hand, dict):
        return None
    hand.setdefault("session_id", session.id)
    _enrich_decisions_with_gto(session, hand)
    hand["coach_notes"] = _build_coach_notes(session, hand)
    return hand


def _serialize_hud(session: LiveSession) -> Dict[str, Any]:
    raw_stats: Dict[str, Dict[str, Any]] = {}
    stats_fn = getattr(session.engine, "_get_opponent_stats_for_hud", None)
    if callable(stats_fn):
        try:
            raw_stats = stats_fn() or {}
        except Exception:
            raw_stats = {}

    opponents: List[Dict[str, Any]] = []
    seen = set()
    for name, stats in raw_stats.items():
        if not isinstance(stats, dict):
            continue
        raw_af = stats.get("aggression_factor", stats.get("af"))
        try:
            af_value = float(raw_af)
        except (TypeError, ValueError):
            af_value = 0.0
        af = 99.0 if math.isinf(af_value) else _safe_float(af_value, 0.0)
        opponents.append(
            {
                "name": str(name),
                "hands": int(_safe_float(stats.get("hands"), 0.0)),
                "vpip": _safe_float(stats.get("vpip"), 0.0),
                "pfr": _safe_float(stats.get("pfr"), 0.0),
                "aggression_factor": af,
                "type": str(stats.get("type") or "unknown"),
            }
        )
        seen.add(str(name))

    if session.engine.table:
        try:
            table_players = session.engine.table.get_players_in_order()
        except Exception:
            table_players = []
        hero_name = session.engine.human_player.name
        for player in table_players:
            name = str(getattr(player, "name", ""))
            if not name or name == hero_name or name in seen:
                continue
            opponents.append(
                {
                    "name": name,
                    "hands": int(getattr(player, "hands_played", 0) or 0),
                    "vpip": 0.0,
                    "pfr": 0.0,
                    "aggression_factor": 0.0,
                    "type": "unknown",
                }
            )

    return {"opponents": opponents}


def _current_betting_round(session: LiveSession) -> str:
    round_value = getattr(session.engine, "current_betting_round", None)
    if round_value is not None:
        return str(getattr(round_value, "value", round_value))
    return str(getattr(getattr(session.engine, "game_state", None), "value", "unknown"))


def _players_in_hand(session: LiveSession) -> int:
    if not session.engine.table:
        return 2
    try:
        return len(
            [
                player
                for player in session.engine.table.get_players_in_order()
                if not getattr(player, "folded", False)
            ]
        )
    except Exception:
        return 2


def _find_current_aggressor(session: LiveSession, betting_round: str) -> Optional[str]:
    try:
        hand = session.engine.session_tracker.hand_history[-1]
        actions = list(hand.get("actions") or [])
    except Exception:
        actions = []

    hero_name = session.engine.human_player.name
    for entry in reversed(actions):
        if not isinstance(entry, dict):
            continue
        if entry.get("betting_round") != betting_round:
            continue
        if not (entry.get("did_raise") or entry.get("is_aggressive_intent")):
            continue
        name = entry.get("player")
        if name and name != hero_name:
            return str(name)

    if betting_round == "preflop" and session.engine.table is not None:
        try:
            return str(session.engine.table.get_big_blind_player().name)
        except Exception:
            return None
    return None


def _opponent_for_coach(session: LiveSession, aggressor_name: Optional[str]) -> Dict[str, Any]:
    hud = _serialize_hud(session)
    opponents = hud.get("opponents") if isinstance(hud, dict) else []
    if not isinstance(opponents, list):
        opponents = []

    selected = None
    if aggressor_name:
        selected = next(
            (
                opponent
                for opponent in opponents
                if isinstance(opponent, dict) and opponent.get("name") == aggressor_name
            ),
            None,
        )
    if selected is None:
        selected = next((opponent for opponent in opponents if isinstance(opponent, dict)), None)

    if not isinstance(selected, dict):
        return {
            "name": aggressor_name,
            "type": "unknown",
            "hands": 0,
            "vpip": 0.0,
            "pfr": 0.0,
            "aggression_factor": 0.0,
        }

    return {
        "name": selected.get("name"),
        "type": selected.get("type") or "unknown",
        "hands": int(_safe_float(selected.get("hands"), 0.0)),
        "vpip": _safe_float(selected.get("vpip"), 0.0),
        "pfr": _safe_float(selected.get("pfr"), 0.0),
        "aggression_factor": _safe_float(selected.get("aggression_factor"), 0.0),
    }


def _coach_history_signals(session: LiveSession, preferred_focus: Optional[str]) -> List[str]:
    manager = session.engine.data_manager or DataManager(data_file=str(get_data_file()))
    try:
        record = manager.get_player(session.player_name) if manager else None
    except Exception:
        record = None
    if not isinstance(record, dict):
        return []

    signals: List[str] = []
    weaknesses = record.get("weaknesses")
    if isinstance(weaknesses, list):
        for weakness in weaknesses[:3]:
            signals.append(f"Profile leak: {str(weakness).replace('_', ' ')}")

    progress = record.get("training_progress")
    weakness_history = progress.get("weakness_history") if isinstance(progress, dict) else {}
    if isinstance(weakness_history, dict):
        focus_items = []
        if preferred_focus:
            focus_items.append(preferred_focus)
        focus_items.extend(key for key in weakness_history.keys() if key not in focus_items)

        for focus in focus_items[:3]:
            item = weakness_history.get(focus)
            if not isinstance(item, dict):
                continue
            attempts = int(_safe_float(item.get("attempts"), 0.0))
            accuracy = _safe_float(item.get("accuracy"), -1.0)
            if attempts <= 0 or accuracy < 0:
                continue
            signals.append(
                f"{str(focus).replace('_', ' ')} drills: {accuracy * 100:.0f}% over {attempts} attempt(s)"
            )

    return signals[:5]


def _legal_action_available(pending: Dict[str, Any], action: str) -> bool:
    options = pending.get("options") if isinstance(pending, dict) else None
    if not isinstance(options, list) or not options:
        return True
    target = action.replace("_", " ")
    return any(target in str(option).lower() for option in options)


def _normalize_recommendation(
    *,
    recommendation: str,
    pending: Dict[str, Any],
    can_check: bool,
    call_amount: int,
) -> str:
    recommended = (recommendation or "check").strip().lower()
    # Strict dominance: when checking is free, fold is never the best
    # action. Earlier versions of the coach would happily return
    # "fold" in spots where ``can_check`` was true; replace those with
    # "check" before any downstream rendering.
    if recommended == "fold" and can_check:
        recommended = "check"
    if recommended == "mixed":
        recommended = "call" if call_amount > 0 else "check"
    if recommended == "call" and call_amount <= 0:
        recommended = "check" if can_check else "fold"
    if recommended == "check" and not can_check:
        recommended = "call" if call_amount > 0 else "fold"
    if recommended == "raise" and not _legal_action_available(pending, "raise"):
        recommended = "call" if call_amount > 0 else "check"
    if not _legal_action_available(pending, recommended):
        if can_check and _legal_action_available(pending, "check"):
            return "check"
        if call_amount > 0 and _legal_action_available(pending, "call"):
            return "call"
        return "fold"
    return recommended


def _build_live_coach(session: LiveSession, pending: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not pending:
        return None

    context_fn = getattr(session.engine, "_get_action_context", None)
    try:
        context = context_fn(session.engine.human_player) if callable(context_fn) else {}
    except Exception:
        context = {}

    current_bet = int(_safe_float(context.get("current_bet"), 0.0))
    pot_total = int(_safe_float(context.get("pot_total"), 0.0))
    hero_current_bet = int(getattr(session.engine.human_player, "current_bet", 0) or 0)
    call_amount = max(0, current_bet - hero_current_bet)
    can_check = bool(context.get("can_check", call_amount <= 0))
    betting_round = _current_betting_round(session)
    players_in_hand = _players_in_hand(session)

    hole_cards = list(getattr(session.engine.human_player, "hole_cards", []) or [])
    community_cards = list(getattr(session.engine, "community_cards", []) or [])
    features_fn = getattr(session.engine, "_compute_equity_and_outs", None)
    if callable(features_fn):
        try:
            features = features_fn(
                hole_cards=hole_cards,
                community_cards=community_cards,
                players_in_hand=players_in_hand or 2,
            )
        except Exception:
            features = {}
    else:
        features = {}

    equity = _safe_float(features.get("equity_estimate"), 0.0)
    hand_strength = _safe_float(features.get("hand_strength"), 0.0)
    hand_potential = _safe_float(features.get("hand_potential"), 0.0)
    required_equity = call_amount / (pot_total + call_amount) if call_amount > 0 and pot_total >= 0 else None
    equity_edge = equity - required_equity if required_equity is not None and equity > 0 else None

    aggressor_name = _find_current_aggressor(session, betting_round)
    opponent = _opponent_for_coach(session, aggressor_name)

    recommended = "check" if can_check else "fold"
    confidence = 0.55
    rationale: List[str] = []
    warnings: List[str] = []

    if betting_round == "preflop":
        analyzer_fn = getattr(session.engine, "_get_game_analyzer", None)
        analysis: Dict[str, Any] = {}
        if callable(analyzer_fn) and len(hole_cards) == 2:
            try:
                analyzer = analyzer_fn()
                if analyzer is not None:
                    analysis = analyzer.analyze_preflop_action(
                        {
                            "position": int(getattr(session.engine.human_player, "position", 0) or 0),
                            "hole_cards": hole_cards,
                            "action": "call" if call_amount > 0 else "check",
                            "amount": int(call_amount),
                            "pot_size_before": int(pot_total),
                            "players_in_hand": int(players_in_hand or 2),
                        }
                    ) or {}
            except Exception:
                analysis = {}
        recommended = str(analysis.get("recommended_action") or recommended)
        adjusted_strength = _safe_float(analysis.get("adjusted_strength"), hand_strength)
        confidence = max(0.55, min(0.9, 0.55 + abs(adjusted_strength - 0.55)))
        rationale.append(f"Preflop strength model rates this hand at {adjusted_strength * 100:.0f}%.")
        if call_amount > 0 and required_equity is not None:
            rationale.append(f"Calling needs {required_equity * 100:.1f}% equity before future action.")
    elif call_amount > 0 and required_equity is not None:
        if equity <= 0:
            recommended = "fold"
            confidence = 0.56
            warnings.append("Equity estimate is unavailable; this advice is conservative.")
        else:
            edge = equity - required_equity
            if abs(edge) < 0.02:
                recommended = "call"
                confidence = 0.58
                warnings.append("This is a thin price; small range changes can flip the answer.")
            else:
                recommended = "call" if edge > 0 else "fold"
                confidence = max(0.6, min(0.92, 0.58 + abs(edge) * 2.0))
            rationale.append(
                f"Equity is {equity * 100:.1f}% versus {required_equity * 100:.1f}% required."
            )
    else:
        if equity >= 0.75 and bool(context.get("raise_allowed", True)):
            recommended = "raise"
            confidence = 0.76
            rationale.append("Strong made-hand estimate favors value betting.")
        elif equity <= 0.30 and hand_potential < 0.2:
            recommended = "check"
            confidence = 0.68
            rationale.append("Low equity and low draw potential favor pot control.")
        else:
            recommended = "check"
            confidence = 0.6
            rationale.append("No bet is required, so keep the pot controlled by default.")

    recommended = _normalize_recommendation(
        recommendation=recommended,
        pending=pending,
        can_check=can_check,
        call_amount=call_amount,
    )

    effective_stack = int(getattr(session.engine.human_player, "bankroll", 0) or 0)
    spr = (effective_stack / pot_total) if pot_total > 0 else None
    if spr is not None and spr < 2:
        warnings.append("Low SPR: stack-off thresholds are wider than in deep-stack spots.")
    if int(opponent.get("hands") or 0) < 10:
        warnings.append("Opponent history sample is small.")

    preferred_focus = "poor_pot_odds" if call_amount > 0 else ("poor_position_play" if betting_round == "preflop" else None)
    history_signals = _coach_history_signals(session, preferred_focus)
    if not rationale:
        rationale.append("Recommendation uses the current legal action, stack, board, and tracked history.")

    if recommended == "call" and equity_edge is not None:
        summary = f"Call: equity edge is {equity_edge * 100:+.1f} points."
    elif recommended == "fold" and equity_edge is not None:
        summary = f"Fold: price is short by {abs(equity_edge) * 100:.1f} equity points."
    elif recommended == "raise":
        summary = "Raise: current model favors applying pressure or value betting."
    else:
        summary = "Check: no immediate price forces more chips into the pot."

    training_link = None
    if preferred_focus:
        training_link = f"/training/drill?focus={preferred_focus}"

    return {
        "recommended_action": recommended,
        "confidence": round(confidence, 3),
        "summary": summary,
        "math": {
            "pot": pot_total,
            "to_call": call_amount,
            "pot_odds": round(required_equity, 4) if required_equity is not None else None,
            "required_equity": round(required_equity, 4) if required_equity is not None else None,
            "estimated_equity": round(equity, 4) if equity > 0 else None,
            "equity_edge": round(equity_edge, 4) if equity_edge is not None else None,
            "hand_strength": round(hand_strength, 4),
            "hand_potential": round(hand_potential, 4),
            "outs": features.get("outs", {}) if isinstance(features.get("outs"), dict) else {},
            "spr": round(spr, 2) if spr is not None else None,
            "effective_stack": effective_stack,
        },
        "opponent": opponent,
        "rationale": rationale[:5],
        "warnings": warnings[:4],
        "history_signals": history_signals,
        "training_link": training_link,
    }


def _live_coach_cache_key(session: LiveSession, pending: Dict[str, Any]) -> str:
    """Return a stable key for every deterministic input the live coach reads."""
    context_fn = getattr(session.engine, "_get_action_context", None)
    try:
        context = context_fn(session.engine.human_player) if callable(context_fn) else {}
    except Exception:
        context = {}

    players: List[Dict[str, Any]] = []
    try:
        table_players = session.engine.table.get_players_in_order()
    except Exception:
        table_players = []

    for player in table_players:
        players.append(
            {
                "name": str(getattr(player, "name", "")),
                "bankroll": int(_safe_float(getattr(player, "bankroll", 0), 0.0)),
                "current_bet": int(_safe_float(getattr(player, "current_bet", 0), 0.0)),
                "folded": bool(getattr(player, "folded", False)),
                "all_in": bool(getattr(player, "all_in", False)),
                "position": int(_safe_float(getattr(player, "position", 0), 0.0)),
            }
        )

    hand_history = getattr(session.engine.session_tracker, "hand_history", []) or []
    last_hand = hand_history[-1] if hand_history else {}
    hero = session.engine.human_player
    payload = {
        "session_id": session.id,
        "status": session.status,
        "game_state": getattr(getattr(session.engine, "game_state", None), "value", None),
        "betting_round": _current_betting_round(session),
        "pending": pending,
        "context": {
            "current_bet": int(_safe_float(context.get("current_bet"), 0.0)),
            "min_raise": int(_safe_float(context.get("min_raise"), 0.0)),
            "can_check": bool(context.get("can_check", False)),
            "pot_total": int(_safe_float(context.get("pot_total"), 0.0)),
            "raise_allowed": bool(context.get("raise_allowed", True)),
            "limit_bet_size": context.get("limit_bet_size"),
        },
        "hero": {
            "bankroll": int(_safe_float(getattr(hero, "bankroll", 0), 0.0)),
            "current_bet": int(_safe_float(getattr(hero, "current_bet", 0), 0.0)),
            "hole_cards": [str(card) for card in (getattr(hero, "hole_cards", []) or [])],
        },
        "board": [str(card) for card in (getattr(session.engine, "community_cards", []) or [])],
        "players": players,
        "hand_history_count": len(hand_history),
        "last_hand_number": last_hand.get("hand_number") if isinstance(last_hand, dict) else None,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _cached_live_coach(session: LiveSession, pending: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not pending:
        session._coach_cache_key = None
        session._coach_cache_val = None
        return None

    cache_key = _live_coach_cache_key(session, pending)
    if cache_key == session._coach_cache_key:
        return session._coach_cache_val

    coach = _build_live_coach(session, pending)
    session._coach_cache_key = cache_key
    session._coach_cache_val = coach
    return coach


def _serialize_state(session: LiveSession) -> Dict[str, Any]:
    state = session.engine.get_game_state()
    state["hero_cards"] = [str(card) for card in session.engine.human_player.hole_cards]
    state["hero_name"] = session.engine.human_player.name
    state["hero_bankroll"] = int(session.engine.human_player.bankroll)
    state["game_over_reason"] = session.terminal_reason or state.get("game_over_reason")
    state["hud"] = _serialize_hud(session)
    if session.engine.session_tracker.hand_history:
        last_hand = session.engine.session_tracker.hand_history[-1]
        state["hand_number"] = last_hand.get("hand_number")
    return state


def _session_metrics_snapshot(session: LiveSession, status: str) -> Dict[str, Any]:
    tracker = session.engine.session_tracker
    metrics = getattr(tracker, "metrics", None)
    if metrics is None:
        return {
            "id": session.id,
            "player_name": session.player_name,
            "game_type": session.game_type,
            "limit_type": session.limit_type,
            "status": status,
            "hands_played": 0,
        }

    metrics.bankroll_end = int(session.engine.human_player.bankroll)
    snapshot = metrics.to_dict()
    snapshot.update(
        {
            "id": session.id,
            "player_name": session.player_name,
            "game_type": session.game_type,
            "limit_type": session.limit_type,
            "status": status,
            "config": session.config,
        }
    )
    if session.last_hand:
        snapshot["last_hand_number"] = session.last_hand.get("hand_number")
    return snapshot


def _persist_session_snapshot(session: LiveSession, status: str) -> None:
    manager = session.engine.data_manager
    if not manager:
        return

    try:
        manager.update_session(session.id, _session_metrics_snapshot(session, status))
    except Exception:
        return


def _build_hand_response(session: LiveSession) -> Dict[str, Any]:
    with session.lock:
        session.status = _derive_status(session)
        engine_state = getattr(getattr(session.engine, "game_state", None), "value", None)
        if (
            not session.last_hand
            and engine_state == "hand_complete"
            and session.engine.session_tracker.hand_history
        ):
            session.last_hand = session.engine.session_tracker.hand_history[-1]
        if session.last_hand:
            session.last_hand = _prepare_last_hand(session, session.last_hand)
        pending = session.input_handler.pending_request()
        session.touch()
        response = {
            "session_id": session.id,
            "status": session.status,
            "state": _serialize_state(session),
            "pending_input": pending,
            "live_coach": _cached_live_coach(session, pending),
            "input_error": session.input_handler.last_error(),
            "last_hand": session.last_hand,
            "terminal_reason": session.terminal_reason,
            "error": session.last_error,
        }
        should_flush_complete = session.status in {"hand_complete", "game_over", "tournament_complete"}

    if should_flush_complete:
        _persist_session_snapshot(session, response["status"])
        session.flush_snapshot("hand_response_complete")

    return response


def start_hand(session_id: str) -> Dict[str, Any]:
    session = _get_live_session_or_restore(session_id)
    if not session:
        raise KeyError("Session not found")

    with session.lock:
        if _refresh_terminal_state(session):
            session.touch()
            session.flush_snapshot("terminal_start_rejected")
            return _build_hand_response(session)

    if session.thread and session.thread.is_alive():
        _wait_for_update(session)
        return _build_hand_response(session)

    with session.lock:
        session.last_hand = None
        session.last_error = None
        session.input_handler.clear_pending()
        session.status = "in_hand"
        session.touch()
        session.schedule_snapshot("hand_start", sync=True)

    def run_hand() -> None:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                session.engine.play_hand()
            if session.engine.session_tracker.hand_history:
                with session.lock:
                    session.last_hand = _prepare_last_hand(
                        session, session.engine.session_tracker.hand_history[-1]
                    )

            if not session.engine.tournament_mode and session.engine.data_manager:
                session.engine.data_manager.save_player(session.engine.human_player)
            with session.lock:
                _refresh_terminal_state(session)
                session.status = _derive_status(session)
                session.touch()
                persisted_status = session.status
            _persist_session_snapshot(session, persisted_status)
            session.flush_snapshot("hand_thread_complete")
        except Exception as exc:
            with session.lock:
                session.last_error = str(exc)
            _persist_session_snapshot(session, "error")
            session.flush_snapshot("hand_thread_error")
        finally:
            with session.lock:
                _refresh_terminal_state(session)
                session.status = _derive_status(session)
                session.touch()
            session.flush_snapshot("hand_thread_finally")

    session.thread = threading.Thread(target=run_hand, daemon=True)
    session.thread.start()

    _wait_for_update(session)
    return _build_hand_response(session)


def _start_resume_thread(session: LiveSession) -> None:
    if session.thread and session.thread.is_alive():
        return

    with session.lock:
        session.status = "in_hand"
        session.engine._restored_pending_continuation = False
        session.engine._resume_started = True
        session.touch()
        session.schedule_snapshot("resume_thread_start", sync=True)

    def run_resume() -> None:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                session.engine.resume_hand()
            if session.engine.session_tracker.hand_history:
                with session.lock:
                    session.last_hand = _prepare_last_hand(
                        session, session.engine.session_tracker.hand_history[-1]
                    )
            if not session.engine.tournament_mode and session.engine.data_manager:
                session.engine.data_manager.save_player(session.engine.human_player)
            with session.lock:
                _refresh_terminal_state(session)
                session.status = _derive_status(session)
                session.touch()
                persisted_status = session.status
            _persist_session_snapshot(session, persisted_status)
            session.flush_snapshot("resume_thread_complete")
        except Exception as exc:
            with session.lock:
                session.last_error = str(exc)
            _persist_session_snapshot(session, "error")
            session.flush_snapshot("resume_thread_error")
        finally:
            with session.lock:
                _refresh_terminal_state(session)
                session.status = _derive_status(session)
                session.touch()
            session.flush_snapshot("resume_thread_finally")

    session.thread = threading.Thread(target=run_resume, daemon=True)
    session.thread.start()
    _wait_for_update(session)


def get_hand_state(session_id: str) -> Dict[str, Any]:
    session = _get_live_session_or_restore(session_id)
    if not session:
        raise KeyError("Session not found")
    return _build_hand_response(session)


def _coerce_input_value(value: Any, request: Dict[str, Any]) -> Any:
    kind = request.get("kind")
    if kind == "menu":
        total = int(request.get("max_value") or 0)
        parsed = _parse_number(value)
        if not parsed.is_integer():
            raise ValueError("Choice must be an integer.")
        choice = int(parsed)
        if choice < 1 or choice > total:
            raise ValueError(f"Choice must be between 1 and {total}.")
        return choice
    if kind == "number":
        parsed = _parse_number(value)
        min_value = request.get("min_value")
        max_value = request.get("max_value")
        if request.get("integer_only") and not parsed.is_integer():
            raise ValueError("Enter a whole number.")
        if min_value is not None and parsed < float(min_value):
            raise ValueError("Value is below the minimum.")
        if max_value is not None and parsed > float(max_value):
            raise ValueError("Value is above the maximum.")
        return parsed
    if kind == "yes_no":
        return _parse_bool(value)
    raise ValueError("Unknown input request.")


def submit_input(session_id: str, value: Any) -> Dict[str, Any]:
    session = _get_live_session_or_restore(session_id)
    if not session:
        raise KeyError("Session not found")

    pending = session.input_handler.pending_request()
    if not pending:
        if session.thread and session.thread.is_alive():
            _wait_for_update(session, timeout=0.5)
            pending = session.input_handler.pending_request()
        if not pending:
            engine_state = getattr(getattr(session.engine, "game_state", None), "value", None)
            if session.thread and session.thread.is_alive():
                return _build_hand_response(session)
            if session.last_hand or session.status == "hand_complete" or engine_state == "hand_complete":
                return _build_hand_response(session)
            raise RuntimeError("No input is pending")

    coerced = _coerce_input_value(value, pending)
    prior_input_version = session.input_handler.version()
    session.input_handler.submit(coerced)
    with session.lock:
        session.touch()

    if (not session.thread or not session.thread.is_alive()) and getattr(session.engine, "_restored_pending_continuation", False):
        _start_resume_thread(session)
    else:
        _wait_for_input_progress(session, prior_input_version)
    return _build_hand_response(session)


def simulate_hand(session_id: str) -> Dict[str, Any]:
    session = _get_live_session_or_restore(session_id)
    if not session:
        raise KeyError("Session not found")
    auto_handler = AutoInputHandler()
    engine = session.engine
    previous_handler = engine.input_handler
    engine.input_handler = auto_handler
    engine._test_mode = True

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            engine.play_hand()
        if engine.session_tracker.hand_history:
            with session.lock:
                session.last_hand = _prepare_last_hand(session, engine.session_tracker.hand_history[-1])

        if not engine.tournament_mode and engine.data_manager:
            engine.data_manager.save_player(engine.human_player)
        with session.lock:
            _refresh_terminal_state(session)
            session.status = _derive_status(session)
            session.touch()
            persisted_status = session.status
        _persist_session_snapshot(session, persisted_status)
    finally:
        engine.input_handler = previous_handler
        with session.lock:
            _refresh_terminal_state(session)
            session.status = _derive_status(session)
            session.touch()

    return _build_hand_response(session)


def list_saved_sessions(player_name: Optional[str] = None, state: str = "active") -> List[Dict[str, Any]]:
    manager = DataManager(data_file=str(get_data_file()))
    player = player_name or "Guest"
    records = manager.get_sessions(player, limit=100)
    rows: List[Dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        snapshot = record.get("live_snapshot") if isinstance(record.get("live_snapshot"), dict) else {}
        deleted = bool(snapshot.get("deleted") or record.get("deleted"))
        status = str(snapshot.get("status") or record.get("status") or "")
        if state == "active" and (deleted or status in {"game_over", "tournament_complete", "deleted"}):
            continue
        if state == "deleted" and not deleted:
            continue
        rows.append(
            {
                "id": record.get("id"),
                "player_name": record.get("player_name") or player,
                "game_type": record.get("game_type"),
                "limit_type": record.get("limit_type"),
                "status": status or record.get("status"),
                "terminal_reason": snapshot.get("terminal_reason") or record.get("terminal_reason"),
                "updated_at": snapshot.get("updated_at") or record.get("updated_at"),
                "hands_played": record.get("hands_played") or (snapshot.get("engine", {}).get("tracker", {}).get("metrics", {}) or {}).get("hands_played", 0),
                "last_hand": snapshot.get("last_hand"),
                "hero_stack": (snapshot.get("engine", {}) or {}).get("table", {}).get("players", [{}])[0].get("bankroll")
                if isinstance((snapshot.get("engine", {}) or {}).get("table", {}).get("players"), list)
                and (snapshot.get("engine", {}) or {}).get("table", {}).get("players")
                else None,
            }
        )
    rows.sort(key=lambda row: row.get("updated_at") or 0, reverse=True)
    return rows


def pause_session(session_id: str) -> Dict[str, Any]:
    session = _get_live_session_or_restore(session_id)
    if not session:
        raise KeyError("Session not found")
    with session.lock:
        if session.thread and session.thread.is_alive() and session.input_handler.pending_request() is None:
            raise RuntimeError("Session can only be paused while waiting for input or between hands.")
        session.status = "paused"
        session.touch()
    session.flush_snapshot("pause")
    return session.public_dict()


def resume_session(session_id: str) -> Dict[str, Any]:
    session = _get_live_session_or_restore(session_id)
    if not session:
        raise KeyError("Session not found")
    with session.lock:
        if session.status == "paused":
            session.status = _derive_status(session)
            session.touch()
    session.flush_snapshot("resume")
    return _build_hand_response(session)


def delete_session(session_id: str) -> Dict[str, Any]:
    session = _get_live_session_or_restore(session_id)
    manager = DataManager(data_file=str(get_data_file()))
    if session:
        with session.lock:
            session._snapshot_deleted = True
            session.status = "deleted"
            snapshot = _build_live_snapshot(session, "delete")
            snapshot["deleted"] = True
        manager.update_session(
            session.id,
            {
                "id": session.id,
                "player_name": session.player_name,
                "status": "deleted",
                "deleted": True,
                "live_snapshot": snapshot,
                "updated_at": time.time(),
            },
        )
        with SESSIONS_LOCK:
            SESSIONS.pop(session.id, None)
        return {"id": session_id, "status": "deleted"}

    record = getattr(manager, "get_session_by_id", lambda _id: None)(session_id)
    if not isinstance(record, dict):
        raise KeyError("Session not found")
    snapshot = record.get("live_snapshot") if isinstance(record.get("live_snapshot"), dict) else {}
    snapshot = dict(snapshot)
    snapshot["deleted"] = True
    manager.update_session(
        session_id,
        {
            "id": session_id,
            "player_name": record.get("player_name") or "Guest",
            "status": "deleted",
            "deleted": True,
            "live_snapshot": snapshot,
            "updated_at": time.time(),
        },
    )
    return {"id": session_id, "status": "deleted"}
