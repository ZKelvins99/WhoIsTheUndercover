# 谁是卧底 - 线下聚会辅助工具

> 一次性使用的线下聚会游戏控制器，无需数据库服务器和中间件，开箱即用。

## 开发思路

### 架构设计
- **前端**：Vue 3 + TypeScript + Vite，提供主持人端和玩家端两个视图
- **后端**：FastAPI + Python，使用 SQLite 本地文件数据库
- **通信**：WebSocket 实现实时状态同步，HTTP 接口用于操作和查询
- **存储**：前端使用 cookie 保存会话信息（30天有效期），刷新页面可恢复状态

### 核心流程
1. 主持人创建房间 → 获得 6 位房间号和 host_secret
2. 玩家输入房间号 + 昵称加入 → 获得 player_token
3. 主持人开始游戏 → 系统随机分配身份
4. 游戏循环：发言 → 投票 → 猜词 → 结算 → 下一轮
5. 达到胜利条件 → 游戏结束，显示排行榜

### 状态机设计
游戏严格按照状态机流转，防止非法操作：
```
LOBBY → GAME_INIT → ROUND_SPEAKING → ROUND_VOTING → ROUND_GUESSING → ROUND_RESULT → 下一轮
                                    ↓ (平票)
                              ROUND_TIE_BREAK → ROUND_VOTING
```

## 游戏核心规则

### 角色分配
游戏开始时，系统随机分配以下角色：

| 角色 | 说明 | 词语 |
|------|------|------|
| **平民** | 拿到相同词语，通过发言找出卧底 | 平民词 |
| **卧底** | 拿到相似词语，隐藏身份不被发现 | 卧底词 |
| **白板** | 无固定词语，靠猜词获胜 | 无 |

### 胜利条件

#### 平民阵营胜利
- 通过投票淘汰所有卧底

#### 卧底阵营胜利（核心规则）
- **卧底人数 ≥ 平民人数时，卧底立即胜利**
- 例如：3平民 + 2卧底，淘汰1平民后变成2平民 + 2卧底，卧底胜利

#### 白板独立胜利
- 在猜词阶段猜中任意阵营的词语

### 游戏流程

#### 1. 发言阶段
- 主持人点击"下一位发言"，系统随机或按顺序选择发言人
- 每位玩家用语言描述自己的词语（不能直接说出词语）
- 所有人发言完成后自动进入投票阶段

#### 2. 投票阶段
- 每位存活玩家投一票给怀疑的卧底
- 票数最高者出局并公开身份
- **平票处理**：平票玩家补充发言，全员重新投票
- 二次平票：本轮无人出局，直接进入猜词阶段

#### 3. 猜词阶段
- 存活玩家可以猜测对方阵营的词语
- 平民/卧底：每轮 1 次猜词机会
- 白板：每轮 2 次猜词机会
- 猜中立即触发阵营胜利，游戏结束

#### 4. 结算阶段
- 显示本轮出局玩家身份
- 更新排行榜
- 检查是否达到胜利条件
- 未结束则进入下一轮

## 积分规则

### 每轮基础分

| 行为 | 积分 | 说明 |
|------|------|------|
| 存活到本轮结束 | +1 | 每轮自动获得 |
| 完成有效投票 | +1 | 投票给其他玩家（每局上限3分） |
| 投中敌对关键目标 | +2 | 投票给最终被确认出局的敌对阵营玩家（计入投票上限3分） |

### 局结算胜负分

#### 平民阵营胜利
| 状态 | 积分 |
|------|------|
| 存活平民 | +4 |
| 出局平民 | +2 |

#### 卧底阵营胜利
| 状态 | 积分 |
|------|------|
| 存活卧底 | +6 |
| 出局卧底 | +3 |

#### 白板胜利
| 情况 | 积分 |
|------|------|
| 猜中触发终局 | +8 |
| 未独立胜但存活到末轮 | +3 |

### 排名规则
1. 总分降序
2. 总分相同，按存活轮数降序
3. 存活轮数相同，按投中次数降序
4. 以上都相同，按加入顺序排序

## 快速启动

### 前置要求
- Python 3.8+
- Node.js 16+

### 启动步骤

```bash
# 1. 启动后端
cd python
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 2. 启动前端（新终端）
cd web
npm install
npm run dev
```

### 访问地址
- 前端：http://localhost:5173
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

## 使用流程

### 主持人操作
1. 打开前端，点击"创建房间"
2. 获得 6 位房间号，分享给玩家
3. 等待玩家加入（10-15人）
4. 设置词语（平民词和卧底词）
5. 点击"开始游戏"
6. 控制游戏流程：发言 → 投票 → 猜词 → 结算
7. 游戏结束后可查看排行榜或开始新一局

### 玩家操作
1. 打开前端，输入房间号和昵称
2. 等待游戏开始
3. 查看自己的身份和词语
4. 按主持人指示发言
5. 投票阶段选择怀疑的玩家
6. 猜词阶段猜测对方词语（可选）
7. 查看排行榜和游戏结果

## 客户端存储机制

前端使用 **cookie** 保存会话信息，刷新页面后可自动恢复：

| Cookie 名 | 有效期 | 说明 |
|-----------|--------|------|
| `host_secret` | 30天 | 主持人密钥，用于身份验证 |
| `player_token` | 30天 | 玩家令牌，用于身份验证 |
| `player_id` | 30天 | 玩家ID |

刷新页面后，前端会自动从 cookie 读取这些信息并请求快照接口，恢复当前游戏状态。

## 技术栈

- **前端**：Vue 3 + TypeScript + Vite + Element Plus
- **后端**：FastAPI + Python + SQLAlchemy
- **存储**：SQLite（本地文件数据库，无需安装数据库服务器）
- **通信**：WebSocket 实时同步 + HTTP 补偿拉取

## 项目结构

```
├── web/                    # 前端代码
│   ├── src/
│   │   ├── views/          # 页面组件
│   │   │   ├── Home.vue    # 首页（创建/加入房间）
│   │   │   ├── Host.vue    # 主持人控制台
│   │   │   └── Player.vue  # 玩家端
│   │   ├── stores/         # Pinia 状态管理
│   │   │   └── room.ts     # 房间状态存储
│   │   ├── api/            # API 接口
│   │   └── components/     # 公共组件
│   └── package.json
├── python/                 # 后端代码
│   ├── app/
│   │   ├── routers/        # API 路由
│   │   │   ├── room.py     # 房间相关接口
│   │   │   ├── game.py     # 游戏相关接口
│   │   │   └── ws.py       # WebSocket 接口
│   │   ├── services/       # 业务逻辑
│   │   │   └── game_service.py  # 核心游戏逻辑
│   │   ├── models/         # 数据库模型
│   │   └── core/           # 核心配置
│   └── requirements.txt
└── README.md
```

## API 接口

### 房间管理
- `POST /api/host/rooms` - 创建房间
- `POST /api/rooms/{roomCode}/join` - 加入房间
- `POST /api/rooms/{roomCode}/lock` - 锁房/解锁
- `POST /api/rooms/{roomCode}/kick/{playerId}` - 踢人

### 游戏控制（主持人）
- `POST /api/rooms/{roomCode}/games/start` - 开始游戏
- `POST /api/games/{gameId}/rounds/{roundNo}/speaking/next` - 下一位发言
- `POST /api/games/{gameId}/rounds/{roundNo}/phase/next` - 进入下一阶段
- `POST /api/games/{gameId}/finish` - 结束游戏

### 玩家操作
- `POST /api/games/{gameId}/rounds/{roundNo}/vote` - 投票
- `POST /api/games/{gameId}/rounds/{roundNo}/guess` - 猜词

### 查询接口
- `GET /api/rooms/{roomCode}/snapshot` - 获取房间快照
- `GET /api/rooms/{roomCode}/leaderboard` - 获取排行榜

## 注意事项

- 数据存储在 SQLite 文件中，重启后端不会丢失数据
- 适合 10-15 人的线下聚会使用
- 建议在同一局域网内使用
- 游戏过程中请勿刷新页面（虽然可以恢复，但会中断 WebSocket 连接）
- 主持人请妥善保管 host_secret，这是控制游戏的唯一凭证

## 开发说明

如需修改或扩展功能：
- 前端修改：`web/src/` 目录
- 后端修改：`python/app/` 目录
- API 接口：`python/app/routers/` 目录
- 游戏逻辑：`python/app/services/game_service.py`
