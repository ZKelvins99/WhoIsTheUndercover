import json
import random
import secrets
from collections import Counter
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import GamePhase, RoleType
from app.core.errors import BAD_REQUEST, FORBIDDEN, INVALID_PHASE, NOT_FOUND
from app.models import Game, GameRole, GuessAttempt, Room, RoomPlayer, Round, Vote

ALLOWED_TRANSITIONS = {
    GamePhase.GAME_INIT.value: {GamePhase.ROUND_SPEAKING.value},
    GamePhase.ROUND_SPEAKING.value: {GamePhase.ROUND_VOTING.value},
    GamePhase.ROUND_VOTING.value: {GamePhase.ROUND_GUESSING.value, GamePhase.ROUND_TIE_BREAK.value},
    GamePhase.ROUND_TIE_BREAK.value: {GamePhase.ROUND_VOTING.value},
    GamePhase.ROUND_GUESSING.value: {GamePhase.ROUND_RESULT.value, GamePhase.GAME_FINISHED.value},
    GamePhase.ROUND_RESULT.value: {GamePhase.ROUND_SPEAKING.value, GamePhase.GAME_FINISHED.value},
}


class GameService:
    # ─── helpers ───────────────────────────────────────────────

    @staticmethod
    def _gen_room_code() -> str:
        return f"{random.randint(0, 999999):06d}"

    @staticmethod
    def _gen_secret() -> str:
        return secrets.token_hex(16)

    @staticmethod
    def _parse_json(text: str) -> list[int]:
        if not text or text == "[]":
            return []
        return json.loads(text)

    @staticmethod
    def _append_spoken(round_obj: Round, player_id: int):
        order = GameService._parse_json(round_obj.speaking_order)
        if player_id not in order:
            order.append(player_id)
            round_obj.speaking_order = json.dumps(order)

    # ─── room ──────────────────────────────────────────────────

    @staticmethod
    def create_room(db: Session) -> Room:
        for _ in range(10):
            code = GameService._gen_room_code()
            if not db.scalar(select(Room).where(Room.room_code == code)):
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
        p = db.scalar(
            select(RoomPlayer).where(
                RoomPlayer.player_token == player_token,
                RoomPlayer.room_id == room_id,
            )
        )
        if not p:
            raise FORBIDDEN()
        return p

    @staticmethod
    def join_room(db: Session, room: Room, nickname: str) -> RoomPlayer:
        if room.is_locked:
            raise BAD_REQUEST("ROOM_LOCKED")
        cnt = db.scalar(
            select(func.count()).select_from(RoomPlayer).where(RoomPlayer.room_id == room.id)
        ) or 0
        if cnt >= 15:
            raise BAD_REQUEST("ROOM_FULL")
        if db.scalar(
            select(RoomPlayer).where(
                RoomPlayer.room_id == room.id, RoomPlayer.nickname == nickname
            )
        ):
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
        player = db.scalar(
            select(RoomPlayer).where(
                RoomPlayer.id == player_id, RoomPlayer.room_id == room.id
            )
        )
        if not player:
            raise NOT_FOUND()
        db.delete(player)
        db.commit()

    # ─── game lifecycle ────────────────────────────────────────

    @staticmethod
    def get_game(db: Session, game_id: int) -> Game:
        game = db.scalar(select(Game).where(Game.id == game_id))
        if not game:
            raise NOT_FOUND()
        return game

    @staticmethod
    def get_round(db: Session, game_id: int, round_no: int) -> Round:
        r = db.scalar(
            select(Round)
            .where(Round.game_id == game_id, Round.round_no == round_no)
            .order_by(Round.id.desc())
        )
        if not r:
            raise NOT_FOUND()
        return r

    @staticmethod
    def get_current_round(db: Session, game: Game) -> Round:
        return GameService.get_round(db, game.id, game.round_no)

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
        players = list(
            db.scalars(
                select(RoomPlayer)
                .where(RoomPlayer.room_id == room.id)
                .order_by(RoomPlayer.id)
            ).all()
        )
        n = len(players)
        if n <= 0:
            raise BAD_REQUEST("NO_PLAYER_IN_ROOM")

        role_total = civilian_count + undercover_count + blank_count
        if role_total <= 0:
            raise BAD_REQUEST("ROLE_COUNT_INVALID")
        if role_total > n:
            raise BAD_REQUEST("ROLE_COUNT_EXCEED_PLAYER_COUNT")
        civilian_count += n - role_total

        game_no = (
            db.scalar(select(func.max(Game.game_no)).where(Game.room_id == room.id)) or 0
        ) + 1

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

        roles = (
            [RoleType.CIVILIAN.value] * civilian_count
            + [RoleType.UNDERCOVER.value] * undercover_count
            + [RoleType.BLANK.value] * blank_count
        )
        random.shuffle(roles)
        for p, r in zip(players, roles):
            db.add(GameRole(game_id=game.id, player_id=p.id, role=r, is_alive=True))

        db.add(
            Round(game_id=game.id, round_no=1, phase=GamePhase.ROUND_SPEAKING.value)
        )
        db.commit()
        db.refresh(game)
        return game

    @staticmethod
    def finish_game(db: Session, game: Game):
        if game.phase == GamePhase.GAME_FINISHED.value:
            return
        if not GameService._check_auto_finish(db, game):
            GameService._finalize_game(db, game, "MANUAL")

    @staticmethod
    def restart_game(db: Session, game: Game) -> Game:
        room = GameService.get_room_by_id(db, game.room_id)
        role_rows = list(
            db.scalars(select(GameRole).where(GameRole.game_id == game.id)).all()
        )
        return GameService.start_game(
            db,
            room,
            civilian_count=sum(1 for r in role_rows if r.role == RoleType.CIVILIAN.value),
            undercover_count=sum(
                1 for r in role_rows if r.role == RoleType.UNDERCOVER.value
            ),
            blank_count=sum(1 for r in role_rows if r.role == RoleType.BLANK.value),
            civilian_word=game.civilian_word,
            undercover_word=game.undercover_word,
        )

    # ─── speaking ──────────────────────────────────────────────

    @staticmethod
    def next_speaker(db: Session, game: Game, mode: str) -> tuple[int | None, bool]:
        if game.phase not in {
            GamePhase.ROUND_SPEAKING.value,
            GamePhase.ROUND_TIE_BREAK.value,
        }:
            raise INVALID_PHASE()

        round_obj = GameService.get_current_round(db, game)
        spoken = set(GameService._parse_json(round_obj.speaking_order))

        if round_obj.is_tie_break:
            eligible = GameService._parse_json(game.tied_player_ids)
        else:
            alive = list(
                db.scalars(
                    select(RoomPlayer.id)
                    .where(
                        RoomPlayer.room_id == game.room_id,
                        RoomPlayer.eliminated == False,
                    )
                    .order_by(RoomPlayer.seat_no)
                ).all()
            )
            eligible = list(alive)

        pending = [pid for pid in eligible if pid not in spoken]
        if not pending:
            game.phase = GamePhase.ROUND_VOTING.value
            round_obj.phase = game.phase
            db.commit()
            return None, True

        next_id = pending[0] if mode == "seq" else random.choice(pending)
        GameService._append_spoken(round_obj, next_id)

        spoken.add(next_id)
        completed = all(pid in spoken for pid in eligible)
        if completed:
            game.phase = GamePhase.ROUND_VOTING.value
            round_obj.phase = game.phase

        db.commit()
        return next_id, completed

    # ─── phase ─────────────────────────────────────────────────

    @staticmethod
    def next_phase(db: Session, game: Game) -> str:
        current = game.phase
        if current == GamePhase.GAME_FINISHED.value:
            raise INVALID_PHASE()

        if current == GamePhase.ROUND_VOTING.value:
            return GameService._handle_vote_result(db, game)

        round_obj = GameService.get_current_round(db, game)
        nxt = {
            GamePhase.ROUND_SPEAKING.value: GamePhase.ROUND_VOTING.value,
            GamePhase.ROUND_TIE_BREAK.value: GamePhase.ROUND_VOTING.value,
            GamePhase.ROUND_GUESSING.value: GamePhase.ROUND_RESULT.value,
            GamePhase.GAME_INIT.value: GamePhase.ROUND_SPEAKING.value,
        }.get(current)

        if current == GamePhase.ROUND_RESULT.value:
            return GameService._start_next_round(db, game)

        if not nxt or nxt not in ALLOWED_TRANSITIONS.get(current, set()):
            raise INVALID_PHASE()

        game.phase = nxt
        round_obj.phase = nxt
        db.commit()
        return nxt

    @staticmethod
    def _handle_vote_result(db: Session, game: Game) -> str:
        round_obj = GameService.get_current_round(db, game)
        votes = list(
            db.scalars(select(Vote).where(Vote.round_id == round_obj.id)).all()
        )
        if not votes:
            raise BAD_REQUEST("NO_VOTE_YET")

        counter = Counter(v.target_player_id for v in votes)
        top = counter.most_common()
        is_revote = round_obj.is_tie_break

        # Check for tie
        if len(top) > 1 and top[0][1] == top[1][1]:
            if is_revote:
                # Second tie → nobody eliminated, go to guessing
                game.phase = GamePhase.ROUND_GUESSING.value
                round_obj.phase = game.phase
                db.commit()
                return game.phase
            # First tie → tie-break
            tied_ids = [pid for pid, _ in top if _ == top[0][1]]
            game.tied_player_ids = json.dumps(tied_ids)
            tie_round = Round(
                game_id=game.id,
                round_no=game.round_no,
                phase=GamePhase.ROUND_TIE_BREAK.value,
                is_tie_break=True,
            )
            db.add(tie_round)
            game.phase = GamePhase.ROUND_TIE_BREAK.value
            db.commit()
            return game.phase

        # No tie → eliminate
        eliminated_id = top[0][0]
        role = db.scalar(
            select(GameRole).where(
                GameRole.game_id == game.id,
                GameRole.player_id == eliminated_id,
            )
        )
        if role:
            role.is_alive = False
        player = db.scalar(select(RoomPlayer).where(RoomPlayer.id == eliminated_id))
        if player:
            player.eliminated = True

        if GameService._check_auto_finish(db, game):
            return GamePhase.GAME_FINISHED.value

        game.phase = GamePhase.ROUND_GUESSING.value
        round_obj.phase = game.phase
        db.commit()
        return game.phase

    @staticmethod
    def _start_next_round(db: Session, game: Game) -> str:
        game.round_no += 1
        game.phase = GamePhase.ROUND_SPEAKING.value
        game.tied_player_ids = "[]"
        db.add(
            Round(
                game_id=game.id,
                round_no=game.round_no,
                phase=GamePhase.ROUND_SPEAKING.value,
            )
        )
        db.commit()
        return game.phase

    # ─── vote ──────────────────────────────────────────────────

    @staticmethod
    def vote(db: Session, game: Game, round_no: int, voter: RoomPlayer, target_id: int):
        if game.phase not in {GamePhase.ROUND_VOTING.value, GamePhase.ROUND_TIE_BREAK.value}:
            raise INVALID_PHASE()
        if voter.eliminated:
            raise BAD_REQUEST("ELIMINATED_PLAYER_CANNOT_VOTE")

        round_obj = GameService.get_round(db, game.id, round_no)
        if db.scalar(
            select(Vote).where(
                Vote.round_id == round_obj.id,
                Vote.voter_player_id == voter.id,
            )
        ):
            raise BAD_REQUEST("DUPLICATE_VOTE")

        target = db.scalar(
            select(RoomPlayer).where(
                RoomPlayer.id == target_id,
                RoomPlayer.room_id == game.room_id,
            )
        )
        if not target or target.eliminated:
            raise BAD_REQUEST("INVALID_VOTE_TARGET")

        if round_obj.is_tie_break:
            tied = set(GameService._parse_json(game.tied_player_ids))
            if target_id not in tied:
                raise BAD_REQUEST("MUST_VOTE_TIED_PLAYER")

        db.add(
            Vote(
                game_id=game.id,
                round_id=round_obj.id,
                voter_player_id=voter.id,
                target_player_id=target_id,
            )
        )
        db.commit()

    # ─── guess ─────────────────────────────────────────────────

    @staticmethod
    def guess(
        db: Session, game: Game, round_no: int, player: RoomPlayer, guess_text: str
    ) -> bool:
        if game.phase != GamePhase.ROUND_GUESSING.value:
            raise INVALID_PHASE()
        if player.eliminated:
            raise BAD_REQUEST("ELIMINATED_PLAYER_CANNOT_GUESS")

        role = db.scalar(
            select(GameRole).where(
                GameRole.game_id == game.id, GameRole.player_id == player.id
            )
        )
        if not role:
            raise NOT_FOUND()

        round_obj = GameService.get_round(db, game.id, round_no)
        used = list(
            db.scalars(
                select(GuessAttempt).where(
                    GuessAttempt.round_id == round_obj.id,
                    GuessAttempt.player_id == player.id,
                )
            ).all()
        )
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
        elif role.role == RoleType.BLANK.value and guess_text in {
            game.civilian_word,
            game.undercover_word,
        }:
            hit = True
            game.winner_side = "BLANK"

        db.add(
            GuessAttempt(
                game_id=game.id,
                round_id=round_obj.id,
                player_id=player.id,
                guess_order=len(used) + 1,
                guess_text=guess_text,
                is_hit=hit,
            )
        )

        if hit:
            GameService._finalize_game(db, game, game.winner_side)
            db.commit()
            return True

        # Wrong guess: -1 per attempt
        db.commit()
        return False

    # ─── scoring (real-time, no persistence) ───────────────────

    @staticmethod
    def _check_auto_finish(db: Session, game: Game) -> bool:
        roles = list(
            db.scalars(select(GameRole).where(GameRole.game_id == game.id)).all()
        )
        civ_alive = sum(
            1 for r in roles if r.role == RoleType.CIVILIAN.value and r.is_alive
        )
        uc_alive = sum(
            1 for r in roles if r.role == RoleType.UNDERCOVER.value and r.is_alive
        )
        if uc_alive == 0 and civ_alive > 0:
            GameService._finalize_game(db, game, "CIVILIAN")
            return True
        if uc_alive > 0 and uc_alive >= civ_alive:
            GameService._finalize_game(db, game, "UNDERCOVER")
            return True
        return False

    @staticmethod
    def _finalize_game(db: Session, game: Game, winner_side: str):
        if game.phase == GamePhase.GAME_FINISHED.value:
            return
        game.winner_side = winner_side
        game.phase = GamePhase.GAME_FINISHED.value

    @staticmethod
    def _compute_leaderboard(db: Session, game: Game) -> list[dict]:
        players = list(
            db.scalars(
                select(RoomPlayer)
                .where(RoomPlayer.room_id == game.room_id)
                .order_by(RoomPlayer.id)
            ).all()
        )
        roles = {
            r.player_id: r
            for r in db.scalars(
                select(GameRole).where(GameRole.game_id == game.id)
            ).all()
        }
        rounds = list(
            db.scalars(
                select(Round)
                .where(Round.game_id == game.id)
                .order_by(Round.round_no, Round.id)
            ).all()
        )

        scores: dict[int, dict] = {}
        for p in players:
            scores[p.id] = {
                "playerId": p.id,
                "nickname": p.nickname,
                "totalScore": 0,
                "survivalRounds": 0,
                "hitVotes": 0,
                "joinOrder": p.join_order,
            }

        alive = {pid: True for pid in roles}

        for rnd in rounds:
            # Survival +1 for alive players at round start
            for pid in alive:
                if alive[pid]:
                    scores[pid]["totalScore"] += 1
                    scores[pid]["survivalRounds"] += 1

            # Voting: participation +1, hit-vote +2
            votes = list(
                db.scalars(select(Vote).where(Vote.round_id == rnd.id)).all()
            )
            voted = {v.voter_player_id for v in votes}
            counter = Counter(v.target_player_id for v in votes)
            if counter:
                top_target = counter.most_common(1)[0][0]
                top_count = counter.most_common(1)[0][1]
                is_tie = len(counter) > 1 and counter.most_common(2)[0][1] == counter.most_common(2)[1][1]
                eliminated_this_round = top_target if not is_tie else None

            for v in votes:
                if v.voter_player_id in scores:
                    scores[v.voter_player_id]["totalScore"] += 1
                if (
                    eliminated_this_round
                    and v.target_player_id == eliminated_this_round
                    and eliminated_this_round in roles
                    and v.voter_player_id in roles
                ):
                    voter_role = roles[v.voter_player_id].role
                    target_role = roles[eliminated_this_round].role
                    if voter_role != target_role:
                        scores[v.voter_player_id]["totalScore"] += 2
                        scores[v.voter_player_id]["hitVotes"] += 1

            # Update alive after elimination
            if counter:
                top_count_val = counter.most_common(1)[0][1]
                top_ids = [pid for pid, c in counter.most_common() if c == top_count_val]
                if len(top_ids) == 1:
                    alive[top_ids[0]] = False

        # End-game bonuses
        winner = game.winner_side
        if winner == "CIVILIAN":
            for pid, r in roles.items():
                if r.role == RoleType.CIVILIAN.value:
                    scores[pid]["totalScore"] += 4 if alive.get(pid) else 2
        elif winner == "UNDERCOVER":
            for pid, r in roles.items():
                if r.role == RoleType.UNDERCOVER.value:
                    scores[pid]["totalScore"] += 6 if alive.get(pid) else 3
        elif winner == "BLANK":
            hit_players = {
                g.player_id
                for g in db.scalars(
                    select(GuessAttempt).where(
                        GuessAttempt.game_id == game.id, GuessAttempt.is_hit == True
                    )
                ).all()
            }
            for pid in hit_players:
                if pid in scores:
                    scores[pid]["totalScore"] += 8

        # Blank survival bonus (if didn't win independently)
        if winner != "BLANK":
            for pid, r in roles.items():
                if r.role == RoleType.BLANK.value and alive.get(pid):
                    scores[pid]["totalScore"] += 3

        board = list(scores.values())
        board.sort(
            key=lambda x: (
                -x["totalScore"],
                -x["survivalRounds"],
                -x["hitVotes"],
                x["joinOrder"],
            )
        )
        return board

    @staticmethod
    def leaderboard(db: Session, room: Room) -> list[dict]:
        game = db.scalar(
            select(Game)
            .where(Game.room_id == room.id)
            .order_by(Game.id.desc())
        )
        if not game:
            players = list(
                db.scalars(
                    select(RoomPlayer).where(RoomPlayer.room_id == room.id)
                ).all()
            )
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
        return GameService._compute_leaderboard(db, game)

    # ─── snapshot ──────────────────────────────────────────────

    @staticmethod
    def room_snapshot(
        db: Session, room: Room, host_secret: str | None, player_token: str | None
    ) -> dict:
        game = db.scalar(
            select(Game)
            .where(Game.room_id == room.id)
            .order_by(Game.id.desc())
        )
        players = list(
            db.scalars(
                select(RoomPlayer)
                .where(RoomPlayer.room_id == room.id)
                .order_by(RoomPlayer.seat_no)
            ).all()
        )

        requester = None
        if player_token:
            requester = db.scalar(
                select(RoomPlayer).where(
                    RoomPlayer.room_id == room.id,
                    RoomPlayer.player_token == player_token,
                )
            )

        is_host = (
            host_secret is not None and host_secret == room.host_secret
        )

        roles: dict[int, str] = {}
        spoken_map: dict[int, bool] = {}
        my_word: str | None = None
        my_vote_submitted = False
        my_guess_used = 0
        my_guess_limit = 0
        tied_player_ids: list[int] = []
        vote_map: dict[int, int] = {}

        if game:
            for r in db.scalars(
                select(GameRole).where(GameRole.game_id == game.id)
            ).all():
                roles[r.player_id] = r.role

            round_obj = db.scalar(
                select(Round)
                .where(
                    Round.game_id == game.id, Round.round_no == game.round_no
                )
                .order_by(Round.id.desc())
            )
            if round_obj:
                spoken_list = GameService._parse_json(round_obj.speaking_order)
                spoken_map = {pid: True for pid in spoken_list}

                # Vote details for current round
                round_votes = list(
                    db.scalars(select(Vote).where(Vote.round_id == round_obj.id)).all()
                )
                vote_map = {v.voter_player_id: v.target_player_id for v in round_votes}

                if requester:
                    my_vote_submitted = (
                        db.scalar(
                            select(Vote).where(
                                Vote.round_id == round_obj.id,
                                Vote.voter_player_id == requester.id,
                            )
                        )
                        is not None
                    )
                    my_guess_used = len(
                        list(
                            db.scalars(
                                select(GuessAttempt).where(
                                    GuessAttempt.round_id == round_obj.id,
                                    GuessAttempt.player_id == requester.id,
                                )
                            ).all()
                        )
                    )

            if requester:
                my_role = roles.get(requester.id)
                if my_role == RoleType.CIVILIAN.value:
                    my_word = game.civilian_word
                    my_guess_limit = 1
                elif my_role == RoleType.UNDERCOVER.value:
                    my_word = game.undercover_word
                    my_guess_limit = 1
                elif my_role == RoleType.BLANK.value:
                    my_word = "白板(无固定词)"
                    my_guess_limit = 2

            tied_player_ids = GameService._parse_json(game.tied_player_ids)

        data_players = []
        for p in players:
            role = roles.get(p.id)
            visible_role = (
                role
                if is_host
                or p.eliminated
                or (requester and requester.id == p.id)
                else None
            )
            player_data = {
                "id": p.id,
                "nickname": p.nickname,
                "seatNo": p.seat_no,
                "online": p.is_online,
                "eliminated": p.eliminated,
                "spoken": spoken_map.get(p.id, False),
                "role": visible_role,
            }
            if is_host:
                player_data["votedTargetId"] = vote_map.get(p.id)
            data_players.append(player_data)

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
                "tiedPlayerIds": tied_player_ids,
            }
            if is_host:
                game_data["civilianWord"] = game.civilian_word
                game_data["undercoverWord"] = game.undercover_word

        return {
            "room_code": room.room_code,
            "game": game_data,
            "players": data_players,
            "leaderboard": GameService.leaderboard(db, room),
        }

    # ─── round result ──────────────────────────────────────────

    @staticmethod
    def round_result(db: Session, game_id: int, round_no: int) -> dict:
        r = GameService.get_round(db, game_id, round_no)
        votes = list(
            db.scalars(select(Vote).where(Vote.round_id == r.id)).all()
        )
        guesses = list(
            db.scalars(select(GuessAttempt).where(GuessAttempt.round_id == r.id)).all()
        )
        counter = Counter(v.target_player_id for v in votes)
        top = counter.most_common(1)

        return {
            "roundNo": round_no,
            "isTieBreak": r.is_tie_break,
            "votes": [
                {"voter": v.voter_player_id, "target": v.target_player_id}
                for v in votes
            ],
            "eliminated": top[0][0] if top and not (
                len(counter) > 1 and counter.most_common(2)[0][1] == counter.most_common(2)[1][1]
            ) else None,
            "guessAttempts": [
                {
                    "playerId": g.player_id,
                    "guessText": g.guess_text,
                    "isHit": g.is_hit,
                }
                for g in guesses
            ],
            "publishedAt": datetime.utcnow().isoformat(),
        }
