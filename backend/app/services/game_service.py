import os
import queue
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.paths import ensure_src_path, get_data_file

ensure_src_path()

from data.manager import DataManager
from game.game_engine import GameEngine
from game.player import Player


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
        self._wake_event: Optional[threading.Event] = None

    def attach_event(self, event: threading.Event) -> None:
        self._wake_event = event

    def submit(self, value: Any) -> None:
        self._queue.put(value)

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

    def _set_error(self, message: str) -> None:
        with self._lock:
            self._last_error = message

    def _set_pending(self, request: InputRequest) -> None:
        with self._lock:
            self._pending = request
            self._last_error = None
        if self._wake_event is not None:
            self._wake_event.set()

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
    tournament_finalized: bool = False
    tournament_result: Optional[Dict[str, Any]] = None
    update_event: threading.Event = field(default_factory=threading.Event)
    last_touched: float = field(default_factory=lambda: time.time())

    def public_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "player_name": self.player_name,
            "game_type": self.game_type,
            "limit_type": self.limit_type,
            "status": self.status,
            "config": self.config,
        }


_SESSION_LIMIT = int(os.getenv("PYHOLDEM_SESSION_LIMIT", "64") or "64")
_SESSION_TTL_SECONDS = float(os.getenv("PYHOLDEM_SESSION_TTL_SECONDS", "3600") or "3600")


class _SessionStore:
    """Thread-safe LRU+TTL session registry.

    Behaves like a dict for the existing code paths (clear, in, [], get, item
    assignment) but evicts the least-recently-touched session when the soft
    limit is exceeded and prunes sessions older than the TTL on read.
    """

    def __init__(self, *, limit: int, ttl_seconds: float):
        self._limit = max(1, int(limit))
        self._ttl = float(ttl_seconds)
        self._lock = threading.Lock()
        self._sessions: "OrderedDict[str, LiveSession]" = OrderedDict()

    def _expired(self, session: LiveSession, now: float) -> bool:
        if self._ttl <= 0:
            return False
        thread = session.thread
        if thread and thread.is_alive():
            return False
        return (now - session.last_touched) > self._ttl

    def _prune(self) -> None:
        now = time.time()
        for session_id in [sid for sid, s in self._sessions.items() if self._expired(s, now)]:
            self._sessions.pop(session_id, None)
        while len(self._sessions) > self._limit:
            self._sessions.popitem(last=False)

    def __setitem__(self, session_id: str, session: LiveSession) -> None:
        with self._lock:
            session.last_touched = time.time()
            self._sessions[session_id] = session
            self._sessions.move_to_end(session_id)
            self._prune()

    def __getitem__(self, session_id: str) -> LiveSession:
        with self._lock:
            self._prune()
            session = self._sessions[session_id]
            session.last_touched = time.time()
            self._sessions.move_to_end(session_id)
            return session

    def get(self, session_id: str) -> Optional[LiveSession]:
        with self._lock:
            self._prune()
            session = self._sessions.get(session_id)
            if session is not None:
                session.last_touched = time.time()
                self._sessions.move_to_end(session_id)
            return session

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()

    def __contains__(self, session_id: object) -> bool:
        with self._lock:
            return session_id in self._sessions

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)


SESSIONS = _SessionStore(limit=_SESSION_LIMIT, ttl_seconds=_SESSION_TTL_SECONDS)


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
            manager.save_players()
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
    session = LiveSession(
        id=session_id,
        player_name=player_name,
        game_type=game_type,
        limit_type=limit_type,
        config=config,
        engine=engine,
        input_handler=api_input,
    )
    api_input.attach_event(session.update_event)
    return session


def create_session(payload: Dict[str, Any]) -> Dict[str, Any]:
    player_name = payload.get("player_name") or "Guest"
    game_type = payload.get("game_type") or "cash"
    limit_type = payload.get("limit_type") or "no_limit"

    session = _build_engine(
        player_name=player_name,
        game_type=game_type,
        limit_type=limit_type,
        config=payload,
    )
    SESSIONS[session.id] = session
    return session.public_dict()


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    session = SESSIONS.get(session_id)
    return session.public_dict() if session else None


def _get_live_session(session_id: str) -> Optional[LiveSession]:
    return SESSIONS.get(session_id)


def _derive_status(session: LiveSession) -> str:
    if session.last_error:
        return "error"
    if session.input_handler.pending_request():
        return "awaiting_input"
    if session.thread and session.thread.is_alive():
        return "in_hand"
    if session.tournament_finalized:
        return "tournament_complete"
    if session.last_hand:
        return "hand_complete"
    return "idle"


def _wait_for_update(session: LiveSession, timeout: float = 1.0) -> None:
    """Block until the engine surfaces new state or the worker thread exits.

    Wakes on either ApiInputHandler._set_pending (via the attached Event) or the
    background thread completing. Caller should clear the event before
    triggering a state change so the next call doesn't see the previous wake.
    """
    session.update_event.wait(timeout=timeout)
    session.update_event.clear()


def _serialize_state(session: LiveSession) -> Dict[str, Any]:
    state = session.engine.get_game_state()
    engine = session.engine
    state["hero_cards"] = [str(card) for card in engine.human_player.hole_cards]
    state["hero_name"] = engine.human_player.name
    state["hero_bankroll"] = int(engine.human_player.bankroll)
    if engine.session_tracker.hand_history:
        last_hand = engine.session_tracker.hand_history[-1]
        state["hand_number"] = last_hand.get("hand_number")

    # HUD payload - opponent VPIP/PFR/AF/type so the UI doesn't have to compute
    # it client-side. Cheap (already cached structure on the engine) and
    # frontends that don't care about HUD can ignore the field.
    try:
        opponents = engine._get_opponent_stats_for_hud() or {}
    except Exception:
        opponents = {}
    if opponents:
        state["hud"] = {
            "opponents": [
                {
                    "name": name,
                    "hands": int(stats.get("hands", 0)),
                    "vpip": float(stats.get("vpip", 0.0) or 0.0),
                    "pfr": float(stats.get("pfr", 0.0) or 0.0),
                    "aggression_factor": (
                        99.9
                        if stats.get("af") in (float("inf"), None)
                        else float(stats.get("af", 0.0) or 0.0)
                    ),
                    "type": stats.get("type", "unknown"),
                }
                for name, stats in opponents.items()
            ]
        }
    return state


def _maybe_finalize_tournament(session: LiveSession) -> None:
    """Settle a tournament when it reaches a terminal state.

    Without this, run_game_loop's settlement path is never invoked through the
    REST flow (we drive play_hand by hand), so chip-stack -> cash conversion
    and payout would never occur and the buy-in would be lost permanently.
    """
    engine = session.engine
    if not engine.tournament_mode or session.tournament_finalized:
        return
    if engine.table is None:
        return

    try:
        active = engine.table.get_players_in_tournament()
    except Exception:
        return

    hero = engine.human_player
    hero_eliminated = hero not in active
    tournament_over = len(active) <= 1

    if not (hero_eliminated or tournament_over):
        return

    if hero_eliminated:
        result = "lost"
    elif hero in active and len(active) == 1:
        result = "won"
    else:
        result = "lost"

    pre_finalize_bankroll = int(hero.bankroll)
    try:
        engine._finalize_tournament(result)
    except Exception as exc:  # noqa: BLE001
        session.last_error = f"Tournament settlement failed: {exc}"
        return

    session.tournament_finalized = True
    session.tournament_result = {
        "result": result,
        "final_bankroll": int(hero.bankroll),
        "chip_stack_at_end": pre_finalize_bankroll,
    }


def _build_hand_response(session: LiveSession) -> Dict[str, Any]:
    _maybe_finalize_tournament(session)
    session.status = _derive_status(session)
    response: Dict[str, Any] = {
        "session_id": session.id,
        "status": session.status,
        "state": _serialize_state(session),
        "pending_input": session.input_handler.pending_request(),
        "input_error": session.input_handler.last_error(),
        "last_hand": session.last_hand,
        "error": session.last_error,
    }
    if session.tournament_result is not None:
        response["tournament_result"] = session.tournament_result
    return response


def start_hand(session_id: str) -> Dict[str, Any]:
    session = _get_live_session(session_id)
    if not session:
        raise KeyError("Session not found")

    if session.tournament_finalized:
        return _build_hand_response(session)

    if session.thread and session.thread.is_alive():
        _wait_for_update(session)
        return _build_hand_response(session)

    session.last_hand = None
    session.last_error = None
    session.input_handler.clear_pending()
    session.update_event.clear()
    session.status = "in_hand"

    def run_hand() -> None:
        try:
            session.engine.play_hand()
            if session.engine.session_tracker.hand_history:
                session.last_hand = session.engine.session_tracker.hand_history[-1]
            if not session.engine.tournament_mode and session.engine.data_manager:
                session.engine.data_manager.save_player(session.engine.human_player)
        except Exception as exc:
            session.last_error = str(exc)
        finally:
            session.status = _derive_status(session)
            session.update_event.set()

    session.thread = threading.Thread(target=run_hand, daemon=True)
    session.thread.start()

    _wait_for_update(session)
    return _build_hand_response(session)


def get_hand_state(session_id: str) -> Dict[str, Any]:
    session = _get_live_session(session_id)
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
    session = _get_live_session(session_id)
    if not session:
        raise KeyError("Session not found")

    pending = session.input_handler.pending_request()
    if not pending:
        if session.thread and session.thread.is_alive():
            _wait_for_update(session, timeout=0.5)
            pending = session.input_handler.pending_request()
        if not pending:
            if session.last_hand or session.status == "hand_complete":
                return _build_hand_response(session)
            raise RuntimeError("No input is pending")

    coerced = _coerce_input_value(value, pending)
    session.update_event.clear()
    session.input_handler.submit(coerced)

    _wait_for_update(session)
    return _build_hand_response(session)


def simulate_hand(session_id: str) -> Dict[str, Any]:
    session = SESSIONS.get(session_id)
    if not session:
        raise KeyError("Session not found")
    auto_handler = AutoInputHandler()
    engine = session.engine
    previous_handler = engine.input_handler
    engine.input_handler = auto_handler
    engine._test_mode = True

    try:
        engine.play_hand()
        if engine.session_tracker.hand_history:
            session.last_hand = engine.session_tracker.hand_history[-1]
        if not engine.tournament_mode and engine.data_manager:
            engine.data_manager.save_player(engine.human_player)
    finally:
        engine.input_handler = previous_handler

    return _build_hand_response(session)
