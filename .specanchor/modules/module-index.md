# Module Spec 索引

> 2026-04-09 起，canonical Module Spec 统一使用 `*.spec.md` 文件名并存放在 `.specanchor/modules/`。
> 旧版 legacy 命名文件已移除；请统一使用 `*.spec.md` 作为唯一主入口。

| 模块名 | 模块路径 | Spec 文件 | 状态 | 说明 |
|---|---|---|---|---|
| Bus Console 监听器 | `ava/patches/bus_patch.py` | [ava-patches-bus_patch.spec.md](./ava-patches-bus_patch.spec.md) | active | Module Spec: bus_patch — Bus Console + Observe 监听器 |
| 分类记忆系统 | `ava/agent/categorized_memory.py` | [ava-agent-categorized_memory.spec.md](./ava-agent-categorized_memory.spec.md) | active | Module Spec: categorized_memory — 分类记忆系统 |
| Telegram 批处理 Patch | `ava/patches/channel_patch.py` | [ava-patches-channel_patch.spec.md](./ava-patches-channel_patch.spec.md) | active | Module Spec: channel_patch — Telegram 消息批处理与 send_delta 修复 |
| Claude Code 工具 | `ava/tools/claude_code.py` | [ava-tools-claude_code.spec.md](./ava-tools-claude_code.spec.md) | review | Module Spec: claude_code_tool — Claude Code CLI 工具、后台任务上下文与完成回调 |
| Codex 工具 | `ava/tools/codex.py` | [ava-tools-codex.spec.md](./ava-tools-codex.spec.md) | active | Module Spec: Codex Tool |
| 统一命令系统 | `ava/agent/commands.py` | [ava-agent-commands.spec.md](./ava-agent-commands.spec.md) | draft | Module Spec: commands — 统一命令系统 |
| 配置字段注入 Patch | `ava/patches/b_config_patch.py` | [ava-patches-b_config_patch.spec.md](./ava-patches-b_config_patch.spec.md) | active | Module Spec: b_config_patch — Config Schema 字段注入（降级方案） |
| 浏览器预览页 | `console-ui/src/pages/BrowserPage` | [console-ui-src-pages-BrowserPage.spec.md](./console-ui-src-pages-BrowserPage.spec.md) | active | Module Spec: console_browser_page — console-ui 浏览器预览链路 |
| Console 启动 Patch | `ava/patches/console_patch.py` | [ava-patches-console_patch.spec.md](./ava-patches-console_patch.spec.md) | active | Module Spec: console_patch — Web Console 独立服务启动 |
| 上下文构建 Patch | `ava/patches/context_patch.py` | [ava-patches-context_patch.spec.md](./ava-patches-context_patch.spec.md) | active | Module Spec: context_patch — 历史处理与记忆注入 |
| 历史压缩器 | `ava/agent/history_compressor.py` | [ava-agent-history_compressor.spec.md](./ava-agent-history_compressor.spec.md) | active | Module Spec: history_compressor — 历史压缩器 |
| 历史摘要器 | `ava/agent/history_summarizer.py` | [ava-agent-history_summarizer.spec.md](./ava-agent-history_summarizer.spec.md) | active | Module Spec: history_summarizer — 历史摘要器 |
| AgentLoop 注入 Patch | `ava/patches/loop_patch.py` | [ava-patches-loop_patch.spec.md](./ava-patches-loop_patch.spec.md) | active | Module Spec: loop_patch — AgentLoop 属性注入、Token 统计与实时广播 |
| Onboard 兼容 Patch | `ava/patches/c_onboard_patch.py` | [ava-patches-c_onboard_patch.spec.md](./ava-patches-c_onboard_patch.spec.md) | active | Module Spec: c_onboard_patch — onboard refresh 旧配置兼容层 |
| Page Agent 运行时 | `ava/tools/page_agent.py` | [ava-tools-page_agent.spec.md](./ava-tools-page_agent.spec.md) | active | Module Spec: page_agent_runtime — PageAgent Tool 与 Node Runner 调用链 |
| Provider 前缀兼容 Patch | `ava/patches/provider_prefix_patch.py` | [ava-patches-provider_prefix_patch.spec.md](./ava-patches-provider_prefix_patch.spec.md) | active | Module Spec: provider_prefix_patch |
| Schema Fork Patch | `ava/patches/a_schema_patch.py` | [ava-patches-a_schema_patch.spec.md](./ava-patches-a_schema_patch.spec.md) | active | Module Spec: a_schema_patch — Config Schema 继承式 Fork 注入 |
| 技能加载 Patch | `ava/patches/skills_patch.py` | [ava-patches-skills_patch.spec.md](./ava-patches-skills_patch.spec.md) | active | Module Spec: skills_patch — SkillsLoader 三源发现与禁用过滤 |
| SQLite 存储 Patch | `ava/patches/storage_patch.py` | [ava-patches-storage_patch.spec.md](./ava-patches-storage_patch.spec.md) | active | Module Spec: storage_patch — SQLite 存储层替换 |
| 模板覆盖 Patch | `ava/patches/templates_patch.py` | [ava-patches-templates_patch.spec.md](./ava-patches-templates_patch.spec.md) | active | Module Spec: templates_patch |
| 自定义工具注入 Patch | `ava/patches/tools_patch.py` | [ava-patches-tools_patch.spec.md](./ava-patches-tools_patch.spec.md) | active | Module Spec: tools_patch — 自定义工具注入 |
| 转写代理 Patch | `ava/patches/transcription_patch.py` | [ava-patches-transcription_patch.spec.md](./ava-patches-transcription_patch.spec.md) | active | Module Spec: transcription_patch — Groq 转写代理注入 |
