"""WebSocket session stream.

Pushes a fresh `GameHandState` snapshot whenever the session's status,
pending-input prompt, last-hand, or terminal_reason changes. The HTTP routes
(`start_hand`, `submit_input`) still drive the engine - this endpoint is a
read-mostly mirror that lets clients receive state without polling. Clients
can also send the same actions over the socket:

    { "action": "start" }
    { "action": "input", "value": <int|string|bool> }   (or "choice")
    { "action": "snapshot" }

Errors are returned inline as `{ "error": "..." }`. The socket closes with
code 4404 if the session id is unknown.

NOTE: This route used to reference `session.update_event` and
`session.tournament_finalized` which were never added to `LiveSession`. That
caused the very first push to raise AttributeError and silently kill the
push task. We now poll `_build_hand_response` on a short interval and
broadcast only when the response actually changed - that uses only attrs
LiveSession actually has, and uses the engine's own state machine as the
source of truth.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.services.game_service import (
    SESSIONS,
    SESSIONS_LOCK,
    _build_hand_response,
    start_hand,
    submit_input,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _snapshot_signature(payload: Dict[str, Any]) -> str:
    """Stable representation of the payload so we only push on change."""
    # status + pending_input shape + last_hand_number + terminal_reason are
    # the bits the UI actually cares about; ignore everything else to avoid
    # spamming the socket on irrelevant churn.
    pending = payload.get("pending_input") or {}
    last_hand = payload.get("last_hand") or {}
    state = payload.get("state") or {}
    digest = {
        "status": payload.get("status"),
        "terminal_reason": payload.get("terminal_reason"),
        "pending_kind": pending.get("kind"),
        "pending_prompt": pending.get("prompt"),
        "pending_options": pending.get("options"),
        "last_hand_number": last_hand.get("hand_number"),
        "game_state": state.get("game_state"),
        "pot_size": state.get("pot_size"),
        "hero_bankroll": state.get("hero_bankroll"),
        "error": payload.get("error"),
        "input_error": payload.get("input_error"),
    }
    return json.dumps(digest, sort_keys=True, default=str)


@router.websocket("/ws/sessions/{session_id}")
async def session_stream(websocket: WebSocket, session_id: str) -> None:
    with SESSIONS_LOCK:
        session = SESSIONS.get(session_id)
    if not session:
        await websocket.close(code=4404)
        return

    await websocket.accept()

    loop = asyncio.get_running_loop()

    def snapshot() -> Dict[str, Any]:
        return _build_hand_response(session)

    last_payload = snapshot()
    last_signature = _snapshot_signature(last_payload)
    await websocket.send_json(last_payload)

    poll_interval = max(0.05, float(settings.WS_POLL_INTERVAL_SECONDS))

    async def push_loop() -> None:
        nonlocal last_signature
        try:
            while True:
                await asyncio.sleep(poll_interval)
                # `_build_hand_response` touches the engine but is thread-safe
                # via the session lock; run it on the default executor so we
                # don't block the event loop on `Session.lock` contention.
                payload = await loop.run_in_executor(None, snapshot)
                signature = _snapshot_signature(payload)
                if signature == last_signature:
                    continue
                last_signature = signature
                try:
                    await websocket.send_json(payload)
                except Exception:
                    return
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("WebSocket push loop crashed for %s", session_id)

    push_task = asyncio.create_task(push_loop())

    try:
        while True:
            try:
                payload = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except Exception:
                continue

            action = (payload or {}).get("action") if isinstance(payload, dict) else None
            response: Optional[Dict[str, Any]] = None
            try:
                if action == "start":
                    response = await loop.run_in_executor(None, start_hand, session_id)
                elif action == "input":
                    value = payload.get("value")
                    if value is None:
                        value = payload.get("choice")
                    response = await loop.run_in_executor(
                        None, submit_input, session_id, value
                    )
                elif action == "snapshot":
                    response = snapshot()
                else:
                    response = {"error": f"Unknown action: {action!r}"}
            except KeyError:
                response = {"error": "Session not found"}
            except RuntimeError as exc:
                response = {"error": str(exc)}
            except ValueError as exc:
                response = {"error": str(exc)}
            except Exception as exc:  # noqa: BLE001
                logger.exception("WS action %s failed", action)
                response = {"error": str(exc)}

            if response is not None:
                # Update the signature so the push loop doesn't immediately
                # re-broadcast the same payload we just sent inline.
                last_signature = _snapshot_signature(response)
                try:
                    await websocket.send_json(response)
                except Exception:
                    break
    finally:
        push_task.cancel()
        try:
            await push_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
