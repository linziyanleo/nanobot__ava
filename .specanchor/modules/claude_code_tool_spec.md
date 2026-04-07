# Module Spec: claude_code_tool — Claude Code CLI 工具、后台任务上下文与完成回调

> 相关文件：`ava/tools/claude_code.py`、`ava/tools/__init__.py`、`ava/patches/tools_patch.py`、`ava/patches/loop_patch.py`、`ava/patches/context_patch.py`、`ava/agent/bg_tasks.py`、`ava/agent/commands.py`、`ava/console/routes/chat_routes.py`、`ava/console/services/chat_service.py`、`ava/forks/config/schema.py`
> 状态：🟡 部分实现（sync 可用；async / 任务上下文 / 完成回调未闭环）（2026-04-04 v3）
> 架构决策：BackgroundTaskStore 模式（替代 v2 CodingTaskRegistry，替代 v1 subagent_patch）

---

## 1. 模块职责

把本地 `claude` CLI 封装成 Nanobot 可调用的 `claude_code` 工具，用于代码分析、修改和重构，并把执行结果以 Nanobot/console 可消费的形式回传。

当前真实边界：

- **已闭环**：同步执行链。
- **未闭环**：异步后台任务链、任务状态透出、IM 上下文注入、完成回调落盘。

这个模块不负责：

- 直接改 `nanobot/` 上游代码；
- 通用编程 CLI 抽象（Phase 2，通过 `CodingCLIBase` 实现）；
- 管理 cron/subagent 的上下文（由 BackgroundTaskStore 统一管理，claude_code 只是事件源之一）。

---

## 2. 调用链路

```text
AgentLoop._register_default_tools()
  -> tools_patch 注册 ClaudeCodeTool(task_store=self.bg_tasks)
  -> agent tool_call: claude_code(prompt, mode, ...)
  -> ClaudeCodeTool.execute()
     ├─ mode="sync"
     │   -> _execute_sync() → 阻塞执行 → 返回字符串给当前 turn
     └─ mode in {"fast","standard","readonly"}
         ├─ 当前实现：调 SubagentManager.spawn_claude_code(...)（缺失，断头）
         └─ 目标实现：调 BackgroundTaskStore.submit_coding_task(...)
             -> asyncio.Task 后台运行
             -> store.record_event(started/succeeded/failed)
             -> store._on_complete()
                 -> 写结果到 origin session history
                 -> publish_outbound → async_result → ChatPage reload
```

### 2.1 工具注册链

| 环节 | 说明 |
|------|------|
| `ava/patches/tools_patch.py` | 读取 `config.tools.claude_code` 并注册 `ClaudeCodeTool` |
| `ava/forks/config/schema.py` | 定义 `ClaudeCodeConfig`（model、max_turns、allowed_tools、timeout、api_key、base_url） |
| `ava/tools/__init__.py` | 导出 `ClaudeCodeTool` 供 patch 引用 |

### 2.2 同步执行链（不变）

| 步骤 | 入口 | 说明 |
|------|------|------|
| 参数接收 | `ClaudeCodeTool.execute()` | `mode="sync"` 时走阻塞执行 |
| 命令构造 | `_build_command()` | 构造 `claude -p ... --output-format json --model ... --max-turns ...` |
| 子进程执行 | `_run_subprocess()` | 注入 `ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL`，超时 kill |
| 结果解析 | `_parse_result()` | 反向扫描 stdout，取最后一个有效 JSON 行 |
| 统计记录 | `_record_stats()` | 写入 `TokenStatsCollector`，`provider="claude-code-cli"`、`model_role="claude_code"` |
| UI 结果 | `_format_output()` | 组装 `[Claude Code STATUS]` 文本给聊天记录和 console-ui 卡片消费 |

### 2.3 异步设计意图与目标架构（BackgroundTaskStore 模式）

| 设计意图 | 当前真实状态 | Phase 1 目标 |
|----------|-------------|--------------|
| 后台任务启动 | ❌ `spawn_claude_code` 缺失 | `BackgroundTaskStore.submit_coding_task()` |
| 任务取消 | ❌ `cancel_claude_code` 缺失 | `BackgroundTaskStore.cancel()` |
| 状态查询 | ❌ `get_claude_code_status` 缺失 | `BackgroundTaskStore.get_status()` |
| 上下文路由 | ⚠️ session_key 从 channel/chat_id 反推（console 场景错） | `origin_session_key` 一等字段，直传不反推 |
| IM 上下文 | ❌ 模型不知道有任务在跑 | `context_patch` 注入 active task digest |
| 结果落盘 | ❌ async_result reload 是空操作 | 先写 session history 再通知 |

---

## 3. Agent 可见接口契约

### 3.1 参数（不变）

| 参数 | 类型 | 说明 |
|------|------|------|
| `prompt` | `str` | Claude Code 任务描述，必填 |
| `project_path` | `str \| None` | 工作目录，缺省回落到默认 workspace |
| `mode` | `"fast" \| "standard" \| "readonly" \| "sync"` | 当前只有 `sync` 真正可用 |
| `session_id` | `str \| None` | 传给 `claude --resume` 的恢复会话 ID |

### 3.2 同步结果格式（不变）

```text
[Claude Code SUCCESS/ERROR]
Turns: <N> | Duration: <N>ms | Cost: $<N>
Session: <session_id?>

<Claude Code result 文本>
```

### 3.3 异步结果格式（Phase 1 目标）

工具返回（立即）：
```text
Claude Code task started (id: <task_id>). Use /task to check progress.
```

完成后写入 origin session history（用户在 ChatPage 可见）：
```text
[Claude Code task <task_id> completed]
Status: SUCCESS/ERROR
Duration: <N>ms | Cost: $<N>

<result digest>
```

---

## 4. session_key 路由修复

### 4.1 当前 bug

Console 调用链中 `_set_tool_context` 传 `channel="console", chat_id=user_id`，ClaudeCodeTool 计算 `session_key = "console:{user_id}"`。但真实的 session_key 是 `"console:{session_id}"`。

| 通道 | chat_id | 真实 session_key | 工具计算的 session_key | 是否正确 |
|------|---------|-----------------|----------------------|----------|
| telegram | `12345` | `telegram:12345` | `telegram:12345` | ✅ |
| console | `alice` | `console:abc123` | `console:alice` | ❌ |
| cli | `direct` | `cli:direct` | `cli:direct` | ✅ |

### 4.2 修复方式

1. `loop_patch` 在 `_process_message` 入口存 `self._current_session_key = key`
2. `patched_set_tool_context` 遍历所有有 `set_context` 的工具，传 `session_key=self._current_session_key`
3. `ClaudeCodeTool.set_context(channel, chat_id, *, session_key=None)` 优先使用直传的 session_key

这是前置修复，与 Phase 1 解耦，可独立提交。

---

## 5. 后台任务上下文层（BackgroundTaskStore）

### 5.1 定位

BackgroundTaskStore 不只服务于 claude_code。它是统一的后台任务上下文层，采用"写多读一"模式：

- **写入**：coding executor / cron observer / subagent observer 分别向 store 写入事件
- **读取**：context_patch（digest 注入）、commands（/task 查询）、async_result（完成通知）统一从 store 读

Phase 1 只实装 coding 事件源，但读接口从第一天起就是通用的。

### 5.2 与 claude_code 的关系

claude_code 是 BackgroundTaskStore 的一个事件源。职责分离：

| 职责 | 归属 |
|------|------|
| 命令构造、子进程管理、JSON 解析、token stats | ClaudeCodeTool |
| 任务注册、状态机、timeline、持久化、digest | BackgroundTaskStore |
| 完成回调：落盘 + 通知 | BackgroundTaskStore |
| session_key 路由 | loop_patch + set_context |
| IM 上下文注入 | context_patch |

### 5.3 完成回调链（Phase 1）

```text
BackgroundTaskStore._on_complete(snapshot, agent_loop)
  1. 写结果到 origin session history:
     session = agent_loop.sessions.get_or_create(snapshot.origin_session_key)
     session.add_message(role="assistant", content=formatted_result)
     agent_loop.sessions.save(session)
  2. 通知前端:
     bus.publish_outbound(OutboundMessage(
         channel=..., chat_id=...,
         content=formatted_result,
         session_key=snapshot.origin_session_key))
  3. ChatPage 收到 async_result → loadSessionMessages → 看到新消息 ✅
```

**关键**：步骤 1（落盘）必须先于步骤 2（通知）。否则 reload 是空操作。

### 5.4 IM 上下文注入（Phase 1）

`context_patch.build_messages` 新增第 5 步：

```text
1. HistorySummarizer
2. HistoryCompressor
3. 原始 build_messages
4. 注入分类记忆
5. 注入 BackgroundTaskStore.get_active_digest(session_key)  ← 新增
```

Digest 格式（注入 system prompt 尾部）：

```text
## Active Background Tasks
- [coding:abc123] running 45s — "Fix bug in auth module..."
```

无活跃任务时不注入（空字符串）。

### 5.5 内存保留策略（2026-04-07）

- `_active` / `_tasks` 继续持有 live task
- `_finished` 只保留内存热窗口：默认最多 20 条、最多 30 分钟
- 被 prune 的完成任务不再占用常驻内存；完整历史继续以 SQLite 为真相源
- `get_status(task_id=...)` 在内存中找不到时会回退 DB，避免 prune 后 console 单任务详情直接丢失
- `get_timeline()` / `get_task_detail()` 继续可从 DB 读取完整事件和全文结果

---

## 6. 配置与依赖

### 6.1 配置来源（不变）

主路径：`config.tools.claude_code`（fork schema）

### 6.2 上游 / sidecar 依赖

#### 上游依赖

- `nanobot.agent.tools.base.Tool`
- `nanobot.agent.loop.AgentLoop`

#### Sidecar 依赖

- `ava/patches/tools_patch.py`
- `ava/patches/loop_patch.py`
- `ava/patches/context_patch.py`
- `ava/agent/bg_tasks.py`（Phase 1 新增）
- `ava/console/services/token_stats_service.py`
- `ava/forks/config/schema.py`

#### 不再依赖

- ~~`nanobot.agent.subagent.SubagentManager`~~（v1 的 subagent_patch 已废弃）

#### 外部依赖

- 本机 `claude` 可执行文件
- `ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL`（显式配置时）

---

## 7. 已知约束与技术债

- [x] ~~`spawn_claude_code` 等方法缺失~~ → 不再 patch SubagentManager，改用 BackgroundTaskStore
- [ ] session_key 路由 bug：console 场景下 `set_context` 收到的是 `user_id` 而非 `session_id` → 前置修复
- [ ] async_result 链没闭环：结果未落盘，reload 是空操作 → Phase 1 修复
- [ ] IM 对话完全感知不到后台任务 → Phase 1 context_patch digest 注入
- [ ] `/stop` 不覆盖 coding 任务 → Phase 1 修复
- [ ] 异步模式默认暴露给 LLM 但不可用 → Phase 1 实装后解除
- [ ] 无 tests/tools/test_claude_code.py → Phase 1 补齐
- [ ] 结果只有文本，无结构化 diff、文件列表 → 远期
- [ ] console 卡片只消费最终文本，不消费独立状态事件 → 远期

---

## 8. 后续改进方向

### Phase 1：BackgroundTaskStore + coding 闭环

- 创建 `BackgroundTaskStore`（`ava/agent/bg_tasks.py`）
- `claude_code` async 分支接入 store
- session_key 路由修复（前置）
- 结果落盘到 origin session + async_result 通知
- context_patch 注入 active task digest
- 通用命令（/task, /task_cancel），/cc_status 降为别名
- SQLite 持久化 timeline + task history

### Phase 2：通用 CLI + 更多事件源

- 抽取 `CodingCLIBase`
- 新增 `CodexCLI` 后端
- BackgroundTaskStore 接入 cron observer / subagent observer

### Phase 2.5（可选）：streaming 增强

- `_run_subprocess` 改成 streaming
- snapshot 实时更新 phase/todo/last_tool

对应任务 Spec：`./tasks/2026-04-04_coding-cli-and-self-improvement-loop.md`

---

## 9. 测试要点

| 场景 | 验证内容 |
|------|----------|
| 同步成功 | JSON 解析、结构化输出格式、session/cost/turns 渲染 |
| CLI 缺失 | `claude` 不在 PATH 时给出可操作错误 |
| stderr-only 失败 | 正确回传错误摘要 |
| 超长输出 | 头尾截断策略稳定 |
| 配置注入 | `api_key` / `base_url` 正确写入环境变量 |
| Token stats | `provider=claude-code-cli`、`model_role=claude_code` 正确记录 |
| session_key 路由 | console 场景下 `_session_key == "console:{session_id}"`（非 user_id） |
| Store submit | 任务创建、状态转换、timeline 事件记录 |
| Store cancel | 取消运行中/已完成任务的行为 |
| 结果落盘 | 完成后 origin session history 包含结果消息 |
| async_result | console listener 收到通知、ChatPage reload 可见新消息 |
| context digest | build_messages 返回的 system prompt 包含 active task digest |
| /task 命令 | 返回正确的任务列表和 timeline |
| /stop 覆盖 | 取消 coding 任务 + 原有 turn task + subagent |
| async fallback | `task_store=None` 时 async mode 自动降级到 sync |
| 持久化 | gateway 重启后历史任务可查 |
