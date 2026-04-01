# Engineering Guardrails Demo

> 面向演讲的演示证据提纲。这里记录的是“如何触发护栏、为什么会失败、修复后为什么转绿”，方便现场稳定复现。

## Demo 1: 误改 `nanobot/` 被 hook 拦截

### 触发条件

- 开发者在当前仓库中 staged 了 `nanobot/` 目录下的改动
- 未设置 `ALLOW_NANOBOT_PATCH=1`

### 执行命令

```bash
bash scripts/install-hooks.sh
git add nanobot/config/schema.py
git commit -m "test guardrail"
```

### 预期失败输出

```text
COMMIT BLOCKED: staged changes under nanobot/ are not allowed by default.
Set ALLOW_NANOBOT_PATCH=1 only for:
  - upstream bugfix
  - upstream feature
  - upstream PR preparation
```

### 转绿方式

- 若这是误改：撤掉 `nanobot/` 变更，重新提交
- 若这是例外场景：本地使用 `ALLOW_NANOBOT_PATCH=1`，并继续满足 CI 对 `ava/UPSTREAM_VERSION` 与 `[allow-nanobot-patch]` 的要求

---

## Demo 2: schema 漂移测试报警

### 触发条件

- 上游 `nanobot/config/schema.py` 新增字段
- fork `ava/forks/config/schema.py` 未同步，也未在 `INTENTIONAL_REMOVALS` 中说明

### 执行命令

```bash
pytest -q tests/guardrails/test_schema_drift.py -q
```

### 预期失败输出

```text
FAILED tests/guardrails/test_schema_drift.py::test_no_unacknowledged_upstream_additions
E   AssertionError: assert ['ProvidersConfig.some_new_field'] == []
```

### 转绿方式

- 同步 fork 字段，或
- 在 `tests/guardrails/test_schema_drift.py` 的 `INTENTIONAL_REMOVALS` 中补充明确原因

---

## Demo 3: patch 结构 / Spec 未同步时报错

### 触发条件

- 新增 `ava/patches/*_patch.py`，但没有补 `tests/patches/test_*.py`
- 或新增 patch 后忘记更新 `.specanchor/modules/module-index.md`

### 执行命令

```bash
pytest -q tests/guardrails/test_patch_structure.py tests/guardrails/test_spec_sync.py -q
```

### 预期失败输出

```text
FAILED tests/guardrails/test_patch_structure.py::test_patch_files_have_corresponding_patch_tests
FAILED tests/guardrails/test_spec_sync.py::test_module_index_covers_all_patch_files
```

### 转绿方式

- 为 patch 补专项测试
- 在 `module-index.md` 中登记 patch
- 若 patch 需要模块 Spec，同时补 `.specanchor/modules/*_spec.md`
