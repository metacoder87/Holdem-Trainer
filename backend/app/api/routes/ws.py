import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.config import settings
from app.services import game_service

router = APIRouter()

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    last_state = None
    try:
        while True:
            try:
                session = game_service._get_live_session(session_id)
                if session:
                    current_response = game_service._build_hand_response(session)
                    current_state_str = json.dumps(current_response, default=str)
                    
                    if current_state_str != last_state:
                         await websocket.send_json(current_response)
                         last_state = current_state_str
                else:
                    await websocket.send_json({"error": "Session not found"})
                    break
                    
            except Exception as exc:
                await websocket.send_json({"error": str(exc)})
            
            await asyncio.sleep(settings.WS_POLL_INTERVAL_SECONDS)
            
    except WebSocketDisconnect:
        return
