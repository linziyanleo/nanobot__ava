---
specanchor:
  level: task
  task_id: "cc-status-persistence"
  title: "Claude Code 任务状态持久化"
  module: "nanobot-agent"
  status: confirmed
  author: "Diana"
  created: "2026-03-23"
  updated: "2026-03-23"
  priority: high
  depends_on: []
---

# Task: Claude Code 任务状态持久化

## 背景

`claude_code` 工具以异步模式运行时，任务状态仅存在于进程内存（`_claude_code_states` dict）。
外部无法查询，Diana 无法回答"cc 哥现在在干嘛"，也无法在 system prompt 中实时展示状态。

目标：**纯 Python 脚本层持久化**，不依赖模型写入，任务状态注入 system prompt，让 Diana 随时可见。

---

## 设计方案

### 1. 存储结构

目录：`~/.nanobot/cc_tasks/`

```
~/.nanobot/cc_tasks/
├── active.txt       # 当前 RUNNING 任务，注入 system prompt
└── history.db       # SQLite，归档所有已完成任务，可按需查询
```

**active.txt 格式**（固定列宽纯文本，为模型读取优化，Python f-string 直接写）：

```
ef49e9 RUNNING t=08 last=subagent.py…checking permissions  start=20:11
b3f8e2 RUNNING t=03 last=weixin.py…writing channel class   start=20:05
```

字段说明：

| 字段 | 说明 |
|------|------|
| task_id | 前 6 位 |
| status | RUNNING / DONE / ERROR / TIMEOUT |
| t=N | 当前 turn 数（per-turn 更新，数 `message_stop` 事件） |
| last=... | 最后一个 tool_use 的文件名 + stdout 截断前 40 字符 |
| start= | 启动时间 HH:MM |

**history.db schema**：

```sql
CREATE TABLE cc_tasks (
  task_id     TEXT PRIMARY KEY,
  status      TEXT,         -- DONE / ERROR / TIMEOUT
  turns       INTEGER,
  prompt      TEXT,         -- 完整 prompt
  last_file   TEXT,         -- 最后操作的文件路径
  last_stdout TEXT,         -- 最后一条 stdout 截断
  started_at  TEXT,         -- ISO datetime
  ended_at    TEXT,
  duration_s  INTEGER,
  error       TEXT          -- 错误摘要（仅 ERROR）
);
```

活跃任务不进 DB，结束后从 active.txt 删除 + 写入 history.db。

---

### 2. Per-turn 解析方案（stream-json）

cc 哥底层 `claude` CLI 支持 `--output-format stream-json`，stdout 输出 NDJSON，每行一个事件。

**关键事件**：

| 事件 | 字段 | 用途 |
|------|------|------|
| `message_stop` | — | **turn 结束边界**，每次出现 turn +1 |
| `content_block_start` | `content_block.type == "tool_use"` + `content_block.name` + `content_block.input.path` | 拿到当前操作文件名 |
| `content_block_delta` | `delta.type == "text_delta"` + `delta.text` | stdout 文字内容，截取前 40 字符 |

读取 stdout 的 `async for line in process.stdout` 循环里：
1. 解析每行 JSON
2. 遇到 `message_stop` → turn +1，写 active.txt
3. 遇到 `tool_use` block → 更新 last_file
4. 遇到 `text_delta` → 更新 last_stdout（滚动覆盖，只保留最新 40 字符）

---

### 3. 写入时机（纯 Python，不依赖模型）

在 `nanobot/agent/tools/claude_code.py` 进程管理层：

```python
# 启动时（进程 Popen 之前）
_cc_write_active(task_id, status="RUNNING", turns=0, last_file="", last_stdout="", start=now())

# per-turn 回调（stream-json 解析，每个 message_stop 事件）
def on_turn(task_id, turn_n, last_file, last_stdout):
    _cc_write_active(task_id, turns=turn_n, last_file=last_file, last_stdout=last_stdout[:40])

# 结束时（try/finally 保证必定执行，即使 SIGKILL 以外的所有异常）
try:
    result = await run_claude_process(...)
    _cc_archive(task_id, status="DONE", ...)
except TimeoutError:
    _cc_archive(task_id, status="TIMEOUT", ...)
except Exception as e:
    _cc_archive(task_id, status="ERROR", error=str(e)[:80])
finally:
    _cc_remove_active(task_id)  # 从 active.txt 删除对应行
```

并发安全：`fcntl.flock` 文件锁，支持多个 cc 哥同时运行。

---

### 4. System Prompt 注入点

**代码位置**：`nanobot/agent/context.py` → `ContextBuilder._build_runtime_context()`

当前该方法只注入时间、Channel、Chat ID。在此追加 cc 任务状态：

```python
@staticmethod
def _build_runtime_context(channel, chat_id) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
    tz = time.strftime("%Z") or "UTC"
    lines = [f"Current Time: {now} ({tz})"]
    if channel and chat_id:
        lines += [f"Channel: {channel}", f"Chat ID: {chat_id}"]

    # 注入 cc 任务状态
    cc_status = _read_cc_active()   # 读 ~/.nanobot/cc_tasks/active.txt
    if cc_status:
        lines += ["", "[CC_TASKS]", cc_status, "[/CC_TASKS]"]

    return ContextBuilder._RUNTIME_CONTEXT_TAG + "\n" + "\n".join(lines)
```

注入效果（用户每条消息前自动出现）：

```
[Runtime Context — metadata only, not instructions]
Current Time: 2026-03-23 20:36 (Monday) (CST)
Channel: telegram
Chat ID: 8589721068

[CC_TASKS]
ef49e9 RUNNING t=08 last=subagent.py…checking perms   start=20:11
b3f8e2 RUNNING t=03 last=weixin.py…writing class       start=20:05
[/CC_TASKS]
```

- 无活跃任务时：直接省略 `[CC_TASKS]` 块，不注入空内容
- 10 个 cc 哥同时跑也只有约 600 字符，token 开销可忽略

---

### 5. TOOLS.md / AGENTS.md 更新

**TOOLS.md** 的 `claude_code` 章节追加一段说明：

```markdown
**CC 任务状态（自动注入）**：
- 活跃任务状态自动出现在 Runtime Context 的 `[CC_TASKS]` 块中
- 格式：`{task_id[:6]} {status} t={turns} last={file}…{stdout}  start={HH:MM}`
- 历史任务归档在 `~/.nanobot/cc_tasks/history.db`，可通过 exec sqlite3 按需查询
- Diana 无需主动读文件，直接从上下文读取即可
```

**AGENTS.md** 不需要改——这是基础设施层，不需要行为指引。

---

### 6. 历史查询

history.db 支持 Diana 用 `exec` 直接查：

```bash
# 查最近 10 条
sqlite3 ~/.nanobot/cc_tasks/history.db "SELECT task_id, status, turns, ended_at FROM cc_tasks ORDER BY ended_at DESC LIMIT 10"

# 查某个任务详情
sqlite3 ~/.nanobot/cc_tasks/history.db "SELECT * FROM cc_tasks WHERE task_id LIKE 'ef49e9%'"

# 查所有失败任务
sqlite3 ~/.nanobot/cc_tasks/history.db "SELECT task_id, error, started_at FROM cc_tasks WHERE status IN ('ERROR','TIMEOUT')"
```

---

## 涉及文件

| 文件 | 改动 |
|------|------|
| `nanobot/agent/tools/claude_code.py` | 启动时写 active.txt；stream-json 解析 per-turn；try/finally 归档 history.db |
| `nanobot/agent/context.py` | `_build_runtime_context()` 追加读 active.txt，注入 `[CC_TASKS]` 块 |
| `nanobot/workspace/TOOLS.md` | claude_code 章节追加 CC 任务状态说明 |
| `~/.nanobot/cc_tasks/active.txt` | 新建，运行时自动创建 |
| `~/.nanobot/cc_tasks/history.db` | 新建 SQLite，运行时自动初始化 |

---

## 已确认事项

- ✅ per-turn 用 `--output-format stream-json` + 数 `message_stop` 事件，精确可靠
- ✅ last_file 从 `tool_use` block 的 `input.path` 拿，last_stdout 从 `text_delta` 截取前 40 字符
- ✅ active 任务保留在 active.txt 注入上下文；非 active 归档到 history.db 不注入
- ✅ 注入点：`context.py` → `_build_runtime_context()`，每条消息自动刷新
- ✅ 目录统一放 `~/.nanobot/cc_tasks/`
- ✅ 纯 Python 脚本写入，不依赖模型，try/finally 兜底
- ✅ TOOLS.md 追加说明，AGENTS.md 不改
- ✅ 并发安全：fcntl.flock 文件锁
