import random
import secrets
from collections import Counter
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import GamePhase, RoleType
from app.core.errors import BAD_REQUEST, FORBIDDEN, INVALID_PHASE, NOT_FOUND
from app.models import Game, GameRole, GameScore, GuessAttempt, Room, RoomPlayer, Round, RoundScore, SpeakingRecord, Vote


ALLOWED_TRANSITIONS = {
    GamePhase.GAME_INIT.value: {GamePhase.ROUND_SPEAKING.value},
    GamePhase.ROUND_SPEAKING.value: {GamePhase.ROUND_VOTING.value},
    GamePhase.ROUND_VOTING.value: {GamePhase.ROUND_TIE_BREAK.value, GamePhase.ROUND_GUESSING.value},
    GamePhase.ROUND_TIE_BREAK.value: {GamePhase.ROUND_GUESSING.value},
    GamePhase.ROUND_GUESSING.value: {GamePhase.ROUND_RESULT.value, GamePhase.GAME_FINISHED.value},
    GamePhase.ROUND_RESULT.value: {GamePhase.ROUND_SPEAKING.value, GamePhase.GAME_FINISHED.value},
}


class GameService:
    @staticmethod
    def _gen_room_code() -> str:
        return f"{random.randint(0, 999999):06d}"

    @staticmethod
    def _gen_secret() -> str:
        return secrets.token_hex(16)

    @staticmethod
    def create_room(db: Session) -> Room:
        for _ in range(10):
            code = GameService._gen_room_code()
            exists = db.scalar(select(Room).where(Room.room_code == code))
            if not exists:
                room = Room(room_code=code, host_secret=GameService._gen_secret())
                db.add(room)
                db.commit()
                db.refresh(room)
                return room
        raise BAD_REQUEST("ROOM_CODE_GENERATION_FAILED")

    @staticmethod
    def get_room_by_code(db: Session, room_code: str) -> Room:
        room = db.scalar(select(Room).where(Room.room_code == room_code))
        if not room:
            raise NOT_FOUND()
        return room

    @staticmethod
    def get_room_by_id(db: Session, room_id: int) -> Room:
        room = db.scalar(select(Room).where(Room.id == room_id))
        if not room:
            raise NOT_FOUND()
        return room

    @staticmethod
    def host_guard(room: Room, host_secret: str | None):
        if not host_secret or host_secret != room.host_secret:
            raise FORBIDDEN()

    @staticmethod
    def player_guard(db: Session, player_token: str | None, room_id: int) -> RoomPlayer:
        if not player_token:
            raise FORBIDDEN()
        p = db.scalar(select(RoomPlayer).where(RoomPlayer.player_token == player_token, RoomPlayer.room_id == room_id))
        if not p:
            raise FORBIDDEN()
        return p

    @staticmethod
    def join_room(db: Session, room: Room, nickname: str) -> RoomPlayer:
        if room.is_locked:
            raise BAD_REQUEST("ROOM_LOCKED")
        cnt = db.scalar(select(func.count()).select_from(RoomPlayer).where(RoomPlayer.room_id == room.id)) or 0
        if cnt >= 15:
            raise BAD_REQUEST("ROOM_FULL")
        nickname_exists = db.scalar(
            select(RoomPlayer).where(RoomPlayer.room_id == room.id, RoomPlayer.nickname == nickname)
        )
        if nickname_exists:
            raise BAD_REQUEST("NICKNAME_DUPLICATED")
        player = RoomPlayer(
            room_id=room.id,
            nickname=nickname,
            player_token=GameService._gen_secret(),
            seat_no=cnt + 1,
            join_order=cnt + 1,
        )
        db.add(player)
        db.commit()
        db.refresh(player)
        return player

    @staticmethod
    def set_lock(db: Session, room: Room, locked: bool):
        room.is_locked = locked
        db.commit()

    @staticmethod
    def kick_player(db: Session, room: Room, player_id: int):
        player = db.scalar(select(RoomPlayer).where(RoomPlayer.id == player_id, RoomPlayer.room_id == room.id))
        if not player:
            raise NOT_FOUND()
        db.delete(player)
        db.commit()

    @staticmethod
    def start_game(
        db: Session,
        room: Room,
        civilian_count: int,
        undercover_count: int,
        blank_count: int,
        civilian_word: str,
        undercover_word: str,
    ) -> Game:
        players = list(db.scalars(select(RoomPlayer).where(RoomPlayer.room_id == room.id).order_by(RoomPlayer.id)).all())
        n = len(players)
        if n <= 0:
            raise BAD_REQUEST("NO_PLAYER_IN_ROOM")

        role_total = civilian_count + undercover_count + blank_count
        if role_total <= 0:
            raise BAD_REQUEST("ROLE_COUNT_INVALID")
        if role_total > n:
            raise BAD_REQUEST("ROLE_COUNT_EXCEED_PLAYER_COUNT")

        # If host sets fewer roles than total players, fill remaining as civilians.
        civilian_count = civilian_count + (n - role_total)

        game_no = (db.scalar(select(func.max(Game.game_no)).where(Game.room_id == room.id)) or 0) + 1

        # Reset room-level elimination flags for a new game.
        for p in players:
            p.eliminated = False

        game = Game(
            room_id=room.id,
            game_no=game_no,
            phase=GamePhase.ROUND_SPEAKING.value,
            round_no=1,
            civilian_word=civilian_word,
            undercover_word=undercover_word,
        )
        db.add(game)
        db.flush()

        roles = [RoleType.CIVILIAN.value] * civilian_count + [RoleType.UNDERCOVER.value] * undercover_count + [RoleType.BLANK.value] * blank_count
        random.shuffle(roles)
        for p, r in zip(players, roles):
            db.add(GameRole(game_id=game.id, player_id=p.id, role=r, is_alive=True))
            pre_bonus = GameService._next_game_compensation(db, room.id, game_no, p.id)
            db.add(GameScore(game_id=game.id, player_id=p.id, total_score=pre_bonus, survival_rounds=0, hit_votes=0))

        db.add(Round(game_id=game.id, round_no=1, phase=GamePhase.ROUND_SPEAKING.value))
        db.flush()
        GameService._init_speaking_records(db, game.id, 1)
        db.commit()
        db.refresh(game)
        return game

    @staticmethod
    def _next_game_compensation(db: Session, room_id: int, game_no: int, player_id: int) -> int:
        bonus = 0
        prev1 = game_no - 1
        prev2 = game_no - 2

        if prev2 >= 1:
            if GameService._is_bottom3(db, room_id, prev1, player_id) and GameService._is_bottom3(db, room_id, prev2, player_id):
                bonus += 1

        if prev1 >= 1 and GameService._is_first_round_eliminated(db, room_id, prev1, player_id):
            bonus += 1
        return bonus

    @staticmethod
    def _is_bottom3(db: Session, room_id: int, game_no: int, player_id: int) -> bool:
        game = db.scalar(select(Game).where(Game.room_id == room_id, Game.game_no == game_no))
        if not game:
            return False
        scores = list(db.scalars(select(GameScore).where(GameScore.game_id == game.id)).all())
        if not scores:
            return False
        scores.sort(key=lambda x: x.total_score)
        bottom = {x.player_id for x in scores[:3]}
        return player_id in bottom

    @staticmethod
    def _is_first_round_eliminated(db: Session, room_id: int, game_no: int, player_id: int) -> bool:
        game = db.scalar(select(Game).where(Game.room_id == room_id, Game.game_no == game_no))
        if not game:
            return False
        role = db.scalar(select(GameRole).where(GameRole.game_id == game.id, GameRole.player_id == player_id))
        if not role or role.is_alive:
            return False
        # Heuristic: if eliminated and round1 has votes targeting this player, treat as first-round elimination.
        round1 = db.scalar(select(Round).where(Round.game_id == game.id, Round.round_no == 1))
        if not round1:
            return False
        hit = db.scalar(select(Vote).where(Vote.round_id == round1.id, Vote.target_player_id == player_id))
        return hit is not None

    @staticmethod
    def _score_add(db: Session, game_id: int, round_id: int | None, player_id: int, delta: int):
        gs = db.scalar(select(GameScore).where(GameScore.game_id == game_id, GameScore.player_id == player_id))
        if not gs:
            return
        gs.total_score = min(15, gs.total_score + delta)
        if round_id is not None:
            rs = db.scalar(
                select(RoundScore).where(
                    RoundScore.game_id == game_id,
                    RoundScore.round_id == round_id,
                    RoundScore.player_id == player_id,
                )
            )
            if not rs:
                rs = RoundScore(game_id=game_id, round_id=round_id, player_id=player_id, score=0)
                db.add(rs)
            rs.score += delta

    @staticmethod
    def _is_enemy(role_a: str, role_b: str) -> bool:
        if role_a == role_b:
            return False
        # Treat blank as independent enemy side in this simplified implementation.
        return True

    @staticmethod
    def _check_auto_finish(db: Session, game: Game) -> bool:
        roles = list(db.scalars(select(GameRole).where(GameRole.game_id == game.id)).all())
        civilians_alive = sum(1 for r in roles if r.role == RoleType.CIVILIAN.value and r.is_alive)
        undercovers_alive = sum(1 for r in roles if r.role == RoleType.UNDERCOVER.value and r.is_alive)

        if undercovers_alive == 0 and civilians_alive > 0:
            GameService._finalize_game(db, game, "CIVILIAN")
            return True
        if undercovers_alive > 0 and undercovers_alive >= civilians_alive:
            GameService._finalize_game(db, game, "UNDERCOVER")
            return True
        return False

    @staticmethod
    def _settle_round_scores(db: Session, game: Game, round_obj: Round, eliminated_player_id: int | None):
        roles = {r.player_id: r for r in db.scalars(select(GameRole).where(GameRole.game_id == game.id)).all()}
        players = {p.id: p for p in db.scalars(select(RoomPlayer).where(RoomPlayer.room_id == game.room_id)).all()}
        votes = list(db.scalars(select(Vote).where(Vote.round_id == round_obj.id)).all())

        voted_by = {v.voter_player_id for v in votes}
        for pid, role_row in roles.items():
            player = players.get(pid)
            if not player:
                continue
            if role_row.is_alive:
                GameService._score_add(db, game.id, round_obj.id, pid, 1)
                gs = db.scalar(select(GameScore).where(GameScore.game_id == game.id, GameScore.player_id == pid))
                if gs:
                    gs.survival_rounds += 1

            if role_row.is_alive and player.is_online and pid not in voted_by:
                GameService._score_add(db, game.id, round_obj.id, pid, -1)

        for v in votes:
            GameService._score_add(db, game.id, round_obj.id, v.voter_player_id, 1)

        if eliminated_player_id is not None and eliminated_player_id in roles:
            eliminated_role = roles[eliminated_player_id].role
            for v in votes:
                if v.target_player_id != eliminated_player_id:
                    continue
                voter_role = roles.get(v.voter_player_id)
                if voter_role and GameService._is_enemy(voter_role.role, eliminated_role):
                    GameService._score_add(db, game.id, round_obj.id, v.voter_player_id, 2)
                    gs = db.scalar(select(GameScore).where(GameScore.game_id == game.id, GameScore.player_id == v.voter_player_id))
                    if gs:
                        gs.hit_votes += 1

    @staticmethod
    def _finalize_game(db: Session, game: Game, winner_side: str):
        if game.phase == GamePhase.GAME_FINISHED.value:
            return
        game.winner_side = winner_side
        game.phase = GamePhase.GAME_FINISHED.value

        roles = list(db.scalars(select(GameRole).where(GameRole.game_id == game.id)).all())

        if winner_side == "CIVILIAN":
            for r in roles:
                if r.role == RoleType.CIVILIAN.value:
                    GameService._score_add(db, game.id, None, r.player_id, 4 if r.is_alive else 2)
        elif winner_side == "UNDERCOVER":
            for r in roles:
                if r.role == RoleType.UNDERCOVER.value:
                    GameService._score_add(db, game.id, None, r.player_id, 6 if r.is_alive else 3)
        elif winner_side == "BLANK":
            blank_hit_players = {
                x.player_id
                for x in db.scalars(select(GuessAttempt).where(GuessAttempt.game_id == game.id, GuessAttempt.is_hit == True)).all()
            }
            for pid in blank_hit_players:
                GameService._score_add(db, game.id, None, pid, 8)

        # Blank survives to final round without independent win: +3.
        if winner_side != "BLANK":
            for r in roles:
                if r.role == RoleType.BLANK.value and r.is_alive:
                    GameService._score_add(db, game.id, None, r.player_id, 3)

        db.commit()

    @staticmethod
    def _init_speaking_records(db: Session, game_id: int, round_no: int):
        round_obj = db.scalar(select(Round).where(Round.game_id == game_id, Round.round_no == round_no))
        if not round_obj:
            return
        game = db.scalar(select(Game).where(Game.id == game_id))
        if not game:
            return
        alive_players = list(
            db.scalars(
                select(RoomPlayer)
                .where(RoomPlayer.room_id == game.room_id, RoomPlayer.eliminated == False)
                .order_by(RoomPlayer.seat_no)
            ).all()
        )
        for idx, p in enumerate(alive_players, start=1):
            db.add(
                SpeakingRecord(
                    game_id=game_id,
                    round_id=round_obj.id,
                    player_id=p.id,
                    spoken=False,
                    order_no=idx,
                )
            )

    @staticmethod
    def next_speaker(db: Session, game: Game, round_no: int, mode: str) -> tuple[int | None, bool]:
        if game.phase != GamePhase.ROUND_SPEAKING.value:
            raise INVALID_PHASE()

        round_obj = GameService.get_round(db, game.id, round_no)
        pending_records = list(
            db.scalars(
                select(SpeakingRecord)
                .join(RoomPlayer, RoomPlayer.id == SpeakingRecord.player_id)
                .where(
                    SpeakingRecord.round_id == round_obj.id,
                    SpeakingRecord.spoken == False,
                    RoomPlayer.eliminated == False,
                )
            ).all()
        )

        if not pending_records:
            game.phase = GamePhase.ROUND_VOTING.value
            round_obj.phase = GamePhase.ROUND_VOTING.value
            db.commit()
            return None, True

        if mode == "seq":
            pending_records.sort(key=lambda x: x.order_no)
            current = pending_records[0]
        else:
            current = random.choice(pending_records)

        current.spoken = True

        still_pending = list(
            db.scalars(
                select(SpeakingRecord)
                .join(RoomPlayer, RoomPlayer.id == SpeakingRecord.player_id)
                .where(
                    SpeakingRecord.round_id == round_obj.id,
                    SpeakingRecord.spoken == False,
                    RoomPlayer.eliminated == False,
                )
            ).all()
        )
        completed = len(still_pending) == 0
        if completed:
            game.phase = GamePhase.ROUND_VOTING.value
            round_obj.phase = GamePhase.ROUND_VOTING.value

        db.commit()
        return current.player_id, completed

    @staticmethod
    def get_game(db: Session, game_id: int) -> Game:
        game = db.scalar(select(Game).where(Game.id == game_id))
        if not game:
            raise NOT_FOUND()
        return game

    @staticmethod
    def get_round(db: Session, game_id: int, round_no: int) -> Round:
        r = db.scalar(select(Round).where(Round.game_id == game_id, Round.round_no == round_no))
        if not r:
            raise NOT_FOUND()
        return r

    @staticmethod
    def next_phase(db: Session, game: Game):
        current = game.phase
        if current == GamePhase.GAME_FINISHED.value:
            raise INVALID_PHASE()

        if current == GamePhase.ROUND_VOTING.value:
            round_obj = GameService.get_round(db, game.id, game.round_no)
            votes = list(db.scalars(select(Vote).where(Vote.round_id == round_obj.id)).all())
            if not votes:
                raise BAD_REQUEST("NO_VOTE_YET")
            counter = Counter([v.target_player_id for v in votes])
            top = counter.most_common()
            if len(top) > 1 and top[0][1] == top[1][1]:
                game.phase = GamePhase.ROUND_TIE_BREAK.value
                round_obj.phase = game.phase
                db.commit()
                return game.phase
            eliminated_player_id = top[0][0]
            role = db.scalar(select(GameRole).where(GameRole.game_id == game.id, GameRole.player_id == eliminated_player_id))
            if role:
                role.is_alive = False
            player = db.scalar(select(RoomPlayer).where(RoomPlayer.id == eliminated_player_id))
            if player:
                player.eliminated = True

            GameService._settle_round_scores(db, game, round_obj, eliminated_player_id)

            if GameService._check_auto_finish(db, game):
                return GamePhase.GAME_FINISHED.value

            game.phase = GamePhase.ROUND_GUESSING.value
            round_obj.phase = game.phase
            db.commit()
            return game.phase

        next_steps = {
            GamePhase.ROUND_SPEAKING.value: GamePhase.ROUND_VOTING.value,
            GamePhase.ROUND_TIE_BREAK.value: GamePhase.ROUND_GUESSING.value,
            GamePhase.ROUND_GUESSING.value: GamePhase.ROUND_RESULT.value,
            GamePhase.ROUND_RESULT.value: GamePhase.ROUND_SPEAKING.value,
            GamePhase.GAME_INIT.value: GamePhase.ROUND_SPEAKING.value,
        }
        if current not in next_steps:
            raise INVALID_PHASE()

        nxt = next_steps[current]
        if nxt == GamePhase.ROUND_SPEAKING.value and current == GamePhase.ROUND_RESULT.value:
            game.round_no += 1
            db.add(Round(game_id=game.id, round_no=game.round_no, phase=GamePhase.ROUND_SPEAKING.value))
            db.flush()
            GameService._init_speaking_records(db, game.id, game.round_no)

        game.phase = nxt
        r = db.scalar(select(Round).where(Round.game_id == game.id, Round.round_no == game.round_no))
        if r:
            r.phase = game.phase
        db.commit()
        return game.phase

    @staticmethod
    def vote(db: Session, game: Game, round_no: int, voter: RoomPlayer, target_player_id: int):
        if game.phase not in {GamePhase.ROUND_VOTING.value, GamePhase.ROUND_TIE_BREAK.value}:
            raise INVALID_PHASE()
        if voter.eliminated:
            raise BAD_REQUEST("ELIMINATED_PLAYER_CANNOT_VOTE")

        r = GameService.get_round(db, game.id, round_no)
        exists = db.scalar(select(Vote).where(Vote.round_id == r.id, Vote.voter_player_id == voter.id))
        if exists:
            raise BAD_REQUEST("DUPLICATE_VOTE")

        target = db.scalar(select(RoomPlayer).where(RoomPlayer.id == target_player_id, RoomPlayer.room_id == game.room_id))
        if not target or target.eliminated:
            raise BAD_REQUEST("INVALID_VOTE_TARGET")

        db.add(Vote(game_id=game.id, round_id=r.id, voter_player_id=voter.id, target_player_id=target_player_id))
        db.commit()

    @staticmethod
    def guess(db: Session, game: Game, round_no: int, player: RoomPlayer, guess_text: str) -> bool:
        if game.phase != GamePhase.ROUND_GUESSING.value:
            raise INVALID_PHASE()
        if player.eliminated:
            raise BAD_REQUEST("ELIMINATED_PLAYER_CANNOT_GUESS")

        role = db.scalar(select(GameRole).where(GameRole.game_id == game.id, GameRole.player_id == player.id))
        if not role:
            raise NOT_FOUND()

        r = GameService.get_round(db, game.id, round_no)
        used = list(db.scalars(select(GuessAttempt).where(GuessAttempt.round_id == r.id, GuessAttempt.player_id == player.id)).all())
        limit = 2 if role.role == RoleType.BLANK.value else 1
        if len(used) >= limit:
            raise BAD_REQUEST("GUESS_LIMIT_REACHED")

        hit = False
        if role.role == RoleType.CIVILIAN.value and guess_text == game.undercover_word:
            hit = True
            game.winner_side = "CIVILIAN"
        elif role.role == RoleType.UNDERCOVER.value and guess_text == game.civilian_word:
            hit = True
            game.winner_side = "UNDERCOVER"
        elif role.role == RoleType.BLANK.value and guess_text in {game.civilian_word, game.undercover_word}:
            hit = True
            game.winner_side = "BLANK"

        db.add(
            GuessAttempt(
                game_id=game.id,
                round_id=r.id,
                player_id=player.id,
                guess_order=len(used) + 1,
                guess_text=guess_text,
                is_hit=hit,
            )
        )

        round_obj = GameService.get_round(db, game.id, round_no)

        if hit:
            GameService._score_add(db, game.id, round_obj.id, player.id, 5)
            GameService._finalize_game(db, game, game.winner_side)
            return True

        GameService._score_add(db, game.id, round_obj.id, player.id, -1)

        if role.role == RoleType.BLANK.value:
            attempts = list(
                db.scalars(
                    select(GuessAttempt).where(GuessAttempt.round_id == round_obj.id, GuessAttempt.player_id == player.id)
                ).all()
            )
            if len(attempts) == 1:
                # plus current attempt will be 2nd if no hit in both.
                pass
            if len(attempts) >= 1 and (len(attempts) + 1) == 2:
                first_hit = any(x.is_hit for x in attempts)
                if not first_hit:
                    GameService._score_add(db, game.id, round_obj.id, player.id, -1)

        db.commit()
        return hit

    @staticmethod
    def leaderboard(db: Session, room: Room, game_id: int | None = None) -> list[dict]:
        if game_id is None:
            game = db.scalar(select(Game).where(Game.room_id == room.id).order_by(Game.id.desc()))
            if not game:
                players = list(db.scalars(select(RoomPlayer).where(RoomPlayer.room_id == room.id)).all())
                return [
                    {
                        "playerId": p.id,
                        "nickname": p.nickname,
                        "totalScore": 0,
                        "survivalRounds": 0,
                        "hitVotes": 0,
                        "joinOrder": p.join_order,
                    }
                    for p in players
                ]
            game_id = game.id

        rows = list(db.scalars(select(GameScore).where(GameScore.game_id == game_id)).all())
        players = {
            p.id: p for p in db.scalars(select(RoomPlayer).where(RoomPlayer.room_id == room.id)).all()
        }
        board = []
        for s in rows:
            p = players.get(s.player_id)
            if not p:
                continue
            board.append(
                {
                    "playerId": p.id,
                    "nickname": p.nickname,
                    "totalScore": s.total_score,
                    "survivalRounds": s.survival_rounds,
                    "hitVotes": s.hit_votes,
                    "joinOrder": p.join_order,
                }
            )
        board.sort(key=lambda x: (-x["totalScore"], -x["survivalRounds"], -x["hitVotes"], x["joinOrder"]))
        return board

    @staticmethod
    def room_snapshot(db: Session, room: Room, host_secret: str | None, player_token: str | None) -> dict:
        game = db.scalar(select(Game).where(Game.room_id == room.id).order_by(Game.id.desc()))
        players = list(db.scalars(select(RoomPlayer).where(RoomPlayer.room_id == room.id).order_by(RoomPlayer.seat_no)).all())

        requester_player = None
        if player_token:
            requester_player = db.scalar(
                select(RoomPlayer).where(RoomPlayer.room_id == room.id, RoomPlayer.player_token == player_token)
            )

        roles = {}
        speaking_map: dict[int, bool] = {}
        my_word: str | None = None
        my_vote_submitted = False
        my_guess_used = 0
        my_guess_limit = 0
        if game:
            role_rows = list(db.scalars(select(GameRole).where(GameRole.game_id == game.id)).all())
            roles = {r.player_id: r.role for r in role_rows}
            round_obj = db.scalar(select(Round).where(Round.game_id == game.id, Round.round_no == game.round_no))
            if round_obj:
                records = list(db.scalars(select(SpeakingRecord).where(SpeakingRecord.round_id == round_obj.id)).all())
                speaking_map = {r.player_id: r.spoken for r in records}

                if requester_player:
                    my_vote_submitted = (
                        db.scalar(
                            select(Vote).where(
                                Vote.round_id == round_obj.id,
                                Vote.voter_player_id == requester_player.id,
                            )
                        )
                        is not None
                    )
                    my_guess_used = len(
                        list(
                            db.scalars(
                                select(GuessAttempt).where(
                                    GuessAttempt.round_id == round_obj.id,
                                    GuessAttempt.player_id == requester_player.id,
                                )
                            ).all()
                        )
                    )

            if requester_player:
                my_role = roles.get(requester_player.id)
                if my_role == RoleType.CIVILIAN.value:
                    my_word = game.civilian_word
                    my_guess_limit = 1
                elif my_role == RoleType.UNDERCOVER.value:
                    my_word = game.undercover_word
                    my_guess_limit = 1
                elif my_role == RoleType.BLANK.value:
                    my_word = "白板(无固定词)"
                    my_guess_limit = 2

        is_host = host_secret == room.host_secret and host_secret is not None
        data_players = []
        for p in players:
            role = roles.get(p.id)
            visible_role = role if is_host or p.eliminated or (requester_player and requester_player.id == p.id) else None
            data_players.append(
                {
                    "id": p.id,
                    "nickname": p.nickname,
                    "seatNo": p.seat_no,
                    "online": p.is_online,
                    "eliminated": p.eliminated,
                    "spoken": speaking_map.get(p.id, False),
                    "role": visible_role,
                }
            )

        game_data = None
        if game:
            game_data = {
                "id": game.id,
                "gameNo": game.game_no,
                "phase": game.phase,
                "roundNo": game.round_no,
                "winnerSide": game.winner_side,
                "myWord": my_word,
                "myVoteSubmitted": my_vote_submitted,
                "myGuessUsed": my_guess_used,
                "myGuessLimit": my_guess_limit,
            }
            if is_host:
                game_data["civilianWord"] = game.civilian_word
                game_data["undercoverWord"] = game.undercover_word

        return {
            "room_code": room.room_code,
            "game": game_data,
            "players": data_players,
            "leaderboard": GameService.leaderboard(db, room, game.id if game else None),
        }

    @staticmethod
    def finish_game(db: Session, game: Game):
        if game.phase != GamePhase.GAME_FINISHED.value:
            # Manual finish: if no winner decided, infer from current alive camp counts.
            if not GameService._check_auto_finish(db, game):
                GameService._finalize_game(db, game, "MANUAL")

    @staticmethod
    def restart_game(db: Session, game: Game) -> Game:
        room = GameService.get_room_by_id(db, game.room_id)
        role_rows = list(db.scalars(select(GameRole).where(GameRole.game_id == game.id)).all())
        civilian_count = sum(1 for r in role_rows if r.role == RoleType.CIVILIAN.value)
        undercover_count = sum(1 for r in role_rows if r.role == RoleType.UNDERCOVER.value)
        blank_count = sum(1 for r in role_rows if r.role == RoleType.BLANK.value)
        return GameService.start_game(
            db,
            room,
            civilian_count=civilian_count,
            undercover_count=undercover_count,
            blank_count=blank_count,
            civilian_word=game.civilian_word,
            undercover_word=game.undercover_word,
        )

    @staticmethod
    def apply_interaction_bonus(
        db: Session,
        game: Game,
        round_no: int,
        speech_bonus_player_ids: list[int],
        logic_bonus_player_ids: list[int],
    ):
        round_obj = GameService.get_round(db, game.id, round_no)
        speech = speech_bonus_player_ids[:2]
        logic = logic_bonus_player_ids[:2]

        bonus_map: dict[int, int] = {}
        for pid in speech:
            bonus_map[pid] = bonus_map.get(pid, 0) + 1
        for pid in logic:
            bonus_map[pid] = bonus_map.get(pid, 0) + 1

        for pid, score in bonus_map.items():
            delta = min(score, 2)
            GameService._score_add(db, game.id, round_obj.id, pid, delta)

        db.commit()

    @staticmethod
    def round_result(db: Session, game_id: int, round_no: int) -> dict:
        r = GameService.get_round(db, game_id, round_no)
        votes = list(db.scalars(select(Vote).where(Vote.round_id == r.id)).all())
        guess = list(db.scalars(select(GuessAttempt).where(GuessAttempt.round_id == r.id)).all())
        counter = Counter([v.target_player_id for v in votes])
        top = counter.most_common(1)

        return {
            "roundNo": round_no,
            "votes": [{"voter": v.voter_player_id, "target": v.target_player_id} for v in votes],
            "eliminated": top[0][0] if top else None,
            "guessAttempts": [
                {"playerId": g.player_id, "guessText": g.guess_text, "isHit": g.is_hit} for g in guess
            ],
            "publishedAt": datetime.utcnow().isoformat(),
        }
