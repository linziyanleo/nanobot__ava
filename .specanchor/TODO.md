# Sidecar TODO

> 记录当前 sidecar 的技术债、merge 热区和需要持续盯住的问题。
> 原则：这里只记“还没闭环”的事项，不重复记录已经稳定的能力。

## P0

### 1. `context_patch` / `loop_patch` 配置读取口径漂移

- 现状：
  - [context_patch_spec.md](./modules/context_patch_spec.md) 已明确写出，当前实现仍通过旧的 `history_compressor.*` 路径读取参数并带默认回退。
  - 实际设计目标是读取 `config.agents.defaults.context_compression` / `history_summarizer`。
- 风险：
  - spec 和代码会继续漂；
  - fork schema 明明已经有新配置结构，但运行时没真正吃进去。
- 后续动作：
  - 对齐 `loop_patch.py` 的参数读取路径；
  - 同步更新 `tests/patches/test_context_patch.py`、`tests/patches/test_loop_patch.py`；
  - 确认 `context_patch_spec.md` 从“现状说明”切回“实现即规范”。

### 2. fork schema 与 upstream schema 的残余差异需要持续收敛

- 现状：
  - 这次 merge 后已补 `ApiConfig` / `Config.api`；
  - 但 `tests/guardrails/test_schema_drift.py` 中仍保留一批 `INTENTIONAL_REMOVALS` / `INTENTIONAL_DEFAULT_DRIFTS`。
- 当前已登记的差异重点：
  - `MCPServerConfig.type`
  - `MCPServerConfig.enabled_tools`
  - `ProvidersConfig.byteplus`
  - `ProvidersConfig.byteplus_coding_plan`
  - `ProvidersConfig.mistral`
  - `ProvidersConfig.ollama`
  - `ProvidersConfig.ovms`
  - `ProvidersConfig.stepfun`
  - `ProvidersConfig.volcengine_coding_plan`
  - `WebSearchConfig.provider`
  - `WebSearchConfig.base_url`
  - `ProvidersConfig.openai_codex` / `github_copilot` 的默认值差异
- 风险：
  - 这些差异如果长期不清，会让 schema drift test 变成“白名单堆积器”。
- 后续动作：
  - 逐项判断是“sidecar 特意不跟”还是“应该同步”；
  - 能同步的尽快同步，不能同步的在 spec 中写清边界。

## P1

### 3. `loop_patch` 与上游 hook 体系进入同一热区

- 现状：
  - 上游已引入 `AgentHook` / `CompositeHook`；
  - 我们的 `loop_patch` 仍直接包装 `AgentLoop.__init__`、`_run_agent_loop`、`_process_message`、`_save_turn`。
- 风险：
  - 后续上游继续重构 runner / hook / loop 生命周期时，`loop_patch` 是最容易破的 patch。
- 后续动作：
  - 评估 token stats、usage 捕获、history bookkeeping 中哪些能力可以迁移到 hook 层；
  - 尽量减少对 `AgentLoop` 私有流程的深包装。

### 4. `console_patch` 与上游 `serve` 命令共享 CLI 热区

- 现状：
  - 上游 `nanobot.cli.commands` 新增 OpenAI-compatible API `serve` 命令；
  - `gateway` / `agent` 继续把更多 `AgentDefaults` 参数透传到 `AgentLoop`，`channels` 子命令也开始显式支持 `--config`；
  - sidecar 的 `console_patch` 仍通过包装 `gateway` callback + 临时替换 `asyncio.run` 来注入 Console。
- 风险：
  - `cli.commands` 继续演进时，Console patch 很容易被间接影响；
  - 如果 wrapper 内自己 `load_config()` 的时机或路径选错，就可能绕开用户传入的 config path；
  - 如果未来 Console 要和 `serve` 共存，入口策略需要重新评估。
- 后续动作：
  - 每次 upstream 改 `nanobot/cli/commands.py` 都必须先查 [patch_map.md](./patch_map.md)；
  - 增加一条带自定义 `--config` 的 console/gateway 回归，确认 patch 没有回退到默认配置；
  - 中期评估是否应把 Console 注入点从 `gateway` callback 下沉到更稳定的 runtime 入口。

### 5. `context_patch` 与上游 `ContextBuilder` / `LLMProvider` 开始出现消息清洗重叠

- 现状：
  - upstream 已在 `ContextBuilder.build_messages()` 原生合并连续同角色消息；
  - sidecar 仍在 `context_patch` 的 provider wrapper 里做 `sanitize_messages()`，同时负责历史压缩与分类记忆注入。
- 风险：
  - 如果 upstream 继续把 trailing assistant / provider-specific sanitize 做进核心层，context patch 很容易开始重复做同一件事；
  - “历史压缩 / 记忆注入”和“消息清洗”耦在一个 patch 里，会让 overlap 判断越来越难。
- 后续动作：
  - 下次 upstream 改 `nanobot/agent/context.py` 或 `nanobot/providers/base.py` 时，优先评估 `sanitize_messages()` 是否应收窄为 trailing assistant / orphan cleanup；
  - 若要继续保留 provider wrapper，至少把“历史处理”和“协议兼容清洗”的职责边界写得更清楚。

### 6. `channel_patch` 与上游 Telegram `send_delta` 存在部分重叠

- 现状：
  - 上游已覆盖 `stream_id` / `not_modified`；
  - sidecar 仍额外修 `tool-only turn` typing 清理和 `message_id is None` fallback。
- 风险：
  - 以后上游若继续补 Telegram streaming，patch 很容易开始重复做同一件事。
- 后续动作：
  - 每次 upstream 改 `nanobot/channels/telegram.py`，先对照 [patch_map.md](./patch_map.md) 再决定 patch 是否收窄；
  - 一旦上游覆盖这两个边界，就删掉对应 patch 分支，而不是继续叠逻辑。

### 7. 全量测试的本机环境依赖不稳定

- 现状：
  - 当前机器跑 `uv run pytest tests/ -q` 会在 Matrix 测试链路缺少 `nio/python-olm` 构建依赖时失败；
  - `uv sync --all-extras` 还会卡在 `python-olm`，缺 `cmake/gmake`。
- 风险：
  - 容易把“环境没齐”误判成“merge 代码坏了”。
- 后续动作：
  - 补一份本机依赖安装说明，至少说明 Matrix / `python-olm` 需要的构建工具；
  - 或者明确区分“patch/guardrails 回归”和“全量含 matrix extras 回归”。

## P2

### 8. `b_config_patch` 的长期价值需要重新判断

- 现状：
  - `a_schema_patch` 已是主路径，`b_config_patch` 只是 fork 缺失时的降级方案。
- 风险：
  - 继续维护两套 schema 扩展路径，会放大 spec、测试和 merge 成本。
- 后续动作：
  - 判断是否还需要保留 “字段注入” 这条备用路线；
  - 如果决定不保留，就删 patch、删 spec、删测试，而不是让它永远挂在那儿。
