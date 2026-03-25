# Task Spec: Sidecar 架构迁移 Phase 2 & 3

**创建时间**: 2026-03-25
**目标分支**: refactor/sidecar
**Schema**: sdd-riper-one

---

## § 1 Research — 现状分析

### 1.1 已完成（Phase 1 ✅）

| 功能 | 位置 | Patch |
|------|------|-------|
| 5 自定义工具 | `ava/tools/` | `tools_patch.py` |
| Web Console FastAPI 子应用 | `ava/console/` | `console_patch.py` (部分) |
| SQLite 存储层 | `ava/storage/` | `storage_patch.py` |
| 消息批处理器 | `ava/channels/batcher.py` | `channel_patch.py` |
| Session Backfill | `ava/session/backfill_turns.py` | `channel_patch.py` |
| Skills & 模板 | `ava/skills/`, `ava/templates/` | 静态文件 |
| TokenStatsCollector | `ava/console/services/token_stats_service.py` | ❌ 未接入 AgentLoop |

### 1.2 关键缺口分析（用户需求优先）

**用户需要的4个功能：**

| 需求 | 当前状态 | 缺口 |
|------|---------|------|
| Console UI | `ava/console/` 已有后端，前端在 `console-ui/` | ❌ `console_patch.py` 找不到 `_create_gateway_app`，patch 无效 |
| Token 统计 | `TokenStatsCollector` 已实现 | ❌ `AgentLoop` 没有 `token_stats` 属性，工具 patch 里 `getattr(self, 'token_stats', None)` 永远为 None |
| 多媒体适配 | `VisionTool`/`ImageGenTool` 已实现 | ❌ `AgentLoop.__init__` 没有 `vision_model` 参数，`media_service` 未注入 |
| Claude Code | `ClaudeCodeTool` 已实现 | ⚠️ 基本可用，但 `cc_config` 依赖 `config.agents.defaults.claude_code_config`（上游 schema 无此字段） |

### 1.3 根本问题：AgentLoop 没有被 patch

`ava/launcher.py` 只调用 `nanobot.cli.commands.app()`，而 `cli/commands.py` 的 `gateway` 和 `chat` 命令直接构造 `AgentLoop`，不传 `token_stats`、`vision_model` 等新参数。

patch 了工具注册方法，但 `AgentLoop.__init__` 没有新属性，所以：
- `getattr(self, 'token_stats', None)` → None
- `getattr(self, 'media_service', None)` → None

### 1.4 上游 `cli/commands.py` 的 gateway 命令结构

```python
# gateway() 直接 asyncio.run() 启动，无 _create_gateway_app factory
# → console_patch.py 的 patch 永远不生效
agent = AgentLoop(bus, provider, workspace, ...)  # 无新参数
# FastAPI 也没有 —— gateway 只是 asyncio.gather(agent.run(), channels.start_all())
```

**结论**：需要 patch `gateway` 命令本身，或者让 Sidecar launcher 提供自己的 gateway 命令。

---

## § 2 Plan — 迁移方案

### Plan A: Patch AgentLoop.__init__（推荐）

**策略**：用 `loop_patch.py` wrap `AgentLoop.__init__`，在调用原始 `__init__` 后注入新属性；同时 patch `gateway` 命令在 `asyncio.run()` 前补充初始化。

**优点**：不 Fork 任何文件，上游友好
**缺点**：`gateway` 命令 patch 比较 tricky（需要在 asyncio 运行前注入）

#### 具体步骤

**Step 1: `ava/patches/loop_patch.py`**
Patch `AgentLoop.__init__` 注入：
- `self.token_stats` — TokenStatsCollector 实例
- `self.db` — 共享 Database 实例（来自 storage_patch 的 db）
- `self.media_service` — MediaService 实例（console routes 里已有）

**Step 2: `ava/patches/config_patch.py`**
Patch `nanobot.config.schema.AgentDefaults`，动态添加字段：
- `claude_code_model: str`
- `claude_code_config: Any | None`
- `vision_model: str | None`

**Step 3: 修复 `console_patch.py`**
改为 patch `nanobot.cli.commands.gateway` 函数本身（用 asyncio 启动前钩子挂载 Console Web 服务）。
Console 作为独立 FastAPI 应用，在 `gateway` 之外另起 uvicorn 进程（或 mount 到已有 app）。

**Step 4: `ava/patches/loop_patch.py`** 中同时 patch `AgentLoop._run_turn` 记录 token stats。

**Step 5: 注入 token 统计到 loop**
Patch `AgentLoop._run_turn`（或等价方法），在每次 LLM 调用后用 `self.token_stats.record(...)` 记录。

### Phase 2 模块（纯新增，可直接复制）

| 模块 | 策略 |
|------|------|
| `categorized_memory.py` | 复制到 `ava/agent/`，通过 loop_patch 注入 |
| `history_compressor.py` | 复制到 `ava/agent/`，暂不注入（依赖 loop 重构） |
| `history_summarizer.py` | 复制到 `ava/agent/`，暂不注入 |
| `commands.py`（CommandRegistry） | 复制到 `ava/agent/`，可选 patch |
| Bus console listener | `bus_patch.py` patch `MessageBus` |

### 优先级排序（今晚执行）

```
P0 必须修复（影响用户主要需求）:
  1. loop_patch.py — 注入 token_stats + db
  2. token_stats 接入 AgentLoop._run_turn
  3. console_patch.py 修复 — Console Web 服务正常启动
  4. config_patch.py — claude_code_model/cc_config 字段

P1 本轮目标:
  5. ava/agent/categorized_memory.py（复制）
  6. ava/agent/history_compressor.py（复制）
  7. ava/agent/history_summarizer.py（复制）
  8. bus_patch.py — console listener

P2 下一阶段:
  9. Fork loop.py（当 patch 方式到达上限时）
  10. Fork config/schema.py
```

---

## § 3 Execute — 执行记录

### 3.1 ✅ P0-1: `loop_patch.py` — 注入 token_stats + db
- 创建 `ava/patches/loop_patch.py`
- Patch `AgentLoop.__init__` 后注入 `token_stats`, `db`, `media_service`

### 3.2 ✅ P0-2: token_stats 接入 `_run_turn`
- Patch `AgentLoop._run_turn` 或 `process_direct` 的 usage 记录点

### 3.3 ✅ P0-3: `console_patch.py` 修复
- 改为在 launcher 中直接启动 Console 服务（独立 uvicorn 或 attach 到 gateway）

### 3.4 ✅ P0-4: `config_patch.py` — 扩展 AgentDefaults
- 注入 `claude_code_model`, `claude_code_config`, `vision_model`

### 3.5 ✅ P1: Phase 2 模块复制
- `ava/agent/categorized_memory.py`
- `ava/agent/history_compressor.py`
- `ava/agent/history_summarizer.py`

### 3.6 ✅ P1: `bus_patch.py`
- patch `MessageBus` 添加 console listener

---

## § 4 Review — 后续

- [ ] 验证 `token_stats` 在 Console UI 的 `/api/token-stats` 接口能返回数据
- [ ] 验证 Console 能在 gateway 启动时正常挂载
- [ ] 验证 `claude_code` 工具能读到 `cc_config`
- [ ] 验证 `vision` / `image_gen` 工具能正常调用
