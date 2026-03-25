# Sidecar 迁移地图 (Refactor Map)

> 基于 `feat/0.0.1` vs `upstream/main` 的 diff 分析，记录所有未迁移功能的状态、迁移策略和优先级。
>
> **已迁移** = 已在 `ava/` 中实现 Monkey Patch
> **未迁移** = 仍然只存在于 `feat/0.0.1` 的 `nanobot/` 修改中
>
> 最后更新：2026-03-25（cafeext → ava 重命名，Phase 2&3 完成）

---

## 迁移状态总览

| 状态 | 数量 | 说明 |
|------|------|------|
| ✅ 已迁移 | 13 组 | Phase 1 + Phase 2&3 全部完成 |
| 🟡 部分迁移 | 3 组 | 模块在 ava/ 但未接入 AgentLoop |
| 🔴 待迁移（需 Fork） | 2 组 | loop.py / session/manager.py 深度修改 |
| ⚪ 无需迁移 | 多个 | feat/0.0.1 删除的模块 |

---

## ✅ 已迁移（Phase 1 + Phase 2&3 — 已完成）

| 功能 | 源文件 | ava/ 位置 | Patch / 文件 |
|------|--------|-----------|-------------|
| 5 个自定义工具 | `nanobot/agent/tools/{claude_code,image_gen,vision,sticker,memory_tool}.py` | `ava/tools/` | `tools_patch.py` |
| Web Console 后端 | `nanobot/console/` (24 文件) | `ava/console/` | `console_patch.py` ✅ 已修复 |
| SQLite 存储层 | `nanobot/storage/database.py` | `ava/storage/database.py` | `storage_patch.py` |
| 消息批处理器 | `nanobot/channels/batcher.py` | `ava/channels/batcher.py` | `channel_patch.py` ✅ 已修复 |
| Session Backfill | `nanobot/session/backfill_turns.py` | `ava/session/backfill_turns.py` | `channel_patch.py` |
| Skills & 模板 | `nanobot/skills/`, `nanobot/templates/` | `ava/skills/`, `ava/templates/` | 静态文件 |
| **Config Schema Fork** | `nanobot/config/schema.py` (+393行) | `ava/forks/config/schema.py` | `a_schema_patch.py` ✅ NEW |
| **AgentLoop 属性注入** | — | `ava/patches/loop_patch.py` | `loop_patch.py` ✅ NEW |
| **Token 统计接入** | `nanobot/agent/loop.py` usage | `ava/patches/loop_patch.py` | `loop_patch.py` ✅ NEW |
| **Bus Console Listener** | `nanobot/bus/queue.py` (+43行) | `ava/patches/bus_patch.py` | `bus_patch.py` ✅ NEW |
| **分类记忆系统** | `nanobot/agent/categorized_memory.py` (+247行) | `ava/agent/categorized_memory.py` | 🟡 已复制未接入 |
| **历史压缩器** | `nanobot/agent/history_compressor.py` (+205行) | `ava/agent/history_compressor.py` | 🟡 已复制未接入 |
| **历史摘要器** | `nanobot/agent/history_summarizer.py` (+174行) | `ava/agent/history_summarizer.py` | 🟡 已复制未接入 |
| **统一命令系统** | `nanobot/agent/commands.py` (+371行) | `ava/agent/commands.py` | 🟡 已复制未接入 |

---

## 🟡 已复制但未接入 AgentLoop（下一步）

这些模块已在 `ava/agent/` 中，但还没有通过 patch 注入到 `AgentLoop`：

### 分类记忆 / 历史压缩 / 历史摘要
- **需要**: patch `AgentLoop.__init__` 构造并赋值 `self.categorized_memory`、`self.history_compressor`、`self.history_summarizer`
- **需要**: patch `AgentLoop._process_message` 在 build_messages 前应用压缩/摘要
- **依赖**: `ContextBuilder.build_messages` 签名（需要传入 channel/chat_id）

### CommandRegistry
- **需要**: patch `AgentLoop.__init__` 替换 `self.commands`（当前是 `CommandRouter`）为 `CommandRegistry`
- **依赖**: `CommandRegistry` 与 `InboundMessage` / `AgentLoop` 的集成

---

## 🔴 仍需 Fork（暂缓，等接口稳定）

### loop.py 完整重构（暂缓）
- **源文件**: `nanobot/agent/loop.py` (+997行变更)
- **核心变更**: 多模型支持、HistoryCompressor 集成、token_stats 直接注入、工具结果字符限制 16000→500
- **当前状态**: 通过 `loop_patch.py` 已覆盖最关键部分（token_stats注入、usage记录）
- **剩余缺口**: `context_compression`、`in_loop_truncation`、`memory_window` 参数

### session/manager.py 重构（暂缓）
- **源文件**: `nanobot/session/manager.py` (+366行变更)
- **核心变更**: `last_completed` 截断逻辑、`get_history()` 重写
- **当前状态**: storage_patch 已覆盖 SQLite 读写，但 `last_completed` 截断未实现

---

## ⚠️ .nanobot/config.json 兼容性问题

运行 `python -m ava` 时，`a_schema_patch` 会用 fork schema 替换 `nanobot.config.schema`。
fork schema 新增了若干字段，**config.json 中有些字段路径也发生了变化**：

### 需要在 config.json 中新增/确认的字段

| 字段路径（camelCase） | 说明 | 当前状态 |
|----------------------|------|---------|
| `gateway.console.enabled` | Console 是否启用 | ❌ 缺失，fork schema 默认 `true` |
| `gateway.console.port` | Console 端口（fork schema default: 6688） | ❌ 缺失，当前由 `CAFE_CONSOLE_PORT` env var 控制（默认18791） |
| `gateway.console.secretKey` | JWT 密钥 | ❌ 缺失，使用默认值（不安全） |
| `agents.defaults.visionModel` | ✅ 已有 | `google/gemini-3.1-flash-lite-preview` |
| `agents.defaults.miniModel` | ✅ 已有 | `google/gemini-3.1-pro-preview` |
| `agents.defaults.voiceModel` | ✅ 已有 | `google/gemini-3.1-flash-lite-preview` |
| `agents.defaults.imageGenModel` | ✅ 已有 | `google/gemini-3.1-flash-image-preview` |
| `tools.claudeCode` | ✅ 已有 | fork schema 里是 `tools.claude_code`（snake_case），camelCase 别名兼容 |
| `tokenStats.enabled` | ✅ 已有 | fork schema 有 `token_stats` 字段 |

### 建议在 config.json 中添加

```json
"gateway": {
  "host": "0.0.0.0",
  "port": 18790,
  "console": {
    "enabled": true,
    "port": 18791,
    "secretKey": "<your-secret-key>"
  }
}
```

---

## ⚪ 无需迁移（feat/0.0.1 中删除的模块）

| 模块 | 行数 | 说明 |
|------|------|------|
| `nanobot/channels/weixin.py` | -1032 | 个人微信渠道，已删除 |
| `nanobot/channels/wecom.py` | -370 | 企业微信渠道，已删除 |
| `nanobot/channels/registry.py` | -71 | 渠道自动发现机制，已删除 |
| `nanobot/cli/onboard.py` | -1023 | 交互式入职向导，已删除 |
| `nanobot/cli/stream.py` | -128 | 流式渲染器，已删除 |
| `nanobot/command/` | -200 | 旧命令路由系统，被 `commands.py` 替代 |

---

## 📊 非 Python 文件（待评估）

| 类别 | 文件 | 状态 |
|------|------|------|
| Console UI (前端) | `console-ui/` (80+ 文件) | 未迁移，独立 React 项目，需单独部署 |
| Docker | `Dockerfile`, `docker-compose.yml` | 需适配 `python -m ava` 入口 |
| CI/CD | `.github/workflows/ci.yml` | 需适配 |
| Bridge | `bridge/src/` (WhatsApp Node.js) | 未迁移 |

---

## 🗓️ 当前进度与下一步

```
Phase 1 ✅ (已完成)
  └─ Sidecar 骨架 + 5 工具 + Console + Storage + Batcher + Backfill + Skills

Phase 2 ✅ (已完成 2026-03-25)
  └─ Schema Fork + Config Patch + Bus Listener + Loop Patch (token_stats)
  └─ console_patch 修复 + channel_patch 修复
  └─ categorized_memory / history_compressor / history_summarizer / commands 已复制

Phase 3 — 下一步
  ├─ 接入分类记忆到 AgentLoop（loop_patch 扩展）
  ├─ 接入历史压缩器/摘要器到 AgentLoop
  ├─ config.json 添加 gateway.console 配置
  └─ Console UI 前端部署适配
```
