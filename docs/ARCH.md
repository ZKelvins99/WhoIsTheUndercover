# 架构说明

## 前端
- Vue3 + TS + Vite + Pinia + Vue Router + Element Plus
- 通过 HTTP 调用 REST 接口
- 通过 WS 接收事件后触发 snapshot 增量恢复

## 后端
- FastAPI + SQLAlchemy + Pydantic
- 分层：router / service / model / core
- 错误码统一：`detail.code` + `detail.message`

## 存储
- MySQL（通过 SQLAlchemy 持久化）
- Redis（Compose 已提供，当前版本预留接入）

## 通信
- REST: 业务写接口与快照读取
- WS: 房间级事件广播，载荷含事件名与上下文
