---
specanchor:
  level: task
  task_name: "Self-Improvement Loop 端到端闭环修复"
  author: "@fanghu"
  created: "2026-04-05"
  status: "review"
  sdd_phase: "REVIEW"
  last_change: "v4: Execute done — all 12 items implemented, 37 tests passing"
  related_modules:
    - ".specanchor/modules/claude_code_tool_spec.md"
    - ".specanchor/modules/tools_patch_spec.md"
    - ".specanchor/modules/loop_patch_spec.md"
    - ".specanchor/modules/context_patch_spec.md"
  related_tasks:
    - ".specanchor/tasks/2026-04-04_coding-cli-and-self-improvement-loop.md"
    - ".specanchor/tasks/2026-04-04_lifecycle-and-frontend-hotupdate.md"
  related_global:
    - ".specanchor/global/architecture.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  branch: "feat/0.1.1"
---

# SDD Spec: Self-Improvement Loop 端到端闭环修复

## 0. Open Questions

- [x] Agent Loop Continuation 的注入方式？
  → **决策：参考 cron 的 `process_direct` 机制**。bg_task 完成后调用 `loop.process_direct(continuation_content, session_key=origin_session_key, ...)`。
  → 不额外发 Telegram 通知（现有 outbound 已通知），continuation 在 origin session 上下文中执行，agent 的后续响应通过正常渠道发送。
  → 增加 `_continuation_depth` 防循环（默认 max=3）。
- [x] 前端 Rebuild 的触发策略？
  → **决策：A+B 双保险**。A 系统级 post-task hook（`_on_complete` 中检测 `console-ui/src/` 变更 → 自动 `rebuild_console_ui()`），B TOOLS.md 显式指引。
- [x] TOOLS.md 的委托策略应该有多激进？
  → **决策：强推荐 + 列出例外场景**。"代码修改/重构/分析任务优先使用 claude_code/codex"，例外：单文件简单编辑、配置修改、日志查看。

---

## 1. Requirements (Context)

- **Goal**: 修复 self-improvement loop 实测中发现的三个闭环缺口：
  1. Agent 不委托代码任务给 claude_code/codex（行为策略缺失）
  2. Claude Code 完成后不触发 agent loop 后续操作（continuation 机制缺失）
  3. 改完前端代码后没有自动 rebuild（post-task automation 缺失）

- **In-Scope**:
  - TOOLS.md 增加 Task Delegation Strategy 段落
  - bg_tasks `_on_complete` 增加 agent loop continuation 机制
  - bg_tasks `_on_complete` 增加 post-task hook（前端变更检测 → 自动 rebuild）
  - 必要时修改 `ava/console/ui_build.py` 暴露 rebuild 的 programmatic 接口

- **Out-of-Scope**:
  - 完整 self-improvement flow 编排（Phase 3）
  - 自动 commit / 自动 PR 流水线
  - cron/subagent 事件源接入
  - Telegram 命令注册（Phase 2 遗留）
  - Agent 自主决策"是否需要重启 gateway"（lifecycle spec 已覆盖）

- **上下文关系**:
  - 本 Spec 是 `coding-cli-and-self-improvement-loop.md` 的 Phase 3 前奏
  - 依赖 `lifecycle-and-frontend-hotupdate.md` 的 Phase B（rebuild API）已实现
  - 三个问题本质是 **self-improvement loop 的端到端闭环缺失**：输入端（不知道委托）→ 中间环节（没有回调驱动）→ 输出端（产物未生效）

---

## 2. Research Findings

### 2.1 Issue 1: Agent 行为策略缺失——自己探索而非委托

**现象**：用户给 nanobot 下达代码任务后，nanobot 自己用 `read_file` / `list_dir` / `exec` 探索代码，而非委托给 `claude_code` 或 `codex`。

**根因分析**：

1. **TOOLS.md Quick Map 只有弱引导**：

   ```
   | 做代码库级修改、重构、只读分析 | `claude_code` 或 `codex` |
   ```

   这只是一个推荐表，没有行为约束力。LLM 看到 `read_file`/`list_dir`/`exec` 也能做代码分析，自然倾向于"先自己看看"。

2. **claude_code 的 tool description 没有触发优先级**：

   ```python
   description = "Run Claude Code CLI to execute code tasks: modify code, add features, fix bugs, refactor, or analyze a codebase."
   ```

   这是功能描述，不是行为指令。没有告诉 agent "你应该在什么场景下**优先使用我**而非自己动手"。

3. **AGENTS.md 缺少任务委托策略**：当前 `AGENTS.md` 只有 Heartbeat 和 Reminder 相关指导，没有"代码任务处理策略"段落。

4. **根本原因**：LLM agent 的默认行为是"用自己最熟悉的工具做事"。`read_file` 等基础工具是 LLM 的舒适区——零延迟、结果确定、不需要等待异步。要让 agent 主动委托，需要**显式的行为规则**。

**修复方向**：

- TOOLS.md 增加 `## Task Delegation Strategy` 段落：
  - 明确列出"必须委托"场景（多文件修改、功能开发、重构、bug 修复）
  - 明确列出"可以自行处理"例外（单文件简单修改、配置文件编辑、查看日志）
  - 给出决策流程图

- AGENTS.md 增加 `## Code Task Handling` 段落，作为行为层的强制指引

### 2.2 Issue 2: Agent Loop 无 Continuation 机制

**现象**：Claude Code 完成后台任务后，通过 Telegram 通知用户"任务完成"，但 nanobot agent loop 不会继续处理后续步骤。用户需要手动发消息触发。

**根因分析**：

1. **`_on_complete` 的终点是"通知"，不是"继续"**：

   ```python
   async def _on_complete(self, snapshot, result):
       # 1. 写结果到 session history ✅
       session.messages.append({"role": "assistant", "content": formatted})
       # 2. 发 outbound 通知 ✅
       bus.publish_outbound(OutboundMessage(...))
       # 3. 触发 agent loop 继续 ❌ ← 缺失
   ```

2. **outbound 消息的消费路径**：
   - `publish_outbound` → `ConsoleListener` → WebSocket → 前端 async_result → reload
   - `publish_outbound` → `TelegramListener` → 发送 Telegram 消息给用户
   - **但不会触发 agent loop 的新 turn**

3. **为什么不能直接调用 `_process_message`**：
   - `_process_message` 需要一个 `InboundMessage`，带 channel/chat_id/session_key
   - 直接合成一个 inbound 并调用 `_process_message` 相当于模拟一个"用户输入"
   - 风险：可能导致无限循环（任务 A 完成 → 触发 turn → turn 又启动任务 B → ...）

4. **已有的近似机制**：
   - `spawn` 工具可以起子代理，但不是 continuation
   - 上游 `AgentLoop` 有 `_active_tasks`，但只管当前 turn 的 tasks

**候选方案分析**：

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| A: 内部注入 | bg_task 完成后直接调 `_process_message` | 延迟最低 | 可能无限循环；绕过消息管道 |
| B: 渠道回注 | 通过 origin 渠道（Telegram/Console）发送一条消息 | 经过完整管道；可控；可追溯 | 延迟稍高；需要构造合适的消息内容 |
| C: Pending queue | agent loop 增加 `_pending_continuations` 队列 | 清晰；无副作用 | 需要修改 agent loop 轮询逻辑（可能要改 nanobot/） |

**倾向方案 B**：

```python
async def _on_complete(self, snapshot, result):
    # 现有逻辑...
    
    # 新增：注入 continuation 消息
    if snapshot.status in ("succeeded", "failed") and loop:
        continuation_content = self._build_continuation_message(snapshot)
        from nanobot.bus.events import InboundMessage
        cont_msg = InboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=continuation_content,
            session_key=snapshot.origin_session_key,
        )
        asyncio.create_task(loop._process_message(cont_msg))
```

**方案 B 的关键细节**：
- 消息内容应该是任务结果摘要 + 明确提示 agent 可以继续下一步
- 需要防循环机制：标记消息来源为 `bg_task_continuation`，agent loop 可识别
- 或者更简单：不通过 `_process_message`，而是直接通过渠道发送（Telegram bot 给自己发消息 / Console 模拟用户消息）

**实际上最简方案**：在 `_on_complete` 中通过 `bus.publish_outbound` 发出的消息已经会到达 Telegram 用户。问题是这条消息是 **bot→user** 方向（outbound），不是 **user→bot** 方向（inbound）。要触发 agent loop，需要的是一个 inbound 消息。

**最可行路径**：在 `_on_complete` 中，成功落盘和通知后，直接 `asyncio.create_task(loop._process_message(InboundMessage(...)))` 合成一个 inbound。消息内容包含任务结果和 continuation 指令。需要增加防重入/防循环机制。

### 2.3 Issue 3: 前端 Rebuild 未自动触发

**现象**：Claude Code 改了 `console-ui/` 下的前端代码，但前端没有热更新。模型截图看到的是旧页面。用户手动 `npm run build` 后才看到更新。

**根因分析**：

1. **Phase B 的设计是"按需 rebuild"，不是"自动 rebuild"**：
   - `POST /api/gateway/console/rebuild` 存在 ✅
   - `useVersionCheck()` 60s 轮询 ✅
   - 但**没有任何自动触发者**

2. **Claude Code 不知道要 rebuild**：
   - TOOLS.md 没有提到"改完前端代码后需要 rebuild"
   - claude_code 的 prompt 没有包含 rebuild 指令
   - Claude Code CLI 运行在独立进程里，只关注完成 prompt 中描述的任务

3. **模型截图是旧页面**：
   - 因为 `npm run build` 没执行，`console-ui/dist/` 里的文件是旧的
   - FastAPI StaticFiles 服务的是旧的 dist 文件
   - `version.json` 没更新，`useVersionCheck` 检测不到变更

**修复方向（双保险）**：

A. **系统层：post-task hook**（在 `_on_complete` 中）

```python
async def _on_complete(self, snapshot, result):
    # 现有逻辑...
    
    # post-task hook: 检测前端文件变更 → 自动 rebuild
    if snapshot.status == "succeeded" and snapshot.task_type == "coding":
        await self._maybe_rebuild_frontend(snapshot)

async def _maybe_rebuild_frontend(self, snapshot):
    """检测 coding task 是否修改了前端文件，若是则自动 rebuild。"""
    project_path = snapshot.project_path
    # 通过 git diff 检测是否有 console-ui/ 下的文件变更
    # 如有 → 调用 rebuild_console_ui()
```

B. **指令层：TOOLS.md / claude_code prompt**

- TOOLS.md 增加说明："修改 `console-ui/` 下文件后，必须在项目根目录执行 `cd console-ui && npm run build`"
- 或在 claude_code 的 prompt 注入中自动附加此指令

**倾向 A+B 双保险**：A 是兜底（LLM 忘了也没关系），B 是显式指引（让 LLM 自己做构建验证）。

### 2.4 现有能力可利用点

| 能力 | 位置 | 可利用性 |
|------|------|---------|
| `rebuild_console_ui()` 异步封装 | `ava/console/ui_build.py` | ✅ 直接调用 |
| `write_version_json()` | `ava/console/ui_build.py` | ✅ build 后自动生成 |
| `BackgroundTaskStore._on_complete` | `ava/agent/bg_tasks.py` | ✅ 扩展点 |
| `bus.publish_outbound` | `nanobot/bus/` | ✅ 通知链路 |
| `loop._process_message` | `nanobot/agent/loop.py` | ⚠️ 可调用但需防循环 |
| `InboundMessage` | `nanobot/bus/events.py` | ✅ 构造 continuation 消息 |
| `git diff --name-only` | shell | ✅ 检测前端文件变更 |
| `useVersionCheck()` | `console-ui/src/hooks/` | ✅ rebuild 后 60s 内前端感知 |

### 2.5 风险识别

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Continuation 无限循环 | 高 | agent 不断触发自己 | 增加 `_continuation_depth` 计数器，限制深度（如 max=3） |
| TOOLS.md 委托策略太强 | 中 | agent 连简单文件操作都要委托 | 明确列出例外场景 |
| `npm run build` 失败但 agent 不知道 | 低 | 前端仍旧版本 | 检查 build 返回值，失败时在 continuation 消息中告知 |
| Continuation 消息内容不当导致 agent 行为偏离 | 中 | agent 做了不该做的事 | 消息模板固定，只包含事实和"请继续"指令 |
| `git diff` 检测范围不准（如 submodule） | 低 | 误判或漏判前端变更 | 限定检测路径为 `console-ui/src/` |

---

## 2.1 Next Actions

- 确认 Open Questions 中的三个决策
- 进入 Innovate 或直接 Plan（如果 Open Questions 可在 Plan 中收敛）

---

## 3. Innovate (Optional: Options & Decision)

### Skip

- Skipped: true
- Reason: 三个 Open Questions 已在 Research 中分析了候选方案并由用户决策，无需多方案比较。

---

## 4. Plan (Contract)

### 4.1 File Changes

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 1 | `ava/tools/claude_code.py` | 修改 | `description` 增加委托优先级语言；`_execute_background` 调用 `submit_coding_task` 时传 `auto_continue=True`（仅 standard/fast mode） |
| 2 | `ava/tools/codex.py` | 修改 | `description` 增加委托优先级语言；`_submit_task` 传 `auto_continue=True` |
| 3 | `ava/agent/bg_tasks.py` | 修改 | `submit_coding_task` 新增 `auto_continue` 参数；`_on_complete` 增加 post-task hooks + opt-in continuation；新增方法见 §4.2 |
| 4 | `ava/templates/TOOLS.md` | 修改 | 新增 `## Task Delegation Strategy` 段落（启动时同步到 workspace，下次重启生效） |
| 5 | `ava/templates/AGENTS.md` | 修改 | 新增 `## Code Task Handling` 段落 |
| 6 | `ava/console/ui_build.py` | 无修改 | 复用 `needs_console_ui_build()` + `rebuild_console_ui()` |

---

### 4.2 Signatures

```python
# ava/agent/bg_tasks.py 新增/修改

_MAX_CONTINUATION_BUDGET = 5

class BackgroundTaskStore:
    def __init__(self, db=None):
        ...
        self._continuation_budgets: dict[str, int] = {}

    def submit_coding_task(
        self,
        executor,
        *,
        origin_session_key: str,
        prompt: str,
        project_path: str,
        timeout: int,
        auto_continue: bool = False,  # 新增：显式 opt-in
        **executor_kwargs,
    ) -> str:
        """auto_continue=True 时，任务完成后在 origin session 中触发 agent loop 继续处理。"""
        ...

    async def _on_complete(self, snapshot, result):
        # 现有：写 session history + publish outbound
        ...
        # 新增：post-task hooks（前端 rebuild 等）
        rebuild_info = await self._run_post_task_hooks(snapshot)
        # 新增：opt-in continuation（仅 auto_continue=True 的任务）
        if snapshot.auto_continue:
            await self._trigger_continuation(snapshot, rebuild_info)

    async def _run_post_task_hooks(self, snapshot) -> str:
        """返回 hook 执行结果描述（如 rebuild 信息），供 continuation 引用。"""
        ...

    async def _maybe_rebuild_frontend(self, snapshot) -> str | None:
        """复用 needs_console_ui_build() 检测 → rebuild_console_ui() 构建。
        返回 rebuild 结果描述，或 None 表示无需 rebuild。"""
        ...

    async def _trigger_continuation(self, snapshot, rebuild_info: str = "") -> None:
        """参考 cron 的 process_direct，在 origin session 中继续。
        路由闭合：从 origin_session_key 解析 channel/chat_id 并显式传入。
        防循环：per-session 累积 budget（不递减），超限停止。"""
        ...

    def _build_continuation_message(self, snapshot, rebuild_info: str = "") -> str:
        """构造 continuation 消息。"""
        ...
```

```python
# ava/agent/bg_tasks.py — TaskSnapshot 扩展
@dataclass
class TaskSnapshot:
    ...
    auto_continue: bool = False  # 新增
```

```python
# ava/tools/claude_code.py — description 增强 + auto_continue 传递
class ClaudeCodeTool(Tool):
    @property
    def description(self) -> str:
        return (
            "Run Claude Code CLI to execute code tasks. "
            "For any task involving code modification, refactoring, bug fixing, "
            "or multi-file analysis, ALWAYS prefer this tool over manually "
            "reading/writing files one by one with read_file/write_file/edit_file. "
            "..."
        )

    async def execute(self, prompt, project_path, mode, session_id, **kwargs):
        ...
        if mode != "sync" and self._task_store:
            task_id = self._task_store.submit_coding_task(
                ...,
                auto_continue=mode in ("standard", "fast"),
            )
```

```python
# ava/tools/codex.py — description 增强 + auto_continue
class CodexTool(Tool):
    @property
    def description(self) -> str:
        return (
            "Run OpenAI Codex CLI for code tasks. "
            "ALWAYS prefer this tool (or claude_code) for code modification, "
            "analysis, or refactoring over manual file operations. "
            "..."
        )
```

### 4.3 详细设计

#### 4.3.1 Continuation 机制（参考 cron）— 修正版

**核心修正（Codex 锐评 #1 #2）**：

1. **opt-in 合同**：`submit_coding_task(auto_continue=True)` 显式标记。只有需要后续处理的任务（如 self-improvement loop 触发的 standard/fast mode）才 opt-in。`readonly` 和 `sync` 模式不 opt-in。
2. **路由闭合**：从 `origin_session_key` 解析 `channel` + `chat_id`，显式传入 `process_direct(session_key=..., channel=..., chat_id=...)`。agent 响应通过 `bus.publish_outbound(resp)` 显式发送到正确渠道。
3. **防循环升级**：per-session **累积 budget**（不递减），而非递归 depth 计数。budget 只在**新的用户消息**到达时重置（通过 `_process_message` hook 检测）。

**触发流程**：

```text
bg_task 完成（auto_continue=True）
  → _on_complete()
    → 1. 写 session history（已有）
    → 2. publish_outbound → Telegram 通知（已有，不额外发）
    → 3. _run_post_task_hooks()（新增）
       → _maybe_rebuild_frontend()
          → needs_console_ui_build(console_ui_dir) 检测
          → rebuild_console_ui(console_ui_dir)
          → 返回 rebuild 结果描述
    → 4. _trigger_continuation()（新增，仅 auto_continue=True）
       → 检查 session budget < MAX
       → budget -= 1
       → 从 origin_session_key 解析 channel/chat_id
       → loop.process_direct(msg, session_key=origin, channel=channel, chat_id=chat_id)
       → resp = OutboundMessage
       → bus.publish_outbound(resp) → 发送到正确的 Telegram/Console 渠道
```

**Continuation 消息模板**：

```text
[Background Task Completed]
Task: {task_type}:{task_id} — {status}
Duration: {elapsed_ms}ms

{result_preview 或 error_message}

{rebuild_info（如有前端 rebuild 则附加结果）}

请基于以上结果继续处理后续步骤。如果所有工作已完成，请总结。
```

**防循环机制**：

```text
_continuation_budgets: dict[str, int]  # session_key → 剩余 budget

- auto_continue 任务提交时：如 session 无 budget → 初始化为 MAX（5）
- 每次 continuation 消费 1 点
- budget 耗尽 → log warning，停止 continuation
- 新的用户消息到达（loop._process_message 入口）→ 重置 budget

vs 旧方案 depth 计数器的区别：
- depth 计数器在 continuation 返回后递减 → 串行链式循环绕过限制
- budget 只减不加（直到用户新消息） → 5 次硬上限无论链式还是递归
```

**与 cron 的类比**：

| 维度 | cron | continuation |
|------|------|-------------|
| 触发 | 定时器 | bg_task 完成回调（仅 auto_continue=True） |
| session | `cron:{job_id}`（独立） | `origin_session_key`（复用） |
| 路由 | `channel=job.payload.channel, chat_id=job.payload.to` | 从 origin_session_key 解析 |
| 响应发送 | 条件 `bus.publish_outbound(resp)` | 显式 `bus.publish_outbound(resp)` |
| 上下文 | 无先前对话 | 有完整 origin session 历史 |

#### 4.3.2 前端自动 Rebuild — 修正版

**修正（Codex 锐评 #4）**：不用 `git diff --name-only`，直接复用 `needs_console_ui_build()`。

**检测逻辑**：

1. 只对 `task_type == "coding"` 且 `status == "succeeded"` 的任务执行
2. 从 `snapshot.project_path` 定位 `console-ui/` 目录
3. 调用已有的 `needs_console_ui_build(console_ui_dir)` — 比较 src/ 与 dist/ 时间戳
   - 已覆盖完整输入集：`src/`, `public/`, `index.html`, `package.json`, `vite.config.ts` 等
   - 不依赖 git 脏树，绑定到**产物新鲜度**
4. 如需 rebuild → 调用 `rebuild_console_ui(console_ui_dir)` → 返回 `RebuildResult`
5. 将结果格式化为字符串，供 continuation 消息引用

**时序保证**：rebuild 在 continuation 之前完成（步骤 3 先于步骤 4），确保 agent 看到最新页面。

#### 4.3.3 Tool Description 增强 — 新增面（Codex 锐评 #3）

**高权重输入面**：`ClaudeCodeTool.description` 和 `CodexTool.description` 直接进入 tool defs，是模型做 tool selection 的最高权重输入。

修改 `description` property：
- 增加 "ALWAYS prefer this tool over manually reading/writing files" 语言
- 明确使用场景（code modification, refactoring, bug fixing, multi-file analysis）
- 这比 TOOLS.md 模板文档更直接影响模型行为

#### 4.3.4 TOOLS.md / AGENTS.md 委托策略 — 辅助面（Codex 锐评 #5）

**定位**：辅助面，通过 `sync_workspace_templates()` 在启动时覆盖到 workspace。对当前运行实例不立即生效（需重启）。

TOOLS.md 新增 `## Task Delegation Strategy` 段落：
- 必须委托场景 / 例外场景 / 决策原则

AGENTS.md 新增 `## Code Task Handling` 段落：
- 行为指引（优先委托、prompt 规范、auto rebuild 说明）

**生效时机**：templates_patch 在 gateway 启动时执行 `sync_workspace_templates()`，将 `ava/templates/` 覆盖到 workspace 根目录。因此模板变更在下次重启后生效。由于本次变更涉及 bg_tasks.py（Python 后端），重启是必要的。

### 4.4 Implementation Checklist

- [ ] 1. `ava/tools/claude_code.py`：`description` 增加委托优先级语言
- [ ] 2. `ava/tools/codex.py`：`description` 增加委托优先级语言
- [ ] 3. `ava/agent/bg_tasks.py`：`TaskSnapshot` 新增 `auto_continue` 字段
- [ ] 4. `ava/agent/bg_tasks.py`：`submit_coding_task` 新增 `auto_continue` 参数 → 写入 snapshot
- [ ] 5. `ava/agent/bg_tasks.py`：新增 `_continuation_budgets` + `_MAX_CONTINUATION_BUDGET`
- [ ] 6. `ava/agent/bg_tasks.py`：新增 `_run_post_task_hooks` → `_maybe_rebuild_frontend`（复用 `needs_console_ui_build`）
- [ ] 7. `ava/agent/bg_tasks.py`：新增 `_trigger_continuation` → `_build_continuation_message`（路由闭合 + budget 检查）
- [ ] 8. `ava/agent/bg_tasks.py`：`_on_complete` 调用 hooks + 条件 continuation
- [ ] 9. `ava/tools/claude_code.py`：`submit_coding_task` 调用传 `auto_continue=True`（standard/fast mode）
- [ ] 10. `ava/tools/codex.py`：`submit_coding_task` 调用传 `auto_continue=True`
- [ ] 11. `ava/patches/loop_patch.py`：`_process_message` 入口重置 continuation budget（新用户消息 → 重置）
- [ ] 12. `ava/templates/TOOLS.md`：新增 Task Delegation Strategy 段落
- [ ] 13. `ava/templates/AGENTS.md`：新增 Code Task Handling 段落
- [ ] 14. 测试

### 4.5 Tests

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 15 | `tests/agent/test_bg_tasks.py` | 修改 | continuation budget 限制 / process_direct 路由闭合 / 消息格式 / auto_continue opt-in/out / budget 重置 |
| 16 | `tests/agent/test_bg_tasks.py` | 修改 | post-task hook：needs_console_ui_build 调用 / rebuild 调用 / 非 coding 任务跳过 / rebuild 失败处理 |
| 17 | `tests/tools/test_claude_code.py` | 修改 | auto_continue 参数传递 / description 包含委托语言 |
| 18 | `tests/tools/test_codex.py` | 修改 | auto_continue 参数传递 / description 包含委托语言 |

---

## 5. Execute Log

_(待 Plan approved 后开始)_

---

## 6. Review Verdict

_(待 Execute 完成后填写)_

---

## 7. Plan-Execution Diff

_(待 Execute 完成后填写)_
