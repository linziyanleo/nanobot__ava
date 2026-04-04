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

### 8. Page Agent headless 自动检测与配置三态

- 现状：
  - 当前 `PageAgentConfig.headless: bool = True`，用户需手动在 `extra_config.json` 中修改。
  - 原计划改为 `headless: bool | None = None` 三态 + 启动时检测，但会破坏 `model_dump` 序列化契约。
- 设计方向：
  - 不修改 `PageAgentConfig` 模型，新增运行时属性 `PageAgentTool._resolved_headless`，纯内存态。
  - 前端 Loading 提示（headed vs headless）需要前置数据源，不能依赖结果文本中的 `Mode` 字段（时序不对）。
  - 可选方案：tool args 透传 headless 状态、config API、observe WS 事件流附带 headless 状态。
- 后续动作：
  - 独立 Spec 处理；
  - 参考 `page-agent-chat-inline-display.md` §7.1。

## P2

### 9. `b_config_patch` 的长期价值需要重新判断

- 现状：
  - `a_schema_patch` 已是主路径，`b_config_patch` 只是 fork 缺失时的降级方案。
- 风险：
  - 继续维护两套 schema 扩展路径，会放大 spec、测试和 merge 成本。
- 后续动作：
  - 判断是否还需要保留 “字段注入” 这条备用路线；
  - 如果决定不保留，就删 patch、删 spec、删测试，而不是让它永远挂在那儿。

### 10. 统一生命周期管理与前端热更新

- **详细 Spec**：[2026-04-04_lifecycle-and-frontend-hotupdate.md](./tasks/2026-04-04_lifecycle-and-frontend-hotupdate.md)
- **替代**：[2026-04-02_gateway-lifecycle-supervisor-redesign.md](./tasks/2026-04-02_gateway-lifecycle-supervisor-redesign.md)（方向继承）、[2026-04-04_restart-flow-analysis.md](./tasks/2026-04-04_restart-flow-analysis.md)（已 deprecated）
- 目标：建立可信的生命周期控制面，支持 self-improvement loop 的 restart 需求，同时解耦前端更新与 gateway 重启。
- 核心架构：
  - **Layer A**：LifecycleManager（`ava/runtime/lifecycle.py`）— supervisor-first 生命周期后端
  - **Layer B**：GatewayControlTool（`ava/tools/gateway_control.py`）— 统一 status/restart 控制面
  - **Layer C**：前端热更新（rebuild API + version.json + toast）— 与 gateway 正交
  - **Layer D**：page-agent-runner 独立重启 — 子进程管控
- 现状：
  - 旧 `ava/skills/restart_gateway/` 仍在使用，方向需废弃
  - `GatewayService` 仍 shell 到旧脚本
  - `GatewayStatus` 缺少 lifecycle 字段
- 后续动作：
  - Phase A（P0）：LifecycleManager + gateway_control tool + 删除旧脚本
  - Phase B（P1）：前端 rebuild API + 版本检测
  - Phase C（P2）：page-agent-runner 独立重启

## 远期方向

### 11. Nanobot 自改进闭环（Self-Improvement Loop）

- **详细 Spec**：[2026-04-04_coding-cli-and-self-improvement-loop.md](./tasks/2026-04-04_coding-cli-and-self-improvement-loop.md)
- 目标：Nanobot 具备调用 Claude Code 和 Codex 改进自身的能力，并通过工具链对自身进行测试验证。
- 核心架构决策：
  1. **SpecAnchor 是 agent 间的共享内存协议**：会话知识持久化到 Spec，CLI Agent 通过读取 Spec 获取上下文，消除信息孤岛
  2. **统一 BackgroundTaskStore**：不 patch 上游 SubagentManager（热区），在 `ava/agent/bg_tasks.py` 创建统一后台任务上下文层，"写多读一"模式覆盖 coding/cron/subagent
  3. **origin_session_key 一等化**：直传正确的 session_key，不从 channel/chat_id 反推（修复 console 路由 bug）
  4. **通知与上下文注入分离**：async_result 只是 UI 通知；模型感知后台任务通过 context_patch digest 注入 system prompt
  5. **结果验证而非过程监督**：不关心 CLI Agent 的中间推理，只关心 `git diff` + 测试 + Spec 一致性检查
  6. **三层实现**：Skill 做编排 → Tool 做封装 → Script 做检查
- 前置条件（当前进度）：
  - ✅ `claude_code` sync + async wiring（Phase 1 完成）
  - ✅ BackgroundTaskStore + SQLite 持久化 + context digest 注入
  - ✅ session_key 路由修复（`_current_session_key` + `set_context` 直传）
  - ✅ async_result 落盘 → 通知链路闭环
  - ✅ Codex CLI 工具（独立实现，共享 BackgroundTaskStore）
  - ✅ Page Agent + 浏览器持久化 + LLM usage 记录
  - ✅ Token Stats 异常终止/取消记录
  - ✅ SpecAnchor 体系 + specanchor-check.sh
  - ❌ Lifecycle backend（→ 依赖 §10 完成）
  - ❌ cron/subagent observer 接入 BackgroundTaskStore
  - ❌ Telegram 命令注册（降级）
- 关键风险：
  - 自改进循环可能陷入"无效修改 → 测试失败 → 回退"的死循环，需要引入改动预算（$5/次）和回退阈值（最多重试 2 次）
  - Spec 质量是整个系统的瓶颈——低质量 Spec 导致低质量输出
  - 对 `nanobot/` 目录的隔离约束必须在自改进链路中严格执行
  - **Lifecycle backend 是当前唯一硬依赖**：coding task 改完代码后需要可靠的 restart → verify 闭环
- 后续动作：
  - Phase 2 剩余：cron/subagent observer + Telegram 命令
  - Phase 2.5（可选）：streaming 增强
  - Phase 3：自改进闭环 Skill 设计与实现（依赖 §10 lifecycle backend）
