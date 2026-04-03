---
specanchor:
  level: task
  task_name: "Page Agent Chat 内嵌展示：ToolCallBlock 专属渲染 + 桌面环境自动检测"
  author: "@fanghu"
  created: "2026-04-03"
  status: "in_progress"
  last_change: "Execute 阶段：runner/Python/前端实现完成，待测试和端到端验证"
  related_modules:
    - ".specanchor/modules/page_agent_runtime_spec.md"
    - ".specanchor/modules/console_browser_page_spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "EXECUTE"
  branch: "refactor/sidecar"
---

# SDD Spec: Page Agent Chat 内嵌展示

## 0. Open Questions

- [x] 用 iframe 嵌入还是 screencast 帧？→ screencast 帧（iframe 被多数网站 CSP 阻止）
- [x] 有桌面环境时如何展示？→ `headless: false` 弹出真实浏览器窗口，Chat 页面只显示文本结果
- [x] 无桌面环境时如何展示？→ 列为 TODO，本次 Spec 不实现
- [ ] ~~环境检测时机？→ 启动时检测一次，写入配置~~ → **移至 TODO**：headless 自动检测涉及配置模型三态（`None`）与序列化兼容性问题，需独立 Spec 处理
- [x] 实时 screencast 是否嵌入 ToolCallBlock？→ 仅无桌面模式需要（TODO），有桌面模式不需要
- [x] 返回值格式变更的向后兼容？→ 保留 `session=` 格式以兼容 SKILL.md 等下游消费者

## 1. Requirements (Context)

- **Goal**: 
  1. 在 Chat 页面中为 `page_agent` 工具调用提供专属的 ToolCallBlock 渲染（类似 `claude_code` 和 media tools 的专属展示）
  2. 结构化 page_agent 的返回文本，使前端可以解析元数据并展示专属卡片
  3. 扩展 runner error 协议，使错误/超时也能携带结构化元数据
- **In-Scope**:
  1. **ToolCallBlock 专属渲染**：为 `page_agent` 设计专属卡片，展示 session、URL、指令、执行步数、状态等结构化信息
  2. **page_agent 返回值结构化**：在工具返回文本中增加可解析的元数据（类似 claude_code 的 `[Claude Code SUCCESS]` 格式），保持 `session=` 向后兼容
  3. **runner error 协议扩展**：error/timeout 分支也返回 `session_id`、`steps`、`duration` 等元数据
  4. **下游消费者同步**：更新 `ava/skills/console_ui_regression/SKILL.md` 中的格式文档
- **Out-of-Scope**:
  - headless 自动检测与配置三态（需独立 Spec，涉及配置模型兼容性）
  - Loading 状态区分 headed/headless 提示（依赖 headless 检测）
  - 无桌面模式下的 screencast 内嵌展示（TODO，后续 Spec 处理）
  - 修改 `nanobot/` 目录
  - BrowserPage 独立页面的改动（保持现有功能不变）
  - page_agent 工具的核心执行逻辑改动

### 1.1 Context Sources

- Requirement Source:
  - 用户希望在 Chat 页面中对 page_agent 的工具调用有更好的可视化展示
  - 用户希望有桌面环境时直接弹出浏览器窗口，可以实时观看 AI 操作
- Design Refs:
  - `.specanchor/modules/page_agent_runtime_spec.md`
  - `.specanchor/modules/console_browser_page_spec.md`
- Code Refs:
  - `console-ui/src/pages/ChatPage/ToolCallBlock.tsx` — 现有工具调用渲染（claude_code、media tools 的专属渲染模式）
  - `ava/tools/page_agent.py` — 工具实现，返回文本格式
  - `console-ui/e2e/page-agent-runner.mjs` — Node runner，`headless` 配置消费方
  - `ava/forks/config/schema.py` — `PageAgentConfig`，`headless` 字段定义

## 2. Research Findings

### 2.1 现有 ToolCallBlock 专属渲染模式分析

当前 `ToolCallBlock.tsx` 有三种渲染路径：

| 工具 | 检测方式 | 专属展示 |
|------|---------|---------|
| `claude_code` | `fnName === 'claude_code'` | 解析 `[Claude Code STATUS]` 格式，展示 mode badge、turns、duration、cost、session |
| media tools | `MEDIA_TOOLS[fnName]` | 专属图标/颜色、ImageCarousel、prompt 展示 |
| 其他 | fallback | 通用 Arguments + Result 展示 |

**关键模式**：`claude_code` 的专属渲染依赖工具返回文本的固定格式，前端用正则解析元数据。`page_agent` 应采用相同模式。

### 2.2 page_agent 当前返回格式

`page_agent.py` 的 `_do_execute` 返回文本格式（行 131-158）：

```
[PageAgent] session={session_id}
URL: {page_url}
Title: {page_title}

{result_text}
```

> ⚠️ 注意：
> - 当前实现**没有** Steps 行。steps 数据存在于 runner 成功响应 `result.steps` 中，但 Python 端未格式化输出。
> - runner 成功响应也**没有** `duration` 字段，需要在 runner 中记录执行开始时间并计算差值。
> - runner 成功响应中包含 `success: result.success`（page-agent 内层执行结果），但 Python 端未区分内层 success/fail，只看 RPC 外层 `result.get("success")`。

**错误分支**（两层）：
1. **RPC 失败**（runner 抛异常）：Python `_do_execute` 只返回 `f"Error: {msg}"`，丢失 session_id/steps/duration/url/title。runner error 响应只含 `{code, message}`。
2. **Python 端 TIMEOUT**：`_rpc()` 在 Python 端合成 `{"code": "TIMEOUT"}`（line 506-510），不经过 runner。同样只返回简单错误字符串。
3. **page-agent 内层失败**（RPC 成功但 `result.success == false`）：当前 Python 端不检查内层 `success`，会被当成成功处理。

该格式已经半结构化，可以在此基础上增强为可解析格式。同时需要扩展 runner error 协议和 Python 端 STATUS 判定逻辑。

### 2.3 headless 配置当前流程

```
PageAgentConfig.headless (schema.py)
  → PageAgentTool.__init__ 读取 config.headless
  → _send_init_direct() 下发 {"headless": true/false} 到 runner
  → runner init handler 设置 config.headless
  → ensureBrowser() 使用 config.headless 启动 Playwright
```

当前 `headless` 默认为 `true`，用户需手动在 `extra_config.json` 中修改。

## 3. Design

### 3.1 ~~环境检测与 headless 自动切换~~ → 已移至 §7 TODO

> 本节原计划在 `PageAgentConfig.headless` 上引入 `None` 三态 + 启动时检测 + 写入配置。
> 经 Review 发现以下问题：
> 1. `headless: bool | None = None` 会通过 `model_dump(mode="json")` 将 `null` 写入配置文件，破坏序列化契约
> 2. Spec 描述"启动时检测一次，写入配置"但 File Changes 无持久化路径，描述与实现意图矛盾
> 3. 独立于 ToolCallBlock 专属卡片，不应混在同一 Spec
>
> **建议方向**：不修改 `PageAgentConfig` 模型，新增运行时属性 `PageAgentTool._resolved_headless`，纯内存态，不影响配置模型。独立 Spec 处理。

### 3.2 page_agent 返回值结构化

#### 3.2.1 Python 端格式化（`ava/tools/page_agent.py`）

将 `_do_execute` 的返回文本改为固定格式，便于前端解析。**保留 `session=` 以兼容旧消费者**：

```
[PageAgent SUCCESS] session=s_abc12345 | Steps: 5 | Duration: 3200ms
URL: https://example.com/result
Title: Search Results

已找到搜索框并输入关键词，点击搜索按钮，页面显示 10 条结果。
```

失败时：

```
[PageAgent ERROR] session=s_abc12345 | Steps: 3 | Duration: 2100ms
URL: https://example.com
Title: Example Page

Error: 未找到匹配的按钮元素，已重试 3 次。
```

**格式规范**：
- 第一行：`[PageAgent STATUS] session={id} | Steps: N | Duration: Nms`
  - STATUS 判定逻辑（三层）：
    1. `TIMEOUT`：Python 端 `_rpc()` 超时时合成（`error.code == "TIMEOUT"`），**不经过 runner**
    2. `ERROR`：RPC 外层 `result.get("success")` 为 false（runner 抛异常），或 RPC 成功但 page-agent 内层 `result.result.success` 为 false
    3. `SUCCESS`：RPC 成功且 page-agent 内层 `result.result.success` 为 true
  - `session=` 格式保留，确保 `ava/skills/console_ui_regression/SKILL.md` 等下游消费者兼容
- 第二行：`URL: {current_url}`
- 第三行：`Title: {page_title}`
- 空行
- 正文：page-agent 的执行结果文本

**Python 端 STATUS 判定伪代码**：

```python
result = await self._rpc("execute", ...)

# 1. RPC 失败（含 TIMEOUT）
if not result.get("success"):
    err = result.get("error", {})
    code = err.get("code", "") if isinstance(err, dict) else ""
    status = "TIMEOUT" if code == "TIMEOUT" else "ERROR"
    # → 组装 [PageAgent STATUS] 结构化文本（见 3.2.2）

# 2. RPC 成功但 page-agent 内层执行失败
r = result.get("result", {})
inner_success = r.get("success", True)  # runner 已透传 page-agent 内层 success
status = "SUCCESS" if inner_success else "ERROR"
# → 组装 [PageAgent STATUS] 结构化文本
```

#### 3.2.2 Runner 协议扩展（`console-ui/e2e/page-agent-runner.mjs`）

需要扩展两个方面：
1. **成功分支**：新增 `duration` 字段（毫秒），记录 `executePageAgent` 的执行耗时
2. **错误分支**：返回 `session_id`、`page_url`、`page_title`；`session` 变量 hoist 到 try 外

**当前**（line 296-332）：
```javascript
async execute(id, params) {
    // ...
    try {
      const session = await getOrCreateSession(sessionId);  // session 定义在 try 内
      // ...
    } catch (err) {
      reply(id, false, { code: "EXECUTION_FAILED", message: err.message });
    }
}
```

**改为**（注意 `session` 提升到 try 外）：
```javascript
async execute(id, params) {
    const { url, instruction, session_id: sid } = params;
    if (!instruction) {
      return reply(id, false, { code: "MISSING_PARAM", message: "instruction is required" });
    }
    const sessionId = sid || `s_${Date.now().toString(36)}`;
    let session = null;       // hoist 到 try 外，catch 可访问
    const startMs = Date.now();

    try {
      session = await getOrCreateSession(sessionId);
      if (url) {
        await session.page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
      }
      await setupActivityBridge(sessionId, session.page);
      const result = await executePageAgent(session.page, instruction);
      const pageUrl = session.page.url();
      const pageTitle = await session.page.title();
      const duration = Date.now() - startMs;

      reply(id, true, {
        session_id: sessionId,
        data: result.data,
        success: result.success,
        steps: result.steps,
        duration,               // 新增：执行耗时（毫秒）
        page_url: pageUrl,
        page_title: pageTitle,
      });
    } catch (err) {
      let pageUrl = url || "unknown";
      let pageTitle = "unknown";
      if (session?.page) {
        try {
          pageUrl = session.page.url();
          pageTitle = await session.page.title();
        } catch { /* ignore */ }
      }
      reply(id, false, {
        code: "EXECUTION_FAILED",
        message: err.message,
        session_id: sessionId,
        duration: Date.now() - startMs,
        page_url: pageUrl,
        page_title: pageTitle,
      });
    }
}
```

> 注意：`steps` 和 `duration` 需要在 `executePageAgent` 执行过程中记录并传回。如果 `executePageAgent` 抛出异常导致无法获取 steps，则 steps 置为 0。duration 需要在 try 开头记录 `Date.now()`，catch 中计算差值。

**Python 端 error / timeout 格式化**：

`_do_execute` 中需要处理三种失败：RPC error（runner 抛异常）、TIMEOUT（Python 端合成）、page-agent 内层失败（RPC 成功但 `result.success == false`）。

```python
result = await self._rpc("execute", {...})

# —— 失败分支（RPC 失败 / TIMEOUT） ——
if not result.get("success"):
    err = result.get("error", {})
    code = err.get("code", "") if isinstance(err, dict) else ""
    msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
    status = "TIMEOUT" if code == "TIMEOUT" else "ERROR"
    sid = err.get("session_id", session_id) if isinstance(err, dict) else session_id
    duration = err.get("duration", 0) if isinstance(err, dict) else 0
    page_url = err.get("page_url", "unknown") if isinstance(err, dict) else "unknown"
    page_title = err.get("page_title", "unknown") if isinstance(err, dict) else "unknown"
    parts = [
        f"[PageAgent {status}] session={sid} | Steps: 0 | Duration: {duration}ms",
        f"URL: {page_url}",
        f"Title: {page_title}",
        "",
        f"Error: {msg}",
    ]
    return "\n".join(parts)

# —— 成功分支（RPC 成功） ——
r = result.get("result", {})
inner_success = r.get("success", True)
status = "SUCCESS" if inner_success else "ERROR"
steps = r.get("steps", 0)
duration = r.get("duration", 0)
parts = [
    f"[PageAgent {status}] session={r.get('session_id', session_id)} | Steps: {steps} | Duration: {duration}ms",
    f"URL: {r.get('page_url', 'unknown')}",
    f"Title: {r.get('page_title', 'unknown')}",
    "",
    r.get("data", "(no output)"),
]
return "\n".join(parts)
```

#### 3.2.3 下游消费者同步

更新 `ava/skills/console_ui_regression/SKILL.md` 中的格式文档，将：
```
`execute` 返回格式：`[PageAgent] session=<id>\nURL: <url>\nTitle: <title>\n\n<执行结果描述>`
```
改为：
```
`execute` 返回格式：`[PageAgent SUCCESS/ERROR] session=<id> | Steps: N | Duration: Nms\nURL: <url>\nTitle: <title>\n\n<执行结果描述>`
```

### 3.3 ToolCallBlock page_agent 专属渲染

**文件**：`console-ui/src/pages/ChatPage/ToolCallBlock.tsx`

新增 `page_agent` 的专属渲染分支，插入在 `claude_code` 分支之后、`mediaTool` 分支之前：

```typescript
interface PageAgentResult {
  status: string        // SUCCESS / ERROR / TIMEOUT
  steps: number
  duration: string      // "3.2s"
  sessionId: string
  url: string
  title: string
  body: string          // 执行结果正文
}

function parsePageAgentResult(text: string): PageAgentResult | null {
  const statusMatch = text.match(/\[PageAgent (\w+)\]/)
  if (!statusMatch) return null

  // 兼容 session= 格式
  const sessionMatch = text.match(/session=(\S+?)(?:\s*\||\s*$)/)
  const stepsMatch = text.match(/Steps:\s*(\d+)/)
  const durationMatch = text.match(/Duration:\s*(\d+)ms/)
  const urlMatch = text.match(/URL:\s*(.+)/)
  const titleMatch = text.match(/Title:\s*(.+)/)

  const bodyStart = text.indexOf('\n\n')
  const body = bodyStart >= 0 ? text.slice(bodyStart + 2).trim() : ''

  return {
    status: statusMatch[1],
    steps: stepsMatch ? parseInt(stepsMatch[1]) : 0,
    duration: durationMatch ? `${(parseInt(durationMatch[1]) / 1000).toFixed(1)}s` : '?',
    sessionId: sessionMatch ? sessionMatch[1] : '',
    url: urlMatch ? urlMatch[1].trim() : '',
    title: titleMatch ? titleMatch[1].trim() : '',
    body,
  }
}
```

**卡片布局**：

```
┌─────────────────────────────────────────────────────┐
│ 🌐 Page Agent  [SUCCESS]  5 steps  3.2s  s_abc1234 │  ← 折叠状态的标题行
├─────────────────────────────────────────────────────┤
│ Instruction                                         │  ← 展开后
│ ┌─────────────────────────────────────────────────┐ │
│ │ 访问 google.com 搜索 "AI agent"                  │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ URL: https://www.google.com/search?q=AI+agent       │
│ Title: AI agent - Google Search                     │
│                                                     │
│ Result                                              │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 已找到搜索框并输入关键词，点击搜索按钮，页面显示 │ │
│ │ 10 条结果。第一条是...                           │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ [TODO] 无桌面模式: screencast 实时帧区域            │
└─────────────────────────────────────────────────────┘
```

**视觉风格**（与 `claude_code` 一致）：
- 主色调：`emerald`（绿色系），区别于 claude_code 的 `cyan`
- 图标：`Globe`（来自 lucide-react）
- 状态 badge：SUCCESS 绿色、ERROR 红色、TIMEOUT 橙色
- 折叠状态：标题行显示 instruction 摘要（截断 60 字）
- 展开状态：显示 instruction 全文、URL（可点击）、Title、Result

**Loading 状态**：
- 工具执行中（`isLoading && !resultText`）：显示 `🌐 Page Agent` + spinner + "Browsing..."
- headed/headless 区分提示移至 TODO（依赖 headless 自动检测 Spec）

### 3.4 ~~headless 状态传递到前端~~ → 已移至 §7 TODO

> 本节原计划在返回文本中增加 `Mode: headed/headless` 行来驱动 Loading 提示。
> 经 Review 发现：Loading 分支在 `isLoading && !resultText` 时触发，此时结果文本还不存在，无法从中读取 `Mode`。
> 需要替代数据源（tool args、config API、或 observe WS 事件流）。与 headless 自动检测一起在独立 Spec 中处理。

## 4. File Changes Summary

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `ava/tools/page_agent.py` | 修改 | `_do_execute` 三层 STATUS 判定 + `_format_error_result()` 静态方法 |
| `console-ui/e2e/page-agent-runner.mjs` | 修改 | session hoist + `duration` 字段 + error 分支返回元数据 |
| `console-ui/src/pages/ChatPage/ToolCallBlock.tsx` | 修改 | `parsePageAgentResult` + page_agent 专属渲染（emerald 主色调） |
| `console-ui/src/components/layout/navItems.ts` | 修改 | 暂时隐藏 BrowserPage 导航入口 |
| `ava/skills/console_ui_regression/SKILL.md` | 修改 | 同步更新 execute 返回格式文档 |
| `.specanchor/modules/page_agent_runtime_spec.md` | 修改 | 更新 execute 返回格式、runner 响应字段、测试要点 |

## 5. Implementation Checklist

- [x] 1. 修改 `page-agent-runner.mjs`：session hoist + `duration` 字段 + error 分支返回 `session_id`、`page_url`、`page_title`、`duration`
- [x] 2. 修改 `page_agent.py` `_do_execute`：成功分支格式化为 `[PageAgent SUCCESS/ERROR] session=... | Steps: N | Duration: Nms`（含内层 success 判定）
- [x] 3. 修改 `page_agent.py`：新增 `_format_error_result()` 静态方法，RPC error / TIMEOUT 组装结构化文本
- [x] 4. 在 `ToolCallBlock.tsx` 中新增 `parsePageAgentResult()` 解析函数
- [x] 5. 在 `ToolCallBlock.tsx` 中新增 `page_agent` 专属渲染分支（卡片布局 + emerald 主色调）
- [x] 6. 实现 Loading 状态：统一 "Browsing..." + spinner（不区分 headed/headless）
- [x] 7. 更新 `ava/skills/console_ui_regression/SKILL.md` 格式文档
- [x] 8. 隐藏 BrowserPage 导航入口（`navItems.ts`）
- [x] 9. 更新 `page_agent_runtime_spec.md` Module Spec
- [ ] 10. 编写测试：`_do_execute` 成功/失败/TIMEOUT 返回格式
- [ ] 11. 编写测试：`parsePageAgentResult` 正则解析正确性（含旧格式降级）
- [ ] 12. 端到端验证：Chat 页面显示专属卡片

## 6. Test Coverage

| 测试场景 | 验证内容 |
|----------|----------|
| 返回值格式 SUCCESS | `[PageAgent SUCCESS] session={id} \| Steps: N \| Duration: Nms` 格式正确 |
| 返回值格式 ERROR（RPC 失败） | `[PageAgent ERROR] session={id} \| Steps: 0 \| Duration: Nms` + 错误信息 |
| 返回值格式 TIMEOUT | `[PageAgent TIMEOUT] session={id} \| Steps: 0 \| Duration: 0ms`（Python 端合成） |
| 内层 success=false | RPC 成功但 `result.success == false` → `[PageAgent ERROR]` 而非 `[PageAgent SUCCESS]` |
| runner error 响应 | error 分支返回 `session_id`、`page_url`、`page_title`、`duration` |
| runner error 作用域 | `session` hoist 到 try 外，catch 中可安全访问 `session?.page` |
| runner duration 字段 | 成功/失败分支都包含 `duration` 字段（毫秒） |
| Python error 格式化 | runner error / timeout 响应被 Python 端组装为结构化文本而非 `f"Error: {msg}"` |
| `session=` 兼容性 | 返回文本首行包含 `session=`，下游消费者可继续解析 |
| 前端解析 SUCCESS | `parsePageAgentResult` 正确提取 status/steps/duration/session/url/title/body |
| 前端解析 ERROR | `parsePageAgentResult` 正确提取 ERROR 状态 + body 含 Error 信息 |
| 前端解析 TIMEOUT | `parsePageAgentResult` 正确提取 TIMEOUT 状态 |
| 前端解析容错 | 旧格式（无 `[PageAgent ...]` 头）→ 返回 null，降级为通用渲染 |
| 专属卡片渲染 | 折叠/展开正常；URL 可点击；状态 badge 颜色正确 |
| Loading 状态 | 统一 "Browsing..." + spinner |

## 7. TODO（后续 Spec）

以下功能不在本次 Spec 范围内，列为后续迭代：

### 7.1 headless 自动检测与配置（从本 Spec §3.1/§3.4 移出）

- **环境检测**：`_detect_display_available()` 检测 macOS/Linux/Docker 桌面环境
- **配置策略**：不修改 `PageAgentConfig.headless`（保持 `bool = True`），新增运行时属性 `PageAgentTool._resolved_headless`，纯内存态
- **Loading 提示区分**：headed → "查看桌面浏览器窗口"；headless → "Browsing..."
- **数据源**：Loading 提示需要前置数据源（tool args 透传 headless 状态、config API、或 observe WS 事件流），不能依赖结果文本中的 `Mode` 字段

### 7.2 无桌面模式 screencast 内嵌

- 在 ToolCallBlock 中嵌入实时 screencast 帧流（执行中）+ 最终截图（完成后）+ activity 步骤列表

### 7.3 无桌面模式 ToolCallBlock 交互增强

- screencast 区域可全屏、可暂停、帧率调节

### 7.4 BrowserPage 与 ToolCallBlock 联动

- 从 ToolCallBlock 卡片跳转到 BrowserPage 查看完整 activity 历史

## 8. Execute Log

- `2026-04-03` Plan 阶段完成，经 Codex 两轮 Review（共 7 个问题），全部修复
- `2026-04-03` Execute 阶段：
  1. `page-agent-runner.mjs`：session hoist 到 try 外 + `Date.now()` 计时 + error 分支返回 session_id/duration/page_url/page_title
  2. `page_agent.py`：`_do_execute` 三层 STATUS 判定（TIMEOUT → RPC error → 内层 success）+ `_format_error_result()` 静态方法
  3. `ToolCallBlock.tsx`：`parsePageAgentResult()` + page_agent 专属渲染分支（emerald 主色调、状态 badge、URL 可点击）
  4. `navItems.ts`：隐藏 BrowserPage 导航入口
  5. `SKILL.md`：同步格式文档
  6. `page_agent_runtime_spec.md`：更新 execute 返回格式、runner 响应字段说明、测试要点

## 9. Review Verdict

（待 Review 时填写）

## 10. Risks & Mitigations

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 旧格式返回值的前端兼容 | 升级过渡期间 page_agent 返回旧格式（无 `[PageAgent ...]` 头），前端解析失败 | `parsePageAgentResult` 返回 null 时降级为通用渲染 |
| runner 与 Python 端版本不同步 | runner 已返回新字段但 Python 端未更新（或反过来） | runner 成功响应新增字段向后兼容（Python 端 `.get()` 有默认值）；error 响应同理 |
| `session=` 格式变更影响下游 | SKILL.md 等消费者按 `session=` 解析 session_id | 首行保留 `session=` 格式；SKILL.md 同步更新 |
| runner error 无法获取 steps/duration | `executePageAgent` 抛异常时无法获取已执行步数 | steps 置为 0；duration 通过 `Date.now() - startMs` 在 catch 中计算 |
| TIMEOUT 与 runner error 数据差异 | TIMEOUT 由 Python 端合成，无 `page_url`/`page_title` | TIMEOUT 格式化时 URL/Title 使用 "unknown"；duration 使用 Python 端配置的 timeout 值 |
| page-agent 内层 success=false 被忽略 | 当前 Python 端只检查 RPC 外层 success，不检查内层 | 新增内层 `result.success` 判定，false 时标记为 ERROR |
