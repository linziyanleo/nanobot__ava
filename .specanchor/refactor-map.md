# Sidecar 迁移地图 (Refactor Map)

> 基于 `feat/0.0.1` vs `upstream/main` 的 diff 分析，记录所有未迁移功能的状态、迁移策略和优先级。
>
> **已迁移** = 已在 `cafeext/` 中实现 Monkey Patch  
> **未迁移** = 仍然只存在于 `feat/0.0.1` 的 `nanobot/` 修改中

---

## 迁移状态总览

| 状态 | 数量 | 说明 |
|------|------|------|
| ✅ 已迁移 | 6 组 | 通过 Sidecar Monkey Patch 完成 |
| 🔶 待迁移（可 Patch） | 5 组 | 独立模块，可通过 Monkey Patch 迁移 |
| 🔴 待迁移（需 Fork） | 5 组 | 深度修改上游核心逻辑，需要 Fork 方式 |
| ⚪ 删除/清理 | 4 组 | feat/0.0.1 中删除的上游模块，无需迁移 |

---

## ✅ 已迁移（Phase 1 — 已完成）

| 功能 | 源文件 | Sidecar 位置 | Patch |
|------|--------|-------------|-------|
| 5 个自定义工具 | `nanobot/agent/tools/{claude_code,image_gen,vision,sticker,memory_tool}.py` | `cafeext/tools/` | `tools_patch.py` |
| Web Console | `nanobot/console/` (24 文件) | `cafeext/console/` | `console_patch.py` |
| SQLite 存储层 | `nanobot/storage/database.py` | `cafeext/storage/database.py` | `storage_patch.py` |
| 消息批处理器 | `nanobot/channels/batcher.py` | `cafeext/channels/batcher.py` | `channel_patch.py` |
| Session Backfill | `nanobot/session/backfill_turns.py` | `cafeext/session/backfill_turns.py` | `channel_patch.py` |
| Skills & 模板 | `nanobot/skills/`, `nanobot/templates/` | `cafeext/skills/`, `cafeext/templates/` | 静态文件 |

---

## 🔶 Phase 2 — 可 Monkey Patch 迁移

### 2.1 分类记忆系统
- **源文件**: `nanobot/agent/categorized_memory.py` (+247 行，纯新增)
- **功能**: 基于身份的分类记忆，`IdentityResolver` 通过 `identity_map.yaml` 解析 channel:chat_id → 人名映射，`CategorizedMemoryStore` 为每个用户维护独立记忆
- **依赖**: 无上游依赖，完全独立
- **迁移策略**: Monkey Patch — 放入 `cafeext/agent/categorized_memory.py`，通过 patch 注入到 `ContextBuilder`
- **难度**: ⭐ 简单
- **预估工时**: 1h

### 2.2 历史压缩器
- **源文件**: `nanobot/agent/history_compressor.py` (+205 行，纯新增)
- **功能**: 基于字符预算的历史压缩算法，保留最近轮次 + 轻量级相关性筛选，支持 auto-backfill 消息识别，术语提取（英文 + 中日韩）
- **依赖**: 无上游依赖，纯工具类
- **迁移策略**: Monkey Patch — 放入 `cafeext/agent/history_compressor.py`，patch `AgentLoop` 的消息处理流程
- **难度**: ⭐ 简单
- **预估工时**: 1h

### 2.3 历史摘要器
- **源文件**: `nanobot/agent/history_summarizer.py` (+174 行，纯新增)
- **功能**: 轮级历史摘要，将旧轮次压缩为 `[user, assistant]` 消息对，保留最近消息原始格式，特殊处理定时任务/贴纸 emoji/Cron 任务 ID
- **依赖**: 无上游依赖，纯工具类
- **迁移策略**: Monkey Patch — 放入 `cafeext/agent/history_summarizer.py`
- **难度**: ⭐ 简单
- **预估工时**: 1h

### 2.4 统一命令系统
- **源文件**: `nanobot/agent/commands.py` (+371 行，纯新增)
- **功能**: `CommandRegistry` 跨平台斜杠命令管理，`SlashCommand` 数据类，内置命令（归档快照、记忆管理、任务管理），支持 `pre_dispatch` 模式
- **依赖**: 依赖 `AgentLoop` 和 `InboundMessage`，但作为独立模块可替换旧的 `CommandRouter`
- **迁移策略**: Monkey Patch — 放入 `cafeext/agent/commands.py`，patch 替换旧命令路由
- **难度**: ⭐⭐ 中等
- **预估工时**: 2h

### 2.5 Bus Console Listener
- **源文件**: `nanobot/bus/queue.py` (+43 行变更)
- **功能**: 新增 console listener 机制，支持 WebSocket 推送异步任务结果，`register_console_listener()` / `unregister_console_listener()` / `dispatch_to_console_listener()`
- **依赖**: 与 Console WebSocket 集成
- **迁移策略**: Monkey Patch — patch `MessageBus` 添加 listener 方法
- **难度**: ⭐⭐ 中等
- **预估工时**: 1.5h

---

## 🔴 Phase 3 — 需要 Fork 修改

### 3.1 AgentLoop 核心重构
- **源文件**: `nanobot/agent/loop.py` (+997 行变更)
- **变更内容**:
  - 多模型支持：`vision_model`、`mini_model`、`voice_model`
  - 集成 `CommandRegistry` 替代 `CommandRouter`
  - 引入 `HistoryCompressor`、`HistorySummarizer`
  - 新增参数：`temperature`、`max_tokens`、`memory_window`、`reasoning_effort`、`brave_api_key`、`context_compression`、`in_loop_truncation`、`token_stats`、`record_full_request_payload`、`db`
  - 移除旧配置：`context_window_tokens`、`web_search_config`
  - 工具结果字符限制从 16,000 降至 500
- **为什么不能 Patch**: 深度修改了 `__init__` 签名、消息处理循环、工具集成方式，Monkey Patch 会过于脆弱
- **迁移策略**: Fork `nanobot/agent/loop.py`，在 Sidecar 中维护定制版本
- **难度**: ⭐⭐⭐⭐⭐ 困难
- **预估工时**: 8h
- **风险**: 上游更新时需要手动合并

### 3.2 Subagent 任务持久化
- **源文件**: `nanobot/agent/subagent.py` (+1119 行变更)
- **变更内容**:
  - SQLite 任务历史持久化（`history_tasks.db`）
  - 活跃任务追踪（`active_tasks.txt` 文件锁）
  - Claude Code 集成参数
  - `fcntl` 文件锁并发控制
  - 任务状态管理：启动/结束时间、持续时间、错误追踪
  - 任务目录：`~/.nanobot/tasks/`
- **为什么不能 Patch**: 深度修改了 Subagent 管理逻辑，引入全新持久化层和并发控制
- **迁移策略**: Fork `nanobot/agent/subagent.py`
- **难度**: ⭐⭐⭐⭐⭐ 困难
- **预估工时**: 6h

### 3.3 Session Manager 重构
- **源文件**: `nanobot/session/manager.py` (+366 行变更)
- **变更内容**:
  - 从 JSONL 迁移到 SQLite 作为主存储（JSONL 作为 legacy fallback）
  - 新增 `last_completed` 字段追踪最后完整用户轮次
  - 新增 `token_stats` 字段
  - `get_history()` 基于 `last_completed` 截断
  - 移除 `retain_recent_legal_suffix()`
- **为什么不能 Patch**: 已有 `storage_patch.py` 处理存储层，但 `get_history()` 逻辑重构和 `last_completed` 机制需要更深层修改
- **迁移策略**: Fork `nanobot/session/manager.py`，与 `storage_patch.py` 协同
- **难度**: ⭐⭐⭐⭐ 困难
- **预估工时**: 4h

### 3.4 CLI Commands 重构
- **源文件**: `nanobot/cli/commands.py` (+1460 行变更)
- **变更内容**:
  - Gateway 单实例保护（PID 文件）
  - 移除 `StreamRenderer` 和 `ThinkingSpinner`
  - 重构控制台输出逻辑
  - 集成 Console、SQLite、多模型等新功能的启动参数
- **为什么不能 Patch**: 是 CLI 入口，几乎每个新功能都需要在这里添加启动参数
- **迁移策略**: Fork `nanobot/cli/commands.py`，Sidecar launcher 已部分替代
- **难度**: ⭐⭐⭐⭐ 困难
- **预估工时**: 6h

### 3.5 Config Schema 扩展
- **源文件**: `nanobot/config/schema.py` (+393 行变更)
- **变更内容**:
  - 集中管理所有渠道 Config 类（`TelegramConfig`、`FeishuConfig` 等）
  - 新增多模型配置字段
  - 新增 Console 配置
  - 统一配置结构
- **为什么不能 Patch**: Pydantic 模型的字段定义无法通过 Monkey Patch 安全修改
- **迁移策略**: Fork `nanobot/config/schema.py`
- **难度**: ⭐⭐⭐ 中等
- **预估工时**: 3h

---

## 🟡 Phase 4 — 上游修改（需逐个评估）

### 4.1 Context Builder 扩展
- **源文件**: `nanobot/agent/context.py` (+186 行变更)
- **变更**: 集成分类记忆、新增 `channel`/`chat_id` 参数、活跃任务状态显示
- **策略**: 可尝试 Monkey Patch `build_system_prompt` 方法，或 Fork
- **难度**: ⭐⭐⭐ 中等

### 4.2 Memory 系统重构
- **源文件**: `nanobot/agent/memory.py` (+441 行变更)
- **变更**: 移除 `MemoryConsolidator`，新增 `SELF_MEMORY.md`，重构 `_SAVE_MEMORY_TOOL`
- **策略**: Fork — 移除了大量逻辑且修改了工具定义
- **难度**: ⭐⭐⭐ 中等

### 4.3 Channels 模块修改
- **文件**: `base.py`、`manager.py`、`telegram.py`、`feishu.py`、`qq.py`、`email.py` 等
- **变更**: 移除 Config 类定义（移至 schema.py）、移除 `display_name`、移除流式支持、简化初始化
- **策略**: 与 Config Schema Fork 配合，逐个渠道适配
- **难度**: ⭐⭐⭐ 中等

### 4.4 Cron/Heartbeat 增强
- **文件**: `cron/service.py` (+309)、`cron/types.py` (+6)、`heartbeat/service.py` (+80)
- **变更**: model_tier 支持、任务完成追踪、双模型 heartbeat
- **策略**: 可 Monkey Patch — 变更相对独立
- **难度**: ⭐⭐ 中等

### 4.5 Tools 上游修改
- **文件**: `filesystem.py` (+376)、`web.py` (+380)、`shell.py` (+110)、`cron.py` (+104)、`mcp.py` (+49)、`message.py` (+7)、`spawn.py` (+22)
- **变更**: 移除 `list_file`、简化 web 搜索（仅 DuckDuckGo）、新增 `auto_venv`、model_tier 支持
- **策略**: 逐个评估 — 部分可 Patch，部分需 Fork
- **难度**: ⭐⭐ 中等

### 4.6 Providers 简化
- **文件**: `base.py` (+268)、`azure_openai_provider.py` (+103)、`openai_codex_provider.py` (+120)、`registry.py` (+44)
- **变更**: 移除流式支持、移除重试逻辑、简化接口、新增 Zenmux 提供商
- **策略**: Fork — 接口签名变更
- **难度**: ⭐⭐⭐ 中等

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
| `nanobot/security/network.py` | -104 | SSRF 防护，已删除（⚠️ 安全风险） |
| `nanobot/utils/evaluator.py` | -92 | 后台任务响应评估，已删除 |
| `nanobot/utils/helpers.py` | -188 | 工具函数，已内联或删除 |
| `nanobot/config/__init__.py` | -2 | 移除导出 |
| `nanobot/config/paths.py` | -7 | 移除路径常量 |

---

## 📊 非 Python 文件（待评估）

| 类别 | 文件 | 状态 |
|------|------|------|
| Console UI (前端) | `console-ui/` (80+ 文件) | 未迁移，独立 React 项目 |
| Workspace Skills | `workspace/skills/` (多个 Skill) | 未迁移，运行时文件 |
| Docker | `Dockerfile`, `docker-compose.yml` | 需适配 Sidecar 入口 |
| CI/CD | `.github/workflows/ci.yml` | 需适配 |
| Bridge | `bridge/src/` (WhatsApp Node.js) | 未迁移 |
| 配置模板 | `config.json.template`, `extra_config.json.template` | 需适配 |
| 测试 | `tests/` (40+ 文件) | 需适配 Sidecar 架构 |

---

## 🗓️ 建议迁移路线

```
Phase 1 ✅ (已完成)
  └─ Sidecar 骨架 + 5 工具 + Console + Storage + Batcher + Backfill + Skills

Phase 2 (1-2 天)
  └─ 分类记忆 + 历史压缩器 + 历史摘要器 + 命令系统 + Bus Listener
  └─ 全部可通过 Monkey Patch 实现

Phase 3 (3-5 天)
  └─ Fork: loop.py + subagent.py + session/manager.py + cli/commands.py + config/schema.py
  └─ 需要仔细处理上游合并冲突

Phase 4 (2-3 天)
  └─ 逐个评估: context.py + memory.py + channels/* + cron/* + tools/* + providers/*
  └─ 混合策略: 部分 Patch + 部分 Fork

Phase 5 (1-2 天)
  └─ Console UI 前端 + Docker + CI/CD + 测试适配
```

---

## ⚠️ 风险提示

1. **上游合并冲突**: Fork 的文件在上游更新时需要手动合并，建议定期 rebase
2. **SSRF 防护移除**: `security/network.py` 被删除，需评估是否在 Sidecar 层重新实现
3. **流式支持移除**: Providers 和 Channels 的流式功能被删除，如需恢复需额外工作
4. **Session 数据迁移**: JSONL → SQLite 需要迁移脚本，确保数据不丢失
5. **多模型依赖链**: `model_tier` 贯穿 loop → cron → heartbeat → spawn，需要完整迁移才能生效
