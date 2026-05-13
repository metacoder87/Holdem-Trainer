"""WebSocket endpoints for live session updates.

The HTTP `start_hand`/`hand/input` flow already drives the engine; this
WebSocket simply pushes state snapshots whenever the engine signals an
update_event. It does *not* replace the HTTP endpoints because the engine
relies on blocking input prompts via the thread/queue bridge.

Clients can either:
- send the same payloads they would POST (`{"action": "start"}`, `{"action": "input", "value": ...}`)
- or just `await` for state pushes (read-only mirror).
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.game_service import (
    SESSIONS,
    _build_hand_response,
    start_hand,
    submit_input,
)

router = APIRouter()


@router.websocket("/ws/sessions/{session_id}")
async def session_stream(websocket: WebSocket, session_id: str) -> None:
    session = SESSIONS.get(session_id)
    if not session:
        await websocket.close(code=4404)
        return

    await websocket.accept()

    # Initial snapshot.
    await websocket.send_json(_build_hand_response(session))

    async def push_updates() -> None:
        """Broadcast state every time the engine wakes us."""
        loop = asyncio.get_running_loop()
        while True:
            # Engine wakes the event from a worker thread; bridge to async.
            await loop.run_in_executor(None, session.update_event.wait, 1.0)
            if session.update_event.is_set():
                session.update_event.clear()
                try:
                    await websocket.send_json(_build_hand_response(session))
                except Exception:
                    return
            if session.tournament_finalized:
                # One final flush; loop continues so further commands work.
                await asyncio.sleep(0.1)

    push_task = asyncio.create_task(push_updates())

    try:
        while True:
            try:
                payload = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except Exception:
                continue

            action = (payload or {}).get("action") if isinstance(payload, dict) else None
            try:
                if action == "start":
                    response = await asyncio.get_running_loop().run_in_executor(
                        None, start_hand, session_id
                    )
                elif action == "input":
                    value = payload.get("value")
                    if value is None:
                        value = payload.get("choice")
                    response = await asyncio.get_running_loop().run_in_executor(
                        None, submit_input, session_id, value
                    )
                elif action == "snapshot":
                    response = _build_hand_response(session)
                else:
                    response = {"error": f"Unknown action: {action!r}"}
            except KeyError:
                response = {"error": "Session not found"}
            except RuntimeError as exc:
                response = {"error": str(exc)}
            except ValueError as exc:
                response = {"error": str(exc)}
            except Exception as exc:  # noqa: BLE001
                response = {"error": str(exc)}

            await websocket.send_json(response)
    finally:
        push_task.cancel()
        try:
            await push_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
