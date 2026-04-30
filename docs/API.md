# API

基础路径：`/api`

## 房间
- `POST /host/rooms`
- `POST /rooms/{roomCode}/join`
- `POST /rooms/{roomCode}/lock`
- `POST /rooms/{roomCode}/kick/{playerId}`
- `GET /rooms/{roomCode}/snapshot`
- `GET /rooms/{roomCode}/leaderboard`

## 游戏
- `POST /rooms/{roomCode}/games/start`
- `POST /games/{gameId}/rounds/{roundNo}/speaking/next-random`
- `POST /games/{gameId}/rounds/{roundNo}/speaking/next-seq`
- `POST /games/{gameId}/rounds/{roundNo}/phase/next`
- `POST /games/{gameId}/rounds/{roundNo}/vote`
- `POST /games/{gameId}/rounds/{roundNo}/guess`
- `GET /games/{gameId}/rounds/{roundNo}/result`
- `POST /games/{gameId}/finish`

## WS
- `GET /ws/rooms/{roomCode}`
- 事件：`room.player_joined`、`game.started`、`round.phase_changed`、`round.vote_updated`、`round.guess_submitted`、`round.guess_hit`、`game.finished` 等
