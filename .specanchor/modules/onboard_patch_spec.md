# Module Spec: c_onboard_patch — onboard refresh 旧配置兼容层

> 文件：`ava/patches/c_onboard_patch.py`
> 状态：✅ 已实现
> 执行顺序：**第 4 个**（位于 `bus_patch` 之后、`channel_patch` 之前）

---

## 1. 模块职责

只拦截 `nanobot onboard` 的「已有 config + 非 wizard + 选择 N(refresh)」分支。

目标不是改写整条 onboard 流程，而是修复旧 sidecar `config.json` 的 refresh 写回语义：

- 保留旧字段和旧 key 形状
- 只补当前 schema 缺失的默认字段
- 不把 `extra_config.json` 的 overlay 值固化回 `config.json`

这让真实 `~/.nanobot` 旧配置在 refresh 后不会被错误收缩成上游默认结构。

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `nanobot.cli.commands.app.registered_commands[*].callback == onboard` | CLI callback 包装 | 用包装后的 callback 替换原始 `onboard` 命令 |

### 拦截详情

- **原始行为**：
  - 现有配置 + 非 wizard + 选择 refresh 时，执行 `load_config(config_path)` → `save_config(config, config_path)`
  - 由于 `load_config()` 会先把 `extra_config.json` merge 到 base config，再经当前 schema round-trip，旧 sidecar 字段会被收缩，overlay 也会被写回 base config
- **修改后行为**：
  - overwrite 分支保持原样
  - wizard 分支保持原样
  - refresh 分支改为：
    - 直接读取原始 `config.json`
    - 运行 `_migrate_config()` 做最小迁移
    - 用当前 schema 默认结构生成“缺失字段清单”
    - 递归补齐缺失字段，但不覆盖原值
    - 单独处理 `workspace` override

---

## 3. 幂等性保证

- 通过 `onboard_cmd.callback._ava_onboard_patched` 防止重复包装
- 若 Typer app 中找不到 `onboard` 命令，返回 skip 文案并 warning

---

## 4. 依赖关系

### 上游依赖

- `nanobot.cli.commands.onboard`
- `nanobot.config.loader._migrate_config`
- `nanobot.config.loader.get_config_path` / `set_config_path`

### Sidecar 内部依赖

- `a_schema_patch`：refresh 兼容层依赖 fork schema 的 `Config().model_dump(...)` 作为默认结构来源

---

## 5. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 幂等性 | 二次 apply 返回 skipped |
| 拦截点缺失 | `onboard` 命令不存在时优雅跳过 |
| refresh 兼容 | 旧 sidecar config refresh 后保留 `voiceModel` / `contextCompression.maxOldTurns` / `claudeCode.enabled` / `token_stats.record_full_request_payload` |
| overlay 隔离 | `extra_config.json` 中的 `providers.gemini.apiBase` 不会被写回 base config |
| 新默认结构补齐 | refresh 后补上 `api.host`、`gateway.console`、新增 provider 等缺失块 |
