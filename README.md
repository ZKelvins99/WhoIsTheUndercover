# 谁是卧底线下辅助系统（最终版）— 从头开发执行提示词
> 技术栈：Vue3 + TS + Vite + Pinia + FastAPI(Python3.10+) + Redis + MySQL  
> 场景：线下朋友局（内网可用），无登录账号体系，房主+玩家临时会话机制。

---

## 0. 你是开发 Agent：任务目标

请从 0 到 1 开发一个“谁是卧底”线下辅助 Web 系统，支持：
- 主持人电脑端（可控制流程、查看所有身份）
- 玩家手机端（仅查看自己身份）
- 房间号 6 位数字
- 10–15 人游戏
- 每轮发言管理、投票、出局身份公开、猜词、积分、排名
- 两端底部实时展示排行榜

这是线下口头发言游戏，Web 只做流程辅助与计分同步。

---

## 1. 产品功能（必须全部实现）

### 1.1 房间与加入
- 主持人创建房间：生成 6 位数字房间号
- 玩家输入 房间号+昵称 加入
- 房间内昵称唯一
- 主持人可锁房/解锁房、踢人
- 主持人可开始游戏（需满足人数 10–15）

### 1.2 身份系统
- 角色：平民、卧底、白板
- 主持人可设置阵营人数（提供默认模板）
- 系统自动随机分配身份
- 主持人端可见全员身份
- 玩家端只可见自己身份
- 出局后公开该玩家身份给所有人

### 1.3 回合与发言流程
- 主持人控制阶段推进
- 发言阶段支持：
  - 随机点名下一位
  - 按顺序（座位号）下一位
- 每人每轮发言状态：未发言/已发言
- 全员发言完成后进入投票（或主持人强制跳转，二次确认）

### 1.4 投票与平票
- 每轮每人一票
- 票高者出局并公开身份
- 平票进入加赛：平票者补充发言后全员重投
- 出局玩家不可继续投票/猜词

### 1.5 猜词机制
- 每轮每人可文字猜测“其他阵营词语”
- 平民/卧底：每轮 1 次
- 白板：每轮 2 次
- 本轮提交后不可修改
- 任意人猜中目标阵营词语 => 对应阵营立即胜利，游戏结束
- 客户端不可看到他人猜词内容；主持人端可查看全部猜词记录

### 1.6 排行榜
- 主持人端、玩家端底部固定显示实时排名
- 排名按总分降序，分数相同按“本局存活轮数>投中次数>加入先后”排序

---

## 2. 内网朋友局会话机制（无登录版）

### 2.1 主持人会话
- 创建房间后返回 `host_secret`
- 前端存 localStorage
- 主持人操作接口带 `X-Host-Secret`

### 2.2 玩家会话
- 加入后返回 `player_token`
- 前端存 localStorage
- 玩家操作接口带 `X-Player-Token`
- 刷新后可自动恢复

> 不做注册/登录/JWT 用户中心。  
> 但要做最小权限校验：host_secret 仅主持人可用；player_token 仅绑定该玩家。

---

## 3. 技术架构要求

### 3.1 前端
- Vue3 + TS + Vite
- Pinia 状态管理
- Vue Router
- Element Plus
- 响应式：主持人优先 PC，玩家优先移动端
- WebSocket 实时同步 + HTTP 补偿拉取

### 3.2 后端
- FastAPI + Pydantic + SQLAlchemy + Alembic
- Redis：房间在线、快照、事件广播、幂等键、简易锁
- MySQL：持久化（最终一致）
- Uvicorn/Gunicorn 运行

### 3.3 部署
- Docker Compose 一键启动：
  - frontend
  - backend
  - redis
  - mysql

---

## 4. 游戏状态机（必须按状态迁移控制）

状态定义：
- `LOBBY`
- `GAME_INIT`
- `ROUND_SPEAKING`
- `ROUND_VOTING`
- `ROUND_TIE_BREAK`
- `ROUND_GUESSING`
- `ROUND_RESULT`
- `GAME_FINISHED`

约束：
- 非法迁移直接拒绝
- 仅主持人可推进阶段
- 未到投票阶段不可投票
- 每轮每玩家投票唯一
- 每轮猜词次数按角色限制
- 出局玩家不可提交操作

---

## 5. 数据库表设计（最低要求）

请创建并迁移以下表（可扩展）：

1. `rooms`
2. `room_players`
3. `games`
4. `game_roles`
5. `rounds`
6. `speaking_records`
7. `votes`
8. `guess_attempts`
9. `round_scores`
10. `game_scores`
11. `leaderboard_snapshots`
12. `operation_logs`

关键约束：
- 同房间昵称唯一（room_id + nickname unique）
- 每轮投票唯一（round_id + voter_player_id unique）
- 猜词次数限制在业务层+唯一键联合控制
- 高频索引：room_id, game_id, round_id, player_id

---

## 6. API 设计（先文档后实现）

### 6.1 房间与会话
- `POST /api/host/rooms` 创建房间
- `POST /api/rooms/{roomCode}/join` 玩家加入
- `POST /api/rooms/{roomCode}/lock` 锁房/解锁
- `POST /api/rooms/{roomCode}/kick/{playerId}` 踢人

### 6.2 游戏控制（主持人）
- `POST /api/rooms/{roomCode}/games/start`
- `POST /api/games/{gameId}/rounds/{roundNo}/speaking/next-random`
- `POST /api/games/{gameId}/rounds/{roundNo}/speaking/next-seq`
- `POST /api/games/{gameId}/rounds/{roundNo}/phase/next`
- `POST /api/games/{gameId}/finish`

### 6.3 玩家操作
- `POST /api/games/{gameId}/rounds/{roundNo}/vote`
- `POST /api/games/{gameId}/rounds/{roundNo}/guess`

### 6.4 查询
- `GET /api/rooms/{roomCode}/snapshot`
- `GET /api/rooms/{roomCode}/leaderboard`
- `GET /api/games/{gameId}/rounds/{roundNo}/result`

---

## 7. WebSocket 事件协议（必须实现）

- `room.player_joined`
- `room.player_left`
- `game.started`
- `round.phase_changed`
- `round.speaker_selected`
- `round.speaking_completed`
- `round.vote_updated`
- `round.tie_break_started`
- `round.player_eliminated`
- `round.guess_submitted`
- `round.guess_hit`（触发终局）
- `round.result_published`
- `leaderboard.updated`
- `game.finished`

要求：
- 事件 payload 标准化（含 roomCode/gameId/roundNo/serverTime）
- 客户端断线重连后调用 snapshot 补齐状态

---

## 8. 最终积分机制（激励性最优版，按此实现）

## 8.1 每轮基础分
- 存活到本轮结束：`+1`
- 本轮完成有效投票（不弃票）：`+1`
- 投中本轮被确认敌对关键目标：`+2`
- 未投票（非离线）：`-1`

## 8.2 发言与互动分（主持人标记）
- 高质量发言（每轮最多2人）：`+1`
- 关键追问/逻辑贡献（每轮最多2人）：`+1`
- 单轮互动加分上限：`+2/人`

## 8.3 猜词分
- 猜中并触发阵营胜利：`+5`
- 猜错：`-1`
- 白板每轮可猜2次；若两次都错，额外 `-1`（该轮白板猜词最多 `-3`）

## 8.4 局结算胜负分
- 平民阵营胜：
  - 存活平民 `+4`
  - 出局平民 `+2`
- 卧底阵营胜：
  - 存活卧底 `+6`
  - 出局卧底 `+3`
- 白板独立猜中终局胜：`+8`
- 白板未独立胜但存活到末轮：`+3`

## 8.5 逆风补偿（防滚雪球）
- 连续两局总分倒数3名：下一局开局 `+1`
- 首轮即出局玩家：下一局 `+1`
- 单局积分封顶：`15`

---

## 9. 前端页面清单

## 9.1 主持人端（PC）
1. 创建房间页
2. 房间大厅页（玩家列表、锁房、踢人、开始）
3. 对局控制台（核心）
4. 回合结果弹层
5. 全局排行榜页

控制台必须有：
- 顶部：房间号/局号/轮次/阶段
- 左栏：玩家列表（在线、出局、总分）
- 中栏：流程控制按钮
- 右栏：身份与猜词管理面板（主持人可见）
- 底部固定：实时排行榜

## 9.2 玩家端（手机）
1. 加入房间页
2. 等待大厅页
3. 对局页（我的身份、阶段提示、玩家列表）
4. 投票弹层
5. 猜词弹层
6. 结算页

要求：
- 玩家只能看到自己的身份
- 他人身份仅在其出局后显示
- 底部固定排行榜始终可见

---

## 10. Redis 设计约束

Redis Key 建议：
- `room:{code}:online_players`
- `room:{code}:snapshot`
- `game:{id}:round:{n}:idempotent:vote:{playerId}`
- `game:{id}:round:{n}:idempotent:guess:{playerId}:{k}`
- `room:{code}:ws:channel`
- `room:{code}:lock:phase_change`

流程规范：
1. 校验状态
2. MySQL 事务写入
3. 刷新 Redis snapshot
4. 广播 WS 事件

---

## 11. 代码质量与工程规范

- 后端：分层（router/service/repo/model/schema）
- 前端：按 domain 拆模块（room/game/leaderboard）
- 全部关键逻辑写类型注解
- 关键流程写单元测试
- API 错误码统一（如 `4001 INVALID_PHASE`）
- README 提供 5 分钟本地启动指南

---

## 12. 测试清单（必须交付）

1. 房间创建/加入/锁房/踢人
2. 10–15 人身份分配正确
3. 发言随机与顺序切换正确
4. 投票幂等与平票加赛
5. 猜词次数限制与命中终局
6. 积分结算准确
7. 排行榜两端同步一致
8. 断线重连恢复
9. 连续 5 局无状态错乱

---

## 13. 文档交付（必须先写再编码）

请先输出并提交：
- `docs/PRD.md`
- `docs/ARCH.md`
- `docs/STATE_MACHINE.md`
- `docs/API.md`
- `docs/DB_SCHEMA.md`
- `docs/SCORING.md`
- `docs/TEST_PLAN.md`

我确认后再进入编码阶段。

---

## 14. 开发里程碑（严格按顺序）

### M1 基建
- 初始化前后端工程
- Docker Compose 跑通
- MySQL + Redis 连接可用

### M2 房间与会话
- 创建房间、加入房间
- host_secret/player_token 机制
- WS 房间广播

### M3 游戏状态机
- 阶段迁移与主持人控制
- 发言顺序（随机/顺序）

### M4 投票与猜词
- 投票、平票加赛、出局公开身份
- 猜词次数与终局判定

### M5 积分与排名
- 每轮积分
- 局结算积分
- 底部排行榜实时更新

### M6 前端完善
- 主持人控制台完整交互
- 玩家端移动体验优化

### M7 测试与发布
- 自动化测试
- README 与演示脚本
- 交付验收

---

## 15. 每个里程碑的汇报模板（必须按此输出）

- 已完成功能：
- 新增/修改文件：
- 接口变更：
- 自测结果（含截图或日志）：
- 风险与待确认项：
- 下一步计划：

---

## 16. 验收标准（DoD）

- 内网环境可一键启动
- 主持人能完整控制整局流程
- 玩家端权限隔离正确
- 出局身份公开逻辑正确
- 猜词命中可立即结束游戏
- 排行榜在两端底部实时同步
- 连续多局稳定运行

---

## 17. README 首页一句话描述（固定文案）

这是一个面向线下朋友局的“谁是卧底”Web 辅助系统：无登录、重流程、强同步，用于主持控场、回合推进、计分与实时排名展示。

---

## 实现与运行（当前仓库）

当前仓库已提供可运行首版：
- 前端：`web`（Vue3 + TS + Vite + Pinia + Element Plus）
- 后端：`python`（FastAPI + SQLAlchemy）
- 部署：根目录 `docker-compose.yml`（frontend/backend/mysql/redis）
- 文档：根目录 `docs/*.md`

### 5 分钟本地启动

方式 A：Docker Compose
```bash
docker compose up --build
```

方式 B：本地开发
```bash
# backend
cd python
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# frontend
cd web
npm install
npm run dev
```

访问：
- 前端 `http://localhost:5173`
- 后端 `http://localhost:8000`