# Sidecar 迁移地图 (Refactor Map)

> 基于 `feat/0.0.1` vs `upstream/main` 的 diff 分析，记录所有未迁移功能的状态、迁移策略和优先级。
>
> **已迁移** = 已在 `ava/` 中实现 Monkey Patch
> **未迁移** = 仍然只存在于 `feat/0.0.1` 的 `nanobot/` 修改中
>
> 最后更新：2026-03-26（Phase 3 完成，Gateway+Console UI 可运行，Docker/CI 已适配）

---

## 迁移状态总览

| 状态 | 数量 | 说明 |
|------|------|------|
| ✅ 已迁移 | 16 组 | Phase 1 + 2 + 3 全部完成 |
| 🟡 暂缓 | 3 组 | CommandRegistry / loop.py Fork / session Fork |
| ⚪ 无需迁移 | 多个 | feat/0.0.1 删除的模块 |

---

## ✅ 已迁移（Phase 1 + 2 + 3 — 已完成）

| 功能 | ava/ 位置 | Patch |
|------|-----------|-------|
| 5 个自定义工具 | `ava/tools/` | `tools_patch.py` |
| Web Console 后端（standalone 模式） | `ava/console/` | `console_patch.py` |
| SQLite 存储层 + Session Backfill | `ava/storage/` | `storage_patch.py` |
| 消息批处理器 | `ava/channels/batcher.py` | `channel_patch.py` |
| Session Backfill | `ava/session/backfill_turns.py` | `storage_patch.py`（集成） |
| Skills & 模板 | `ava/skills/`, `ava/templates/` | 静态文件 |
| Config Schema Fork | `ava/forks/config/schema.py` | `a_schema_patch.py` |
| Config 降级注入 | — | `b_config_patch.py` |
| AgentLoop 属性注入 + Token 统计 | `ava/patches/loop_patch.py` | `loop_patch.py` |
| Bus Console Listener | `ava/patches/bus_patch.py` | `bus_patch.py` |
| 分类记忆系统 | `ava/agent/categorized_memory.py` | `loop_patch.py` + `context_patch.py` |
| 历史压缩器 | `ava/agent/history_compressor.py` | `loop_patch.py` + `context_patch.py` |
| 历史摘要器 | `ava/agent/history_summarizer.py` | `loop_patch.py` + `context_patch.py` |
| ContextBuilder 增强 | `ava/patches/context_patch.py` | `context_patch.py` |
| Config Loader 绑定 | `a_schema_patch.py`（更新 loader.Config） | — |
| Console Standalone 模式 | `console_patch.py` | HTTP 反向代理到 Gateway |

### 9 个 Patch 执行顺序

```
a_schema_patch → b_config_patch → bus_patch → channel_patch → console_patch
→ context_patch → loop_patch → storage_patch → tools_patch
```

---

## 🟡 暂缓

### CommandRegistry（P2，等需求驱动）
- **位置**: `ava/agent/commands.py`（已复制）
- **原因**: 深度依赖 AgentLoop 内部属性（`_consolidation_locks`、`_compression_enabled`、`memory_window` 等），需 Fork loop.py 后才能接入
- **当前状态**: 上游 `CommandRouter` 已提供 `/help`、`/new` 等基础命令，够用

### loop.py 完整重构（P3）
- **源文件**: `nanobot/agent/loop.py` (+997行变更)
- **当前覆盖**: `loop_patch.py` 已注入 db/token_stats/media_service/categorized_memory/summarizer/compressor
- **剩余缺口**: `context_compression` 开关、`in_loop_truncation`、多模型切换
- **暂缓原因**: 等接口稳定，当前 patch 已覆盖核心功能

### session/manager.py 重构（P3）
- **源文件**: `nanobot/session/manager.py` (+366行变更)
- **当前覆盖**: `storage_patch.py` 已替换 SQLite 读写 + backfill
- **剩余缺口**: `last_completed` 截断逻辑、`get_history()` 重写

---

## ⚪ 无需迁移（feat/0.0.1 中删除的模块）

| 模块 | 说明 |
|------|------|
| `nanobot/channels/weixin.py` | 个人微信渠道，已删除 |
| `nanobot/channels/wecom.py` | 企业微信渠道，已删除 |
| `nanobot/channels/registry.py` | 渠道自动发现，已删除 |
| `nanobot/cli/onboard.py` | 交互式向导，已删除 |
| `nanobot/cli/stream.py` | 流式渲染器，已删除 |
| `nanobot/command/` | 旧命令路由，被 CommandRouter 替代 |

---

## 📊 非 Python 文件

| 类别 | 状态 |
|------|------|
| Console UI 前端 (`console-ui/`) | ✅ 已从 feat/0.0.1 提取，`npm run build` 验证通过 |
| Docker | ✅ Dockerfile 已适配（`python -m ava` 入口 + console-ui 构建） |
| CI/CD | ✅ 已添加 `refactor/sidecar` 触发 + `console-ui` 构建 job |
| Bridge (WhatsApp Node.js) | ✅ 已有（Dockerfile 中已集成构建） |

---

## 🗓️ 当前进度

```
Phase 1 ✅  Sidecar 骨架 + 5 工具 + Console + Storage + Batcher + Backfill + Skills
Phase 2 ✅  Schema Fork + Config Patch + Bus Listener + Loop Patch
Phase 3 ✅  分类记忆 + 历史压缩/摘要 + Gateway 启动修复 + Console UI + Docker/CI
             └─ Gateway :18790 + Console :6688 + Telegram + Cron + Heartbeat
             └─ 638 tests passed

待做（按需）：
  └─ CommandRegistry / loop.py Fork / session Fork
```
