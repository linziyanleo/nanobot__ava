# Tool Usage Notes

Tool signatures are provided automatically via function calling.
This file documents non-obvious constraints and usage patterns.

## exec — Safety Limits

- Commands have a configurable timeout (default 60s)
- Dangerous commands are blocked (rm -rf, format, dd, shutdown, etc.)
- Output is truncated at 10,000 characters
- `restrictToWorkspace` config can limit file access to the workspace

## image_gen — Image Generation & Editing

- Generate images from text prompts using AI image generation
- Edit existing images by providing a reference image + edit instruction
- Generated images are saved to `~/.nanobot/media/generated/`
- Use the `message` tool with `media` parameter to send generated images to the user

## page_agent — 网页自然语言操控

使用 page-agent + Playwright 通过自然语言指令操控网页。支持持久化浏览器会话。

### 能力范围

- **结构化网页操控**：导航、点击、填表、选择、滚动、拖拽等
- **DOM 文本提取**：读取页面文本内容、表单值、列表、表格数据
- **多步骤任务**：自动规划并执行多步操作（如登录→导航→填表→提交）
- **会话复用**：通过 `session_id` 在多次调用间保持浏览器状态
- **截图存档**：截图自动保存到 MediaService，可通过 media 页面查看

### 局限性

- **无法读取图像/Canvas 内容**：page-agent 基于 DOM 文本提取，无法识别图片、Canvas、SVG 渲染内容
- **视觉效果验证受限**：CSS 动画、颜色、布局等视觉表现需配合 `screenshot` 动作确认
- **复杂交互可能不稳定**：拖拽排序、复杂手势、Shadow DOM 内操作可能失败
- **受网页结构影响大**：前端展示与 DOM 结构不一致时（如虚拟滚动、iframe），可能忽略实际显示内容

### 何时使用 page_agent vs 其他工具

| 场景 | 推荐工具 |
|------|---------|
| 需要操控页面（点击/填表/导航） | `page_agent` |
| 需要验证页面视觉效果 | `page_agent`（screenshot）+ `vision` |
| 仅需抓取网页文本内容 | `web_fetch`（更快、更轻量） |
| 需要抓取 JavaScript 渲染的内容 | `page_agent`（get_page_info） |
| 需要读取图片或 Canvas 中的内容 | `page_agent`（screenshot）+ `vision` |

### 动作说明

| action | 必需参数 | 说明 |
|--------|---------|------|
| `execute` | `instruction` | 执行自然语言操作指令，可选 `url` 导航、`session_id` 复用会话 |
| `screenshot` | `session_id` | 对指定会话截图并存档到 MediaService |
| `get_page_info` | `session_id` | 获取当前页面 URL、标题、视口信息 |
| `close_session` | `session_id` | 关闭指定浏览器会话 |

### 典型用法

```
1. execute(url="https://example.com", instruction="找到搜索框并搜索 nanobot")
   → 返回 session_id, 页面标题, 操作结果
2. screenshot(session_id="s_xxx")
   → 截图保存, 配合 vision 验证视觉效果
3. close_session(session_id="s_xxx")
   → 释放浏览器资源
```

## cron — Scheduled Reminders

- Please refer to cron skill for usage.
