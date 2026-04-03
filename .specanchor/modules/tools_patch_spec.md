# Module Spec: tools_patch — 自定义工具注入

> 文件：`ava/patches/tools_patch.py`
> 状态：✅ 已实现（Phase 1，Phase 2 更新配置读取）

---

## 1. 模块职责

将 ava 自定义工具注入到 `AgentLoop` 的工具注册流程中。当前实现包含 4 个固定工具（`claude_code`、`image_gen`、`vision`、`send_sticker`）和 2 个条件工具（`page_agent`、`memory`），使 Agent 具备代码子代理、图像生成、视觉识别、贴纸发送、网页操控和分类记忆管理能力。

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `AgentLoop._register_default_tools` | 方法替换 | 在上游默认工具注册完成后，追加注册自定义工具 |

### 拦截详情

- **原始行为**：`AgentLoop._register_default_tools(self)` 注册上游内置工具（filesystem、web、shell、cron、mcp 等）
- **修改后行为**：先调用原始方法完成内置工具注册，然后追加注册自定义工具；其中 `page_agent` 受 `config.tools.page_agent.enabled` 控制，`memory` 受 `self.categorized_memory` 是否存在控制
- **Patch 方式**：保存原始方法引用 → 定义包装函数 → 替换类方法

---

## 3. 注入工具列表

| 工具名 | 类 | 源文件 | 功能 |
|--------|-----|--------|------|
| `claude_code` | `ClaudeCodeTool` | `ava/tools/claude_code.py` | Claude Code 子代理，支持代码读写、执行 |
| `image_gen` | `ImageGenTool` | `ava/tools/image_gen.py` | 图片生成（集成外部 API） |
| `vision` | `VisionTool` | `ava/tools/vision.py` | 图片/视觉内容识别 |
| `send_sticker` | `StickerTool` | `ava/tools/sticker.py` | Telegram 贴纸发送 |
| `page_agent` | `PageAgentTool` | `ava/tools/page_agent.py` | 通过 page-agent + Playwright 执行网页自然语言操作，并向 console 输出实时预览事件 |
| `memory` | `MemoryTool` | `ava/tools/memory_tool.py` | 分类记忆的增删改查 |

---

## 4. 依赖关系

### 上游依赖
- `nanobot.agent.loop.AgentLoop` — 拦截目标
- `nanobot.config.loader.load_config` — 读取配置

### Sidecar 内部依赖
- `ava.tools.*` — 6 个工具实现类（其中 `page_agent` / `memory` 为条件注册）
- `ava.launcher.register_patch` — 自注册机制
- `ava.patches.loop_patch` — 提供 `self.token_stats`、`self.media_service`、`self.db`（间接依赖）

### 运行时依赖
- `AgentLoop` 实例的属性：`workspace`、`provider`、`model`、`subagents`、`tools`
- 可选属性（`getattr` 安全访问）：`token_stats`、`media_service`、`categorized_memory`、`db`

---

## 5. 配置依赖

从 `config.json` 读取的配置项（通过 fork schema）：

| 配置路径 | 说明 | 降级策略 |
|----------|------|----------|
| `config.tools.claude_code` | ClaudeCodeConfig 对象（model、max_turns、allowed_tools、timeout） | 若不存在则使用硬编码默认值 |
| `config.tools.page_agent` | PageAgentConfig 对象（启用开关、LLM、浏览器、截图参数） | 若不存在则以默认配置创建 `PageAgentTool` |
| `config.agents.defaults.claude_code_model` | Claude Code 模型（旧路径，降级使用） | 默认 `claude-sonnet-4-20250514` |
| `config.agents.defaults.vision_model` | 视觉识别模型 | 不存在时使用 `self.model` |

### 配置读取优先级（ClaudeCode）
1. `config.tools.claude_code.model`（fork schema 新路径）
2. `config.agents.defaults.claude_code_model`（旧路径）
3. 硬编码默认值 `"claude-sonnet-4-20250514"`

---

## 6. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 工具注册 | Patch 后 `AgentLoop.tools` 中包含固定工具，并按条件追加 `page_agent` / `memory` |
| 上游工具保留 | Patch 不影响上游默认工具的注册 |
| fork schema 配置 | `config.tools.claude_code` 存在时正确读取 |
| PageAgent 开关 | `config.tools.page_agent.enabled=false` 时不注册 `page_agent` |
| vanilla schema 降级 | fork 未加载时使用 `agents.defaults` 路径 |
| vision_model | 配置 `vision_model` 时 VisionTool 使用指定模型 |
| 可选属性缺失 | `token_stats`/`media_service`/`categorized_memory` 不存在时不报错 |
| `MemoryTool` 条件注册 | `categorized_memory` 为 None 时不注册 `MemoryTool` |
| 拦截点缺失 | `AgentLoop` 无 `_register_default_tools` 时优雅跳过 |
| 幂等性 | 两次调用不会重复注册工具 |
