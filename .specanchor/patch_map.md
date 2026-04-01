# Patch Map

> 后续开发和合并 upstream 代码前，必须先对照本文件。
> 目标不是复述 patch 名称，而是快速判断：当前 patch 是继续保留、收窄、上推还是删除。

## 使用方式

### 开发 / merge 前必做

1. 拉取上游：

```bash
git fetch upstream main
```

1. 找出 upstream 这次改了哪些 `nanobot/` 文件：

```bash
git diff --name-only $(git merge-base HEAD upstream/main)..upstream/main -- nanobot/
```

1. 用下面的 patch map 对照这些改动落在哪些 patch 热区。
2. 对每个命中的 patch，按“取舍规则”判断：
   - 上游已完整覆盖：删除 patch，并同步删测试 / spec
   - 上游部分覆盖：收窄 patch，只保留 sidecar 独有逻辑
   - 上游新增基础能力而 fork 未同步：优先同步 fork / spec，不要先加白名单
   - 完全无关：保留 patch，仅回归测试
3. 变更完成后至少回归：

```bash
uv run pytest tests/patches -q
uv run pytest tests/guardrails -q
```

1. 若本次改动涉及 `nanobot/`，同步更新 `ava/UPSTREAM_VERSION`。

## 取舍规则

### `保留`

- 上游尚未覆盖该能力；
- 或该 patch 明确承载 sidecar 独有能力。

### `收窄`

- 上游已覆盖 patch 中的一部分逻辑；
- 只保留 sidecar 额外修复 / 扩展的最小差异。

### `删除`

- 上游已完整覆盖功能；
- sidecar 不再需要额外行为；
- patch 留着只会增加 merge 成本或行为分叉。

### `上推`

- 该 patch 的逻辑已被证明是通用能力；
- 且 sidecar 继续维护这段代码的成本高于提 upstream PR。

## 当前 Patch 全景

| Patch | 上游触点 | 当前职责 | 热度 | 当前判断 | 取舍信号 | 最低验证 |
|------|----------|----------|------|----------|----------|----------|
| `a_schema_patch.py` | `nanobot/config/schema.py` | 用 fork 完整替换 schema，承载 Console / ClaudeCode / TokenStats / Channel configs / API config 等扩展 | 高 | 保留，但必须持续同步 | upstream 新增基础配置类或字段时，优先同步 fork；若 sidecar 扩展显著减少，可考虑退化为更窄的 additive patch | `tests/patches/test_schema_patch.py` + `tests/guardrails/test_schema_drift.py` |
| `b_config_patch.py` | `nanobot.config.schema.AgentDefaults` | fork 缺失时的降级字段注入 | 中 | 倾向后续删除 | 若 fork 路线稳定且不再需要 fallback，可整体移除 | `tests/patches/test_config_patch.py` |
| `bus_patch.py` | `nanobot.bus.queue.MessageBus.publish_outbound` | Console queue listener 注入 | 低 | 保留 | 若 upstream 原生提供 console listener queue，再删除 | `tests/patches/test_bus_patch.py` |
| `channel_patch.py` | `nanobot/channels/telegram.py` | Telegram 消息批处理 + `send_delta` 边界修复 | 中高 | 保留，但要持续收窄 | upstream 一旦覆盖 typing 清理 / `message_id is None` fallback，就删对应分支；若 upstream 出现原生 batching，整体 patch 需重判 | `tests/patches/test_channel_patch.py` |
| `console_patch.py` | `nanobot/cli/commands.py` | 在 gateway 启动时并行注入 Web Console | 高 | 保留，但属于 CLI 热区 | upstream 若重构 gateway 启动方式，必须先读 patch spec；若未来有官方 console/runtime hook，再考虑迁移 | `tests/patches/test_console_patch.py` |
| `context_patch.py` | `nanobot.agent.context.ContextBuilder`、`LLMProvider.chat_*` | 历史压缩、分类记忆注入、非 Claude provider 消息清洗 | 高 | 保留，但配置口径需要修债 | upstream 若把短期历史聚焦 / message sanitize 做进核心层，patch 应收窄；当前先修参数读取漂移 | `tests/patches/test_context_patch.py` |
| `loop_patch.py` | `nanobot/agent/loop.py` | db/media/token stats/history 相关注入与 `_save_turn` 修复 | 很高 | 保留，但属于首要热区 | 上游 hook / runner / loop 每次变动都要重看；能迁到 hook 层的逻辑逐步迁出，减少深包装 | `tests/patches/test_loop_patch.py` |
| `skills_patch.py` | `nanobot.agent.skills.SkillsLoader` | 三源 skill 发现 + disabled filter | 中 | 保留 | 若 upstream 支持多源发现和 enable/disable 管理，再重判是否删 patch | `tests/patches/test_skills_patch.py` |
| `storage_patch.py` | `nanobot.session.manager.SessionManager` | SQLite 持久化、增量保存、db 共享 | 中 | 保留 | upstream 若原生引入等价 SQLite/session store，再看是否整体替换 | `tests/patches/test_storage_patch.py` |
| `tools_patch.py` | `AgentLoop._register_default_tools` | 注入 `claude_code` / `image_gen` / `vision` / `send_sticker` / `memory` | 高 | 保留 | upstream 若原生支持这些工具或提供稳定扩展点，可转向更轻的注册 hook；不要在深热区反复堆逻辑 | `tests/patches/test_tools_patch.py` |
| `transcription_patch.py` | `nanobot/providers/transcription.py` | 给 Groq transcription 注入 proxy | 低 | 保留 | upstream 一旦支持 proxy 配置，直接删除 | `tests/patches/test_transcription_patch.py` |

## 当前热区提醒

### 热区 1: `nanobot/agent/loop.py`

- 关联 patch：`loop_patch`、`tools_patch`、间接影响 `context_patch`
- 现状：上游已引入 `AgentHook` / `CompositeHook`
- 策略：每次 merge 这里都先判断能否把 sidecar 逻辑迁到 hook 层，而不是继续深包 `_process_message`

### 热区 2: `nanobot/cli/commands.py`

- 关联 patch：`console_patch`
- 现状：上游已新增 `serve` 命令，CLI 继续扩展
- 策略：任何改 CLI 入口的需求，都先判断是不是应该做更稳定的 runtime hook，而不是继续盯死 `gateway` callback

### 热区 3: `nanobot/config/schema.py`

- 关联 patch：`a_schema_patch`、`b_config_patch`
- 现状：fork 仍是 sidecar 最大的 merge 成本来源
- 策略：上游新增基础字段优先同步；只有明确“不跟”的字段才允许进入 `INTENTIONAL_REMOVALS`

### 热区 4: `nanobot/channels/telegram.py`

- 关联 patch：`channel_patch`
- 现状：上游 streaming 逻辑持续演进
- 策略：保持 patch 极窄，只保留 upstream 尚未覆盖的边界修复
