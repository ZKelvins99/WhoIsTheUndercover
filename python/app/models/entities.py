from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import GamePhase


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    room_code: Mapped[str] = mapped_column(String(6), unique=True, index=True)
    host_secret: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RoomPlayer(Base):
    __tablename__ = "room_players"
    __table_args__ = (UniqueConstraint("room_id", "nickname", name="uq_room_nickname"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    nickname: Mapped[str] = mapped_column(String(30))
    player_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    seat_no: Mapped[int] = mapped_column(Integer)
    is_online: Mapped[bool] = mapped_column(Boolean, default=True)
    eliminated: Mapped[bool] = mapped_column(Boolean, default=False)
    join_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    game_no: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(32), default=GamePhase.GAME_INIT.value)
    round_no: Mapped[int] = mapped_column(Integer, default=1)
    winner_side: Mapped[str] = mapped_column(String(20), default="")
    civilian_word: Mapped[str] = mapped_column(String(100), default="苹果")
    undercover_word: Mapped[str] = mapped_column(String(100), default="梨")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GameRole(Base):
    __tablename__ = "game_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("room_players.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True)


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    round_no: Mapped[int] = mapped_column(Integer, index=True)
    phase: Mapped[str] = mapped_column(String(32), default=GamePhase.ROUND_SPEAKING.value)


class SpeakingRecord(Base):
    __tablename__ = "speaking_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("room_players.id"), index=True)
    spoken: Mapped[bool] = mapped_column(Boolean, default=False)
    order_no: Mapped[int] = mapped_column(Integer, default=0)


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (UniqueConstraint("round_id", "voter_player_id", name="uq_vote_once_per_round"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id"), index=True)
    voter_player_id: Mapped[int] = mapped_column(ForeignKey("room_players.id"), index=True)
    target_player_id: Mapped[int] = mapped_column(ForeignKey("room_players.id"), index=True)


class GuessAttempt(Base):
    __tablename__ = "guess_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("room_players.id"), index=True)
    guess_order: Mapped[int] = mapped_column(Integer, default=1)
    guess_text: Mapped[str] = mapped_column(String(100))
    is_hit: Mapped[bool] = mapped_column(Boolean, default=False)


class RoundScore(Base):
    __tablename__ = "round_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("room_players.id"), index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)


class GameScore(Base):
    __tablename__ = "game_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("room_players.id"), index=True)
    total_score: Mapped[int] = mapped_column(Integer, default=0)
    survival_rounds: Mapped[int] = mapped_column(Integer, default=0)
    hit_votes: Mapped[int] = mapped_column(Integer, default=0)


class LeaderboardSnapshot(Base):
    __tablename__ = "leaderboard_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    data_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    game_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    actor_type: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(60))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
