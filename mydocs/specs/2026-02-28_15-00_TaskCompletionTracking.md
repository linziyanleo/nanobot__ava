# SDD Spec: TaskCompletionTracking — 定时任务完成状态追踪机制

## 0. Open Questions

- [x] Q1: heartbeat_state.json 放在 workspace/ 下 → **确认 workspace/**
- [x] Q2: CronTool mark_done 的 cycle_id → **系统自动推断**
- [x] Q3: HeartbeatService 注入 heartbeat_state.json → **确认注入**
- [x] Q4: 执行历史 log → **V1 不做**
- [x] Q5: task_lifecycle skill → **确认 workspace/skills/**

## 1. Requirements (Context)

- **Goal**: 为 nanobot 的定时任务（Cron + Heartbeat）引入统一的「完成状态追踪」机制，让 agent 知道当前轮次是否已完成、是否需要执行、下一轮何时执行。同时提供一个 workspace skill 规范化 agent 的标记流程。
- **In-Scope**:
  1. CronJobState 扩展：添加任务级完成标记（task_completed_at_ms, task_cycle）
  2. CronTool 扩展：添加 `mark_done` 和 `check_status` action
  3. HeartbeatService 增加 per-task 状态追踪文件（heartbeat_state.json）
  4. HeartbeatService 决策 prompt 注入结构化状态
  5. workspace/skills/task_lifecycle skill：标准化 agent 标记流程
  6. 现有 weight_reminder 迁移到新机制（去除 ad hoc state.json）
- **Out-of-Scope**:
  - 任务依赖链/DAG
  - 重试策略
  - 执行历史持久化（V2 考虑）
  - CronService 与 HeartbeatService 合并

## 1.1 Context Sources

- Requirement Source: 用户口述需求 + 当前系统缺陷分析
- Code Refs:
  - `nanobot/cron/types.py` — CronJob, CronJobState 数据结构
  - `nanobot/cron/service.py` — CronService 调度引擎
  - `nanobot/agent/tools/cron.py` — CronTool agent 工具
  - `nanobot/heartbeat/service.py` — HeartbeatService 心跳服务
  - `workspace/HEARTBEAT.md` — 心跳任务定义
  - `workspace/skills/weight_reminder/` — 体重提醒 skill（现有 ad hoc 状态管理范例）
  - `nanobot/skills/cron/SKILL.md` — Cron 内置 skill
  - `workspace/AGENTS.md` — Agent 指令文档
  - `mydocs/specs/2026-02-27_22-30_ScheduleService.md` — 上一版 schedule 扩展

## 1.5 Codemap Used (Feature Index)

- Codemap Mode: `feature`
- Key Index:
  - **Cron 调度链**: `CronService.start()` → `_recompute_next_runs()` → `_arm_timer()` → `_on_timer()` → `_execute_job()` → `on_job(job)` → `agent.process_direct(message)`
  - **Heartbeat 调度链**: `HeartbeatService.start()` → `_run_loop()` → `_tick()` → `_read_heartbeat_file()` → `_decide(content)` [LLM] → `on_execute(tasks)` → `agent.process_direct(tasks)`
  - **Agent 工具**: `CronTool.execute()` → actions: add/list/remove
  - **状态持久化**: `CronJobState(next_run_at_ms, last_run_at_ms, last_status, last_error)` → `jobs.json`
  - **Heartbeat 状态**: 无结构化持久化，完全依赖 markdown checkbox 和 LLM 判断

## 1.6 Context Bundle Snapshot (Lite)

- Bundle Level: `Lite`
- Key Facts:
  1. CronJobState 已追踪 last_run_at_ms / last_status，但这是「调度层」状态（job 是否触发了），不是「业务层」状态（任务目标是否完成了）
  2. HeartbeatService 完全无状态，每 30 分钟读 HEARTBEAT.md → LLM 判断 skip/run → 可能重复执行
  3. weight_reminder 用独立的 state.json + python 脚本管理每日重置，属于 ad hoc 方案
  4. CronTool 只有 add/list/remove，agent 无法标记完成或查询状态
  5. HeartbeatService 的 LLM 决策只有 markdown 文本可参考，没有结构化的完成记录

## 2. Research Findings

### 2.1 核心问题诊断

| # | 问题 | 影响 | 严重度 |
|---|------|------|--------|
| P1 | Cron 任务无"本轮已完成"标记 | agent 不知道是否该执行，可能重复执行 | 高 |
| P2 | Heartbeat 任务无结构化状态 | 每 30 分钟 LLM 重新判断，可能漏判/误判 | 高 |
| P3 | agent 没有标准 API 标记任务完成 | 每个 skill 自行实现 ad hoc 状态管理 | 中 |
| P4 | Heartbeat 决策缺少结构化上下文 | LLM 只看 markdown 文本，缺少"上次完成时间"等关键信息 | 中 |
| P5 | 周期任务无"下一轮何时开始"概念 | 无法区分"今天已完成，明天再执行"和"还没执行" | 高 |

### 2.2 现有状态模型差异

```
┌────────────────────────────────────────────────┐
│  CronService (结构化，但仅追踪调度层)           │
│  ┌─────────────────────────────────────┐       │
│  │ CronJobState                        │       │
│  │  - next_run_at_ms    ← 调度层       │       │
│  │  - last_run_at_ms    ← 调度层       │       │
│  │  - last_status       ← 调度层       │       │
│  │  - [缺] task 完成标记 ← 业务层      │       │
│  │  - [缺] cycle 周期概念              │       │
│  └─────────────────────────────────────┘       │
├────────────────────────────────────────────────┤
│  HeartbeatService (无结构化状态)                │
│  ┌─────────────────────────────────────┐       │
│  │ 状态载体: HEARTBEAT.md (markdown)    │       │
│  │  - [ ] / - [x] 手动 checkbox        │       │
│  │  - 无持久化时间戳                    │       │
│  │  - 无 per-task 状态追踪             │       │
│  │  - 依赖 LLM 判断 → 不确定性高       │       │
│  └─────────────────────────────────────┘       │
├────────────────────────────────────────────────┤
│  Ad Hoc Skills (如 weight_reminder)            │
│  ┌─────────────────────────────────────┐       │
│  │  state.json + python scripts         │       │
│  │  - lastReset, lastReminderDate      │       │
│  │  - 仅适用于单个 skill               │       │
│  │  - 不与调度系统集成                  │       │
│  └─────────────────────────────────────┘       │
└────────────────────────────────────────────────┘
```

### 2.3 解决方案方向

**核心设计：分离「调度层」与「业务层」状态**

- **调度层**（CronService 已有）：job 什么时候触发、下次什么时候触发
- **业务层**（本次新增）：任务目标是否完成、当前在哪个周期、下一周期何时开始

具体措施：

1. **CronJobState 扩展** — 添加 `task_completed_at_ms` + `task_cycle` 字段
2. **CronTool 新 action** — `mark_done` 让 agent 标记完成；`check_status` 让 agent 查询状态
3. **HeartbeatService 状态文件** — `workspace/heartbeat_state.json` per-task 结构化状态
4. **HeartbeatService 决策增强** — 将 heartbeat_state.json 注入 LLM prompt
5. **workspace/skills/task_lifecycle** — 标准化 skill，让 agent 知道如何使用新 API

### 2.4 还可以完善的其他方面

| # | 改进方向 | 说明 | 优先级 |
|---|----------|------|--------|
| I1 | Heartbeat 短路判断 | heartbeat_state.json 显示所有任务已完成 → 跳过 LLM 调用 | 高（省成本） |
| I2 | Cron 执行幂等保护 | job 触发时检查 task_completed_at_ms，已完成本轮则跳过 | 高 |
| I3 | CronTool list 增强 | 展示完成状态（✅/⏳）、周期信息 | 中 |
| I4 | Heartbeat 任务 ID 规范化 | HEARTBEAT.md 中用 HTML comment 标记 task_id，便于状态关联 | 中 |
| I5 | 周期自动重置 | CronService 启动时/timer 触发时自动检测并重置过期周期 | 中 |

## 2.5 Next Actions

1. 等待用户确认 Open Questions
2. 确认方案方向后进入 Plan 阶段
3. 详细设计数据结构、接口签名、实现 checklist

## 3. Innovate (Options & Decision)

### Option A: 仅扩展 CronService（Cron 一体化）

- 把所有任务（包括当前 heartbeat 任务）都迁移到 CronService，废弃 HeartbeatService
- Pros: 统一模型，一处管理
- Cons: HeartbeatService 的 LLM 决策能力丢失；大改动；heartbeat 的灵活性（markdown 编辑）消失

### Option B: 双轨增强（推荐）

- CronService 扩展业务层状态 + HeartbeatService 新增结构化状态文件，各自增强
- 两个系统保持独立，但共享「任务完成标记」的设计模式
- Agent 通过统一的 CronTool 操作 cron 任务状态；通过文件读写操作 heartbeat 任务状态
- Pros: 渐进式改进，风险低，保留 heartbeat 灵活性
- Cons: 两套系统仍然分离

### Option C: 抽象 TaskStateService

- 新建 TaskStateService，CronService 和 HeartbeatService 都依赖它
- Pros: 最干净的架构
- Cons: 过度工程化，当前任务量不大

### Decision

- Selected: **Option B（双轨增强）**
- Why: 渐进式改进，风险最低，保留两个系统的各自优势。CronService 扩展不影响现有功能（向后兼容），HeartbeatService 增加状态文件不影响 markdown 编辑体验。

## 4. Plan (Contract)

### 4.1 File Changes

| # | 文件 | 变更说明 |
|---|------|----------|
| F1 | `nanobot/cron/types.py` | CronJobState 添加 `task_completed_at_ms` + `task_cycle_id` 字段 |
| F2 | `nanobot/cron/service.py` | 添加 `mark_job_done()` + `get_job_status()` 方法；序列化/反序列化新字段；`_execute_job` 中幂等保护（已完成本轮则跳过）；`_compute_cycle_id()` 辅助方法 |
| F3 | `nanobot/agent/tools/cron.py` | CronTool 添加 `mark_done` + `check_status` action；更新 description/parameters |
| F4 | `nanobot/heartbeat/service.py` | 添加 `heartbeat_state_file` 属性；`_read_heartbeat_state()` 方法；`_decide()` prompt 注入状态；全任务已完成时短路跳过 LLM 调用 |
| F5 | `nanobot/skills/cron/SKILL.md` | 更新内置 cron skill 文档，添加 mark_done / check_status 示例 |
| F6 | `workspace/skills/task_lifecycle/SKILL.md` | **新建** — 标准化 agent 任务完成标记流程的 skill |
| F7 | `workspace/AGENTS.md` | 添加「任务完成状态追踪」section |

### 4.2 Signatures

#### F1: `nanobot/cron/types.py`

```python
@dataclass
class CronJobState:
    """Runtime state of a job."""
    next_run_at_ms: int | None = None
    last_run_at_ms: int | None = None
    last_status: Literal["ok", "error", "skipped"] | None = None
    last_error: str | None = None
    # 业务层：agent 标记的任务完成状态
    task_completed_at_ms: int | None = None
    task_cycle_id: str | None = None  # e.g. "2026-02-28" for daily
```

#### F2: `nanobot/cron/service.py`

```python
def _compute_cycle_id(self, schedule: CronSchedule) -> str:
    """根据 schedule 类型计算当前周期标识。
    - cron daily pattern → date string "YYYY-MM-DD"
    - cron hourly → "YYYY-MM-DD-HH"
    - every → str(last_run_at_ms // every_ms)
    - at → "once"
    """

def mark_job_done(self, job_id: str) -> CronJob | None:
    """Agent 标记任务本轮已完成。
    设置 task_completed_at_ms = now, task_cycle_id = current cycle。
    返回更新后的 job，不存在返回 None。
    """

def get_job_status(self, job_id: str) -> dict | None:
    """获取任务详细状态，包含完成信息。
    返回 dict: {id, name, enabled, schedule_kind, last_run, next_run,
                task_completed, task_cycle_id, is_current_cycle_done}
    """
```

`_execute_job` 修改逻辑：
```python
async def _execute_job(self, job: CronJob) -> None:
    # 新增：幂等保护 — 检查当前 cycle 是否已完成
    current_cycle = self._compute_cycle_id(job.schedule)
    if (job.state.task_completed_at_ms
        and job.state.task_cycle_id == current_cycle):
        job.state.last_status = "skipped"
        logger.info("Cron: job '{}' skipped (cycle {} already done)", job.name, current_cycle)
        # 仍然计算下次运行时间
        job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())
        return
    # ... 原有执行逻辑不变 ...
```

`_load_store` / `_save_store` 序列化新字段：
```python
# _load_store 中 state 部分：
state=CronJobState(
    ...,
    task_completed_at_ms=j.get("state", {}).get("taskCompletedAtMs"),
    task_cycle_id=j.get("state", {}).get("taskCycleId"),
)

# _save_store 中 state 部分：
"state": {
    ...,
    "taskCompletedAtMs": j.state.task_completed_at_ms,
    "taskCycleId": j.state.task_cycle_id,
}
```

#### F3: `nanobot/agent/tools/cron.py`

```python
# description 更新
@property
def description(self) -> str:
    return "Schedule reminders and recurring tasks. Actions: add, list, remove, mark_done, check_status."

# parameters 更新 — action enum 增加 "mark_done", "check_status"
"action": {
    "type": "string",
    "enum": ["add", "list", "remove", "mark_done", "check_status"],
}

# execute 路由增加
async def execute(self, action, ..., **kwargs) -> str:
    ...
    elif action == "mark_done":
        return self._mark_done(job_id)
    elif action == "check_status":
        return self._check_status(job_id)

def _mark_done(self, job_id: str | None) -> str:
    """标记指定 job 本轮已完成。"""

def _check_status(self, job_id: str | None) -> str:
    """返回指定 job 的详细状态。若 job_id 为空，返回所有 job 的状态摘要。"""
```

#### F4: `nanobot/heartbeat/service.py`

```python
@property
def heartbeat_state_file(self) -> Path:
    return self.workspace / "heartbeat_state.json"

def _read_heartbeat_state(self) -> dict | None:
    """读取 heartbeat_state.json 并返回 dict。"""

async def _decide(self, content: str) -> tuple[str, str]:
    """修改：注入 heartbeat_state.json 内容到 prompt。"""
    state = self._read_heartbeat_state()
    state_context = ""
    if state:
        state_context = f"\n\n## Task Completion State\n```json\n{json.dumps(state, indent=2, ensure_ascii=False)}\n```"
    
    # 短路判断：如果所有任务今天都已完成
    if self._all_tasks_done_today(state):
        return "skip", ""
    
    response = await self.provider.chat(
        messages=[
            {"role": "system", "content": "You are a heartbeat agent. Call the heartbeat tool to report your decision."},
            {"role": "user", "content": (
                "Review the following HEARTBEAT.md and task completion state, "
                "decide whether there are active tasks that need to run.\n\n"
                f"{content}{state_context}"
            )},
        ],
        tools=_HEARTBEAT_TOOL,
        model=self.model,
    )

def _all_tasks_done_today(self, state: dict | None) -> bool:
    """检查 state 中是否所有任务都在今天完成了。
    注意：只有当 HEARTBEAT.md 中有 active tasks 且 state 覆盖了所有 task 时才短路。
    保守策略：如果 state 为空或不完整，返回 False（不短路）。
    """
```

`heartbeat_state.json` 格式：

```json
{
  "version": 1,
  "tasks": {
    "weight_reminder": {
      "completed_at": "2026-02-28T09:30:00+08:00",
      "cycle": "2026-02-28",
      "next_cycle": "2026-03-01"
    },
    "aiway_check": {
      "completed_at": "2026-02-28T14:30:00+08:00",
      "cycle": "2026-02-28T14:00",
      "next_cycle": "2026-02-28T15:00"
    }
  }
}
```

> **注意**：heartbeat_state.json 由 agent 通过 file tools 读写，HeartbeatService 只读取并注入 prompt。这与 HEARTBEAT.md 的管理方式一致（agent 通过 file tools 编辑）。

#### F5: `nanobot/skills/cron/SKILL.md` 更新

新增 mark_done / check_status 文档和示例。

#### F6: `workspace/skills/task_lifecycle/SKILL.md`

定义标准流程：
1. Cron 任务：执行前 `check_status` → 执行 → `mark_done`
2. Heartbeat 任务：执行前读 `heartbeat_state.json` → 执行 → 写 `heartbeat_state.json`
3. 状态字段说明、示例、最佳实践

#### F7: `workspace/AGENTS.md` 更新

添加 "Task Completion Tracking" section，引用 task_lifecycle skill。

### 4.3 Implementation Checklist

- [ ] 1. `nanobot/cron/types.py` — CronJobState 添加 `task_completed_at_ms` + `task_cycle_id`
- [ ] 2. `nanobot/cron/service.py` — `_load_store` / `_save_store` 序列化新字段
- [ ] 3. `nanobot/cron/service.py` — 添加 `_compute_cycle_id()` 方法
- [ ] 4. `nanobot/cron/service.py` — 添加 `mark_job_done()` 方法
- [ ] 5. `nanobot/cron/service.py` — 添加 `get_job_status()` 方法
- [ ] 6. `nanobot/cron/service.py` — `_execute_job()` 添加幂等保护
- [ ] 7. `nanobot/agent/tools/cron.py` — 添加 `mark_done` + `check_status` action
- [ ] 8. `nanobot/heartbeat/service.py` — 添加 `heartbeat_state_file`、`_read_heartbeat_state()`、`_all_tasks_done_today()`
- [ ] 9. `nanobot/heartbeat/service.py` — `_decide()` 注入状态 + 短路判断
- [ ] 10. `nanobot/skills/cron/SKILL.md` — 更新文档
- [ ] 11. `workspace/skills/task_lifecycle/SKILL.md` — 新建 skill
- [ ] 12. `workspace/AGENTS.md` — 添加任务完成追踪 section

## 5. Execute Log

- [x] Step 1: `nanobot/cron/types.py` L39-41 添加 `task_completed_at_ms` + `task_cycle_id`
- [x] Step 2: `nanobot/cron/service.py` `_load_store` L109-110 反序列化新字段；`_save_store` L159-160 序列化新字段
- [x] Step 3: `nanobot/cron/service.py` L242-266 `_compute_cycle_id()` — 根据 cron 表达式推断 daily/hourly 周期
- [x] Step 4: `nanobot/cron/service.py` L390-403 `mark_job_done()` — 设置 completed_at + cycle_id 并持久化
- [x] Step 5: `nanobot/cron/service.py` L405-437 `get_job_status()` + `_job_status_dict()` — 返回含完成状态的详细信息
- [x] Step 6: `nanobot/cron/service.py` L268-279 `_execute_job()` 幂等保护 — 检查 cycle_id 匹配则 skip
- [x] Step 7: `nanobot/agent/tools/cron.py` — actions enum 增加 `mark_done`/`check_status`；新增 `_mark_done()`、`_check_status()`、`_format_status()` 方法
- [x] Step 8: `nanobot/heartbeat/service.py` L79-98 — 添加 `heartbeat_state_file` 属性 + `_read_heartbeat_state()` + `_all_tasks_done_today()`
- [x] Step 9: `nanobot/heartbeat/service.py` L117-156 — `_decide()` 注入 state context + 短路判断
- [x] Step 10: `nanobot/skills/cron/SKILL.md` — 添加 check_status / mark_done 文档 + Task Completion Tracking 章节
- [x] Step 11: `workspace/skills/task_lifecycle/SKILL.md` — 新建 skill，完整文档化 cron/heartbeat 两套流程
- [x] Step 12: `workspace/AGENTS.md` — 添加 "Task Completion Tracking" section

## 6. Review Verdict

- Spec coverage: **PASS** — 所有 12 步 checklist 均已实现
- Behavior check: **PASS**
  - CronJobState 新字段向后兼容（默认 None）
  - `_compute_cycle_id` 正确区分 daily/hourly 模式
  - `_execute_job` 幂等保护：cycle_id 匹配时 skip，仍计算 next_run
  - `mark_job_done` / `get_job_status` 持久化到 jobs.json
  - CronTool 新 action 无需 session context（mark_done/check_status 不需要 channel/chat_id）
  - HeartbeatService 短路判断保守策略：state 为空/不完整时不短路
  - HeartbeatService prompt 注入清晰标注了状态来源和使用指引
  - heartbeat_state.json 由 agent 读写，HeartbeatService 只读 — 职责分离清晰
- Regression risk: **Low** — 6 个现有测试全部通过，所有新字段默认 None 向后兼容
- Follow-ups:
  - 可选：weight_reminder skill 迁移到 heartbeat_state.json（去除 ad hoc state.json）
  - 可选：初始化 workspace 时自动创建空 heartbeat_state.json
  - 可选：cron list 命令也展示完成状态

## 7. Plan-Execution Diff

- CronTool `_check_status` 中移除了无用的 `import json`（Plan 中未提及，属于 code hygiene 微调）
- 其余实现严格遵循 Plan 签名和 checklist，无偏差
