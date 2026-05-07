from typing import Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.enums import GamePhase
from app.schemas import AdjustScoreReq, GuessReq, RestartGameReq, StartGameReq, VoteReq
from app.services.game_service import GameService
from app.services.ws import ws_manager

router = APIRouter(prefix="/api", tags=["game"])


def _host_guard_by_game(db: Session, game_id: int, host_secret: Optional[str]):
    game = GameService.get_game(db, game_id)
    room = GameService.get_room_by_id(db, game.room_id)
    GameService.host_guard(room, host_secret)
    return game, room


@router.post("/rooms/{room_code}/games/start")
async def start_game(
    room_code: str,
    req: StartGameReq,
    x_host_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    room = GameService.get_room_by_code(db, room_code)
    GameService.host_guard(room, x_host_secret)
    game = GameService.start_game(
        db,
        room,
        civilian_count=req.civilian_count,
        undercover_count=req.undercover_count,
        blank_count=req.blank_count,
        civilian_word=req.civilian_word,
        undercover_word=req.undercover_word,
    )
    await ws_manager.broadcast(
        room.room_code, "game.started", {"gameId": game.id, "roundNo": 1}
    )
    return {"gameId": game.id}


@router.post("/games/{game_id}/rounds/{round_no}/speaking/next-random")
async def next_random_speaker(
    game_id: int,
    round_no: int,
    x_host_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    game, room = _host_guard_by_game(db, game_id, x_host_secret)
    player_id, completed = GameService.next_speaker(db, game, mode="random")
    if player_id is not None:
        await ws_manager.broadcast(
            room.room_code,
            "round.speaker_selected",
            {"gameId": game.id, "roundNo": round_no, "playerId": player_id},
        )
    if completed:
        await ws_manager.broadcast(
            room.room_code,
            "round.speaking_completed",
            {"gameId": game.id, "roundNo": round_no},
        )
        await ws_manager.broadcast(
            room.room_code,
            "round.phase_changed",
            {
                "gameId": game.id,
                "roundNo": round_no,
                "phase": GamePhase.ROUND_VOTING.value,
            },
        )
    return {"player_id": player_id, "completed": completed}


@router.post("/games/{game_id}/rounds/{round_no}/speaking/next-seq")
async def next_seq_speaker(
    game_id: int,
    round_no: int,
    x_host_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    game, room = _host_guard_by_game(db, game_id, x_host_secret)
    player_id, completed = GameService.next_speaker(db, game, mode="seq")
    if player_id is not None:
        await ws_manager.broadcast(
            room.room_code,
            "round.speaker_selected",
            {"gameId": game.id, "roundNo": round_no, "playerId": player_id},
        )
    if completed:
        await ws_manager.broadcast(
            room.room_code,
            "round.speaking_completed",
            {"gameId": game.id, "roundNo": round_no},
        )
        await ws_manager.broadcast(
            room.room_code,
            "round.phase_changed",
            {
                "gameId": game.id,
                "roundNo": round_no,
                "phase": GamePhase.ROUND_VOTING.value,
            },
        )
    return {"player_id": player_id, "completed": completed}


@router.post("/games/{game_id}/rounds/{round_no}/phase/next")
async def next_phase(
    game_id: int,
    round_no: int,
    x_host_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    game, room = _host_guard_by_game(db, game_id, x_host_secret)
    phase = GameService.next_phase(db, game)
    await ws_manager.broadcast(
        room.room_code,
        "round.phase_changed",
        {"gameId": game.id, "roundNo": game.round_no, "phase": phase},
    )
    if phase == GamePhase.GAME_FINISHED.value:
        await ws_manager.broadcast(
            room.room_code,
            "game.finished",
            {"gameId": game.id, "winnerSide": game.winner_side},
        )
    return {"phase": phase}


@router.post("/games/{game_id}/rounds/{round_no}/vote")
async def vote(
    game_id: int,
    round_no: int,
    req: VoteReq,
    x_player_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    game = GameService.get_game(db, game_id)
    room = GameService.get_room_by_id(db, game.room_id)
    voter = GameService.player_guard(db, x_player_token, game.room_id)
    GameService.vote(db, game, round_no, voter, req.target_player_id)
    await ws_manager.broadcast(
        room.room_code,
        "round.vote_updated",
        {"gameId": game.id, "roundNo": round_no},
    )
    return {"ok": True}


@router.post("/games/{game_id}/rounds/{round_no}/guess")
async def guess(
    game_id: int,
    round_no: int,
    req: GuessReq,
    x_player_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    game = GameService.get_game(db, game_id)
    room = GameService.get_room_by_id(db, game.room_id)
    player = GameService.player_guard(db, x_player_token, game.room_id)
    hit = GameService.guess(db, game, round_no, player, req.guess_text)
    evt = "round.guess_hit" if hit else "round.guess_submitted"
    await ws_manager.broadcast(
        room.room_code,
        evt,
        {
            "gameId": game.id,
            "roundNo": round_no,
            "playerId": player.id,
            "hit": hit,
        },
    )
    if game.phase == GamePhase.GAME_FINISHED.value:
        await ws_manager.broadcast(
            room.room_code,
            "game.finished",
            {"gameId": game.id, "winnerSide": game.winner_side},
        )
    return {"hit": hit}


@router.get("/games/{game_id}/rounds/{round_no}/result")
def round_result(game_id: int, round_no: int, db: Session = Depends(get_db)):
    return GameService.round_result(db, game_id, round_no)


@router.post("/games/{game_id}/finish")
async def finish_game(
    game_id: int,
    x_host_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    game, room = _host_guard_by_game(db, game_id, x_host_secret)
    GameService.finish_game(db, game)
    await ws_manager.broadcast(
        room.room_code,
        "game.finished",
        {"gameId": game.id, "winnerSide": game.winner_side},
    )
    return {"ok": True}


@router.post("/games/{game_id}/restart")
async def restart_game(
    game_id: int,
    req: RestartGameReq,
    x_host_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    game, room = _host_guard_by_game(db, game_id, x_host_secret)
    new_game = GameService.restart_game_with_options(
        db,
        game,
        civilian_word=req.civilian_word,
        undercover_word=req.undercover_word,
        keep_scores=req.keep_scores,
    )
    await ws_manager.broadcast(
        room.room_code,
        "game.started",
        {"gameId": new_game.id, "roundNo": 1},
    )
    return {"gameId": new_game.id}


@router.post("/rooms/{room_code}/adjust-score")
async def adjust_score(
    room_code: str,
    req: AdjustScoreReq,
    x_host_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    room = GameService.get_room_by_code(db, room_code)
    GameService.host_guard(room, x_host_secret)
    GameService.adjust_player_score(db, room, req.player_id, req.amount)
    await ws_manager.broadcast(
        room.room_code,
        "leaderboard.updated",
        {"roomCode": room_code},
    )
    return {"ok": True}
