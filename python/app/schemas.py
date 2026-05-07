from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateRoomResp(BaseModel):
    room_code: str
    host_secret: str


class JoinReq(BaseModel):
    nickname: str = Field(min_length=1, max_length=30)


class JoinResp(BaseModel):
    player_id: int
    player_token: str


class LockReq(BaseModel):
    locked: bool


class StartGameReq(BaseModel):
    civilian_count: int = Field(default=8, ge=0)
    undercover_count: int = Field(default=2, ge=0)
    blank_count: int = Field(default=0, ge=0)
    civilian_word: str = Field(default="苹果", min_length=1, max_length=100)
    undercover_word: str = Field(default="梨", min_length=1, max_length=100)


class VoteReq(BaseModel):
    target_player_id: int


class GuessReq(BaseModel):
    guess_text: str = Field(min_length=1, max_length=100)


class NextSpeakerResp(BaseModel):
    player_id: int


class RestartGameReq(BaseModel):
    civilian_word: str = Field(min_length=1, max_length=100)
    undercover_word: str = Field(min_length=1, max_length=100)
    keep_scores: bool = True


class AdjustScoreReq(BaseModel):
    player_id: int
    amount: int


class SnapshotResp(BaseModel):
    room_code: str
    game: Optional[Dict[str, Any]] = None
    players: List[Dict[str, Any]]
    leaderboard: List[Dict[str, Any]]


class EventEnvelope(BaseModel):
    event: str
    roomCode: str
    gameId: Optional[int] = None
    roundNo: Optional[int] = None
    serverTime: datetime
    data: Dict[str, Any]
