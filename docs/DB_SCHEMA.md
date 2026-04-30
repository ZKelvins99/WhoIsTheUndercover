# 数据库表

已实现表：
1. rooms
2. room_players
3. games
4. game_roles
5. rounds
6. speaking_records
7. votes
8. guess_attempts
9. round_scores
10. game_scores
11. leaderboard_snapshots
12. operation_logs

关键约束：
- `room_players(room_id, nickname)` 唯一
- `votes(round_id, voter_player_id)` 唯一
- 高频索引字段：`room_id/game_id/round_id/player_id`
