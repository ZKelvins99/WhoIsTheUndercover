from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas import CreateRoomResp, JoinReq, JoinResp, LockReq
from app.services.game_service import GameService
from app.services.ws import ws_manager

router = APIRouter(prefix="/api", tags=["room"])


@router.post("/host/rooms", response_model=CreateRoomResp)
async def create_room(db: Session = Depends(get_db)):
    room = GameService.create_room(db)
    return {"room_code": room.room_code, "host_secret": room.host_secret}


@router.post("/rooms/{room_code}/join", response_model=JoinResp)
async def join_room(room_code: str, req: JoinReq, db: Session = Depends(get_db)):
    room = GameService.get_room_by_code(db, room_code)
    player = GameService.join_room(db, room, req.nickname)
    await ws_manager.broadcast(room.room_code, "room.player_joined", {"playerId": player.id, "nickname": player.nickname})
    return {"player_id": player.id, "player_token": player.player_token}


@router.post("/rooms/{room_code}/lock")
async def lock_room(
    room_code: str,
    req: LockReq,
    x_host_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    room = GameService.get_room_by_code(db, room_code)
    GameService.host_guard(room, x_host_secret)
    GameService.set_lock(db, room, req.locked)
    await ws_manager.broadcast(room.room_code, "room.lock_changed", {"locked": req.locked})
    return {"ok": True}


@router.post("/rooms/{room_code}/kick/{player_id}")
async def kick_player(
    room_code: str,
    player_id: int,
    x_host_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    room = GameService.get_room_by_code(db, room_code)
    GameService.host_guard(room, x_host_secret)
    GameService.kick_player(db, room, player_id)
    await ws_manager.broadcast(room.room_code, "room.player_left", {"playerId": player_id})
    return {"ok": True}


@router.get("/rooms/{room_code}/snapshot")
def room_snapshot(
    room_code: str,
    x_host_secret: str | None = Header(default=None),
    x_player_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    room = GameService.get_room_by_code(db, room_code)
    return GameService.room_snapshot(db, room, x_host_secret, x_player_token)


@router.get("/rooms/{room_code}/leaderboard")
def room_leaderboard(room_code: str, db: Session = Depends(get_db)):
    room = GameService.get_room_by_code(db, room_code)
    return {"items": GameService.leaderboard(db, room)}
