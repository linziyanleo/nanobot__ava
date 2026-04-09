---
specanchor:
  level: global
  type: api-conventions
  version: "1.0.0"
  author: "Ziyan Lin"
  reviewers: []
  last_synced: "2026-04-09"
  last_change: "按 FastAPI console 与 aiohttp OpenAI-compatible API 统一接口约定"
  applies_to: "**/*.py"
---

# API 设计约定

## 请求封装
- Console HTTP 接口统一定义在 `ava.console.routes.*`，使用 `APIRouter(prefix=\"/api/<domain>\")`
- 请求 / 响应模型集中在 `ava.console.models`，路由层优先接收 `BaseModel` 而不是裸 dict
- 需要用户态隔离的读取统一经 `get_services_for_user(user)`；全局管理能力经 `get_services()`

## 鉴权与权限
- HTTP 优先走 session cookie，其次兼容 `Authorization: Bearer <token>`
- 角色约束统一通过 `auth.require_role(...)` 或 `auth.get_current_user` / `get_ws_user`
- 无认证健康检查仅限 `/health` 这类 supervisor 探针，不向业务写接口扩散

## 错误处理
- FastAPI 路由抛 `HTTPException`；aiohttp API 通过 `_error_json()` 返回结构化错误
- 返回体保持可序列化 dict / Pydantic `model_dump()`，避免泄露内部对象
- 需要审计的写操作先记录 audit，再触发实际副作用

## 接口命名
- Console 领域接口采用 `/api/<domain>/<action>` 语义；OpenAI-compatible API 固定 `/v1/*`
- WebSocket 与 HTTP 共享同一套 token 载荷结构，不引入额外角色字段分叉
