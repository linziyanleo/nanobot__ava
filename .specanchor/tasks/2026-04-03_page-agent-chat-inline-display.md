---
specanchor:
  level: task
  task_name: "Page Agent Chat 内嵌展示：ToolCallBlock 专属渲染 + 桌面环境自动检测"
  author: "@fanghu"
  created: "2026-04-03"
  status: "draft"
  last_change: "初始化 task spec"
  related_modules:
    - ".specanchor/modules/page_agent_runtime_spec.md"
    - ".specanchor/modules/console_browser_page_spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "refactor/sidecar"
---

# SDD Spec: Page Agent Chat 内嵌展示

## 0. Open Questions

- [x] 用 iframe 嵌入还是 screencast 帧？→ screencast 帧（iframe 被多数网站 CSP 阻止）
- [x] 有桌面环境时如何展示？→ `headless: false` 弹出真实浏览器窗口，Chat 页面只显示文本结果
- [x] 无桌面环境时如何展示？→ 列为 TODO，本次 Spec 不实现
- [x] 环境检测时机？→ 启动时检测一次，写入配置
- [x] 实时 screencast 是否嵌入 ToolCallBlock？→ 仅无桌面模式需要（TODO），有桌面模式不需要

## 1. Requirements (Context)

- **Goal**: 
  1. 在 Chat 页面中为 `page_agent` 工具调用提供专属的 ToolCallBlock 渲染（类似 `claude_code` 和 media tools 的专属展示）
  2. 自动检测运行环境是否有桌面，有桌面时切换为 `headless: false`，用户直接在桌面浏览器窗口中观看 AI 操作
- **In-Scope**:
  1. **环境检测**：启动时检测是否有桌面环境，自动设置 `headless` 配置
  2. **ToolCallBlock 专属渲染**：为 `page_agent` 设计专属卡片，展示 session、URL、指令、执行步数、状态等结构化信息
  3. **page_agent 返回值结构化**：在工具返回文本中增加可解析的元数据（类似 claude_code 的 `[Claude Code SUCCESS]` 格式）
- **Out-of-Scope**:
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
Steps: {steps}

{result_text}
```

该格式已经半结构化，可以在此基础上增强为可解析格式。

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

### 3.1 环境检测与 headless 自动切换

**文件**：`ava/tools/page_agent.py`

在 `PageAgentTool.__init__` 中，若用户未在配置中显式设置 `headless`，则自动检测：

```python
def _detect_display_available() -> bool:
    """检测当前环境是否有桌面显示能力。启动时调用一次。"""
    import sys
    import subprocess

    if sys.platform == "darwin":
        # macOS：检查是否在 GUI session 中
        # 通过 `who` 命令检测是否有 console 登录
        try:
            result = subprocess.run(
                ["who"], capture_output=True, text=True, timeout=5
            )
            return "console" in result.stdout
        except Exception:
            return False

    elif sys.platform == "linux":
        # Linux：检查 DISPLAY 或 WAYLAND_DISPLAY 环境变量
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    # Windows 或其他平台：默认有桌面
    return True
```

**配置优先级**：
1. 用户在 `extra_config.json` 中显式设置 `headless` → 使用用户设置
2. 未显式设置 → 调用 `_detect_display_available()`
   - 有桌面 → `headless = False`
   - 无桌面 → `headless = True`

**判断"未显式设置"的方式**：在 `PageAgentConfig` 中，`headless` 字段默认值改为 `None`（而非 `True`）。`None` 表示未显式设置，触发自动检测。

### 3.2 page_agent 返回值结构化

**文件**：`ava/tools/page_agent.py`

将 `_do_execute` 的返回文本改为固定格式，便于前端解析：

```
[PageAgent SUCCESS] Steps: 5 | Duration: 3200ms | Session: s_abc12345
URL: https://example.com/result
Title: Search Results

已找到搜索框并输入关键词，点击搜索按钮，页面显示 10 条结果。
```

失败时：

```
[PageAgent ERROR] Steps: 3 | Duration: 2100ms | Session: s_abc12345
URL: https://example.com
Title: Example Page

Error: 未找到匹配的按钮元素，已重试 3 次。
```

**格式规范**：
- 第一行：`[PageAgent STATUS] Steps: N | Duration: Nms | Session: {id}`
  - STATUS: `SUCCESS` / `ERROR` / `TIMEOUT`
- 第二行：`URL: {current_url}`
- 第三行：`Title: {page_title}`
- 空行
- 正文：page-agent 的执行结果文本

这与 `claude_code` 的 `[Claude Code SUCCESS]` 模式保持一致。

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

  const metaMatch = text.match(/Steps:\s*(\d+)\s*\|\s*Duration:\s*(\d+)ms\s*\|\s*Session:\s*(\S+)/)
  const urlMatch = text.match(/URL:\s*(.+)/)
  const titleMatch = text.match(/Title:\s*(.+)/)

  const bodyStart = text.indexOf('\n\n')
  const body = bodyStart >= 0 ? text.slice(bodyStart + 2).trim() : ''

  return {
    status: statusMatch[1],
    steps: metaMatch ? parseInt(metaMatch[1]) : 0,
    duration: metaMatch ? `${(parseInt(metaMatch[2]) / 1000).toFixed(1)}s` : '?',
    sessionId: metaMatch ? metaMatch[3] : '',
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
- 有桌面环境时额外提示："查看桌面浏览器窗口"

### 3.4 headless 状态传递到前端

前端需要知道当前是否为有桌面模式，以决定是否显示"查看桌面浏览器窗口"提示。

**方案**：在 page_agent 的返回文本中增加一个 metadata 行：

```
[PageAgent SUCCESS] Steps: 5 | Duration: 3200ms | Session: s_abc12345
Mode: headed
URL: https://example.com/result
Title: Search Results

...
```

`Mode` 字段：`headed`（有桌面，用户可看到浏览器窗口）或 `headless`（无桌面）。

前端解析此字段：
- `headed` → Loading 时显示 "查看桌面浏览器窗口"
- `headless` → Loading 时显示 "Browsing..."（未来扩展为 screencast 嵌入）

## 4. File Changes Summary

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `ava/tools/page_agent.py` | 修改 | 新增 `_detect_display_available()`；headless 自动检测逻辑；`_do_execute` 返回值格式化为可解析格式；增加 Mode 字段 |
| `ava/forks/config/schema.py` | 修改 | `PageAgentConfig.headless` 默认值从 `True` 改为 `None` |
| `console-ui/src/pages/ChatPage/ToolCallBlock.tsx` | 修改 | 新增 `page_agent` 专属渲染分支（`parsePageAgentResult` + 卡片布局） |

## 5. Implementation Checklist

- [ ] 1. 修改 `schema.py`：`PageAgentConfig.headless` 默认值改为 `None`
- [ ] 2. 在 `page_agent.py` 中实现 `_detect_display_available()`
- [ ] 3. 修改 `PageAgentTool.__init__`：headless 未显式设置时调用环境检测
- [ ] 4. 修改 `_do_execute` 返回格式：`[PageAgent STATUS] Steps | Duration | Session` + `Mode` + `URL` + `Title`
- [ ] 5. 同步修改 `_do_screenshot`、`_do_get_page_info`、`_do_close_session` 的返回格式（保持一致风格，非必须，可选）
- [ ] 6. 在 `ToolCallBlock.tsx` 中新增 `parsePageAgentResult()` 解析函数
- [ ] 7. 在 `ToolCallBlock.tsx` 中新增 `page_agent` 专属渲染分支
- [ ] 8. 实现 Loading 状态区分（headed 提示 vs headless 提示）
- [ ] 9. 编写测试：`_detect_display_available` 在 macOS/Linux/Docker 下的行为
- [ ] 10. 编写测试：`_do_execute` 返回格式解析
- [ ] 11. 编写测试：`parsePageAgentResult` 正则解析正确性
- [ ] 12. 端到端验证：有桌面环境 → 浏览器窗口弹出 + Chat 页面显示专属卡片

## 6. Test Coverage

| 测试场景 | 验证内容 |
|----------|----------|
| 环境检测 macOS | 有 console 登录 → True；SSH 无 GUI → False |
| 环境检测 Linux | 有 DISPLAY → True；Docker 无 DISPLAY → False |
| headless 配置优先级 | 用户显式设置 → 使用用户值；None → 自动检测 |
| 返回值格式 SUCCESS | `[PageAgent SUCCESS] Steps: N \| Duration: Nms \| Session: {id}` 格式正确 |
| 返回值格式 ERROR | `[PageAgent ERROR]` + 错误信息 |
| 前端解析 | `parsePageAgentResult` 正确提取 status/steps/duration/session/url/title/body |
| 前端解析容错 | 旧格式（无 `[PageAgent ...]` 头）→ 返回 null，降级为通用渲染 |
| 专属卡片渲染 | 折叠/展开正常；URL 可点击；状态 badge 颜色正确 |
| Loading 状态 | headed 模式 → "查看桌面浏览器窗口"；headless → "Browsing..." |

## 7. TODO（后续 Spec）

以下功能不在本次 Spec 范围内，列为后续迭代：

- **无桌面模式 screencast 内嵌**：在 ToolCallBlock 中嵌入实时 screencast 帧流（执行中）+ 最终截图（完成后）+ activity 步骤列表
- **无桌面模式 ToolCallBlock 交互增强**：screencast 区域可全屏、可暂停、帧率调节
- **BrowserPage 与 ToolCallBlock 联动**：从 ToolCallBlock 卡片跳转到 BrowserPage 查看完整 activity 历史

## 8. Execute Log

（待实现时填写）

## 9. Review Verdict

（待 Review 时填写）

## 10. Risks & Mitigations

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| macOS 环境检测不准确（如 SSH + 屏幕共享） | headed 模式下浏览器窗口在远端弹出，用户看不到 | `who` 命令检测 console 登录；用户可在 config 中显式覆盖 |
| 旧格式返回值的前端兼容 | 升级过渡期间 page_agent 返回旧格式，前端解析失败 | `parsePageAgentResult` 返回 null 时降级为通用渲染 |
| `_detect_display_available` 在 CI 环境中的行为 | CI 无桌面但可能有 DISPLAY（Xvfb） | 检测函数仅影响 headless 默认值，不影响功能正确性 |
| `headless: false` 在 Docker 中误触发 | Playwright 启动失败 | Docker 环境无 DISPLAY → 检测结果为 False → headless: True |
