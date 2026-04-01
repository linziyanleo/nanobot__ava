# Module Spec: a_schema_patch — Config Schema Fork 注入

> 文件：`ava/patches/a_schema_patch.py`
> 状态：✅ 已实现（Phase 2）
> 执行顺序：**第 1 个**（文件名 `a_` 前缀确保字母序最先）

---

## 1. 模块职责

用 `ava/forks/config/schema.py` 完整替换 `nanobot.config.schema` 模块，使系统支持多模型配置、Console 配置、ClaudeCode 工具配置等扩展字段。

### 新增/扩展的类和字段
- `AgentDefaults`：新增 `vision_model`、`mini_model`、`image_gen_model`、`memory_tier`、`memory_window`、`context_compression`、`in_loop_truncation`、`history_summarizer`
- `ConsoleConfig`：Console 启用/端口/密钥配置
- `ClaudeCodeConfig`：Claude Code 子代理配置
- `TokenStatsConfig`：Token 使用统计配置
- Channel Config 类：`TelegramConfig`、`FeishuConfig` 等（从各 channel 模块集中到 schema）
- `GatewayConfig.console` 字段

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `sys.modules["nanobot.config.schema"]` | 模块替换 | 在 sys.modules 中直接替换整个模块 |
| `nanobot.config.schema` 属性 | 属性覆盖 | 同步更新 `nanobot.config` 包的 `schema` 属性 |

### 拦截详情

- **原始行为**：`nanobot.config.schema` 定义基础的 Pydantic 配置模型（`AgentDefaults`、`GatewayConfig` 等）
- **修改后行为**：整个模块被替换为 `ava/forks/config/schema.py`，包含所有上游字段 + 扩展字段
- **Patch 方式**：`importlib.util.spec_from_file_location` 加载 fork 模块 → 设置 `_ava_fork = True` 标记 → 替换 `sys.modules` 条目 → 更新包属性

---

## 3. 幂等性保证

- 检查 `sys.modules["nanobot.config.schema"]._ava_fork` 标记
- 若已标记为 True，直接跳过，返回 "schema already patched (skipped)"
- Fork 文件不存在时优雅降级，返回描述性消息

---

## 4. 依赖关系

### 上游依赖
- `nanobot.config.schema` — 替换目标
- `nanobot.config` 包 — 属性更新目标

### Sidecar 内部依赖
- `ava/forks/config/schema.py` — Fork 源文件（必须存在）
- `ava.launcher.register_patch` — 自注册机制

### 被依赖（下游 patch 依赖本 patch）
- `b_config_patch.py` — 检测 `_ava_fork` 标记决定是否跳过
- `tools_patch.py` — 读取 `config.tools.claude_code`（fork schema 新字段）
- `loop_patch.py` — 间接依赖（通过 config 读取扩展字段）

---

## 5. 与 b_config_patch 的关系

- `a_schema_patch` 是**完整替换**方案（推荐）
- `b_config_patch` 是**字段注入**方案（降级备选）
- 当 fork 文件存在时：`a_schema_patch` 执行，`b_config_patch` 自动跳过
- 当 fork 文件不存在时：`a_schema_patch` 跳过，`b_config_patch` 通过 Pydantic 动态注入字段

---

## 6. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| Fork 替换成功 | `sys.modules["nanobot.config.schema"]._ava_fork` 为 True |
| 扩展字段存在 | `AgentDefaults` 包含 `vision_model`、`mini_model`、`image_gen_model` 等字段 |
| ConsoleConfig | `GatewayConfig.console` 字段可用 |
| 幂等性 | 两次调用不报错 |
| Fork 文件缺失 | 优雅降级，不影响系统启动 |
| 与 config_patch 互斥 | fork 存在时 config_patch 跳过 |
| 后续 import 正确 | 其他模块 `from nanobot.config.schema import X` 获取到 fork 版本 |
