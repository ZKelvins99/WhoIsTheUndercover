from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import WebSocket


class WSManager:
    def __init__(self):
        self._rooms: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, room_code: str, ws: WebSocket):
        await ws.accept()
        self._rooms[room_code].append(ws)

    def disconnect(self, room_code: str, ws: WebSocket):
        if room_code not in self._rooms:
            return
        if ws in self._rooms[room_code]:
            self._rooms[room_code].remove(ws)

    async def broadcast(self, room_code: str, event: str, payload: dict[str, Any]):
        body = {
            "event": event,
            "roomCode": room_code,
            "gameId": payload.get("gameId"),
            "roundNo": payload.get("roundNo"),
            "serverTime": datetime.utcnow().isoformat(),
            "data": payload,
        }
        dead: list[WebSocket] = []
        for ws in self._rooms.get(room_code, []):
            try:
                await ws.send_json(body)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room_code, ws)


ws_manager = WSManager()
