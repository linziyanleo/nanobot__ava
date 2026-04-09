# Module Spec: templates_patch

> 文件：`ava/patches/templates_patch.py`
> 注册名：`workspace_templates_overlay`

## 目标

- 用 `ava/templates/` 覆盖工作区 bootstrap 模板的运行时拷贝。
- 保持上游模板可升级，同时让 sidecar 的 `AGENTS.md`、`SOUL.md`、`TOOLS.md`、记忆模板持续生效。

## 拦截点

- `nanobot.utils.helpers.sync_workspace_templates`

## 行为

- 先执行 upstream 默认模板同步。
- 再把 `ava/templates/` 中的 sidecar 模板覆盖到目标 workspace。
- 未命中的模板继续沿用 upstream 默认行为。
- 二次调用 `apply_templates_patch()` 必须保持幂等。

## 验证

- `tests/guardrails/test_spec_sync.py`
- `tests/cli/test_commands.py`
