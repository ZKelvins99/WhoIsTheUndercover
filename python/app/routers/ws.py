from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws import ws_manager

router = APIRouter(tags=["ws"])


@router.websocket("/ws/rooms/{room_code}")
async def room_ws(websocket: WebSocket, room_code: str):
    await ws_manager.connect(room_code, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(room_code, websocket)
