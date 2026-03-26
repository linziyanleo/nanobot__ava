# Module Spec: b_config_patch — Config Schema 字段注入（降级方案）

> 文件：`ava/patches/b_config_patch.py`
> 状态：✅ 已实现（Phase 2）
> 执行顺序：**第 2 个**（文件名 `b_` 前缀确保在 `a_schema_patch` 之后）

---

## 1. 模块职责

作为 `a_schema_patch` 的降级备选方案：当 fork schema 文件不可用时，通过 Pydantic v2 动态字段注入为 `AgentDefaults` 添加 ava 所需的扩展字段。

### 注入字段
| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `claude_code_model` | str | `"claude-sonnet-4-20250514"` | ClaudeCode 工具使用的模型 |
| `claude_code_config` | dict \| None | `None` | ClaudeCode 额外配置（api_key、base_url） |
| `vision_model` | str \| None | `None` | 视觉识别模型 |
| `mini_model` | str \| None | `None` | 轻量级快速任务模型 |

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `nanobot.config.schema.AgentDefaults` | 属性注入 | 通过 Pydantic `model_fields` 和 `__annotations__` 动态添加字段 |

### 拦截详情

- **前置检查**：若 `sys.modules["nanobot.config.schema"]._ava_fork` 为 True，说明 fork 已加载，本 patch 跳过
- **原始行为**：`AgentDefaults` 仅包含上游定义的字段
- **修改后行为**：动态添加 4 个字段，调用 `model_rebuild(force=True)` 重建 Pydantic 模型

---

## 3. 关键实现细节

### Pydantic v2 动态字段注入
```python
from pydantic.fields import FieldInfo
AgentDefaults.model_fields[field_name] = FieldInfo(default=default_val)
AgentDefaults.__annotations__[field_name] = type(default_val)
AgentDefaults.model_rebuild(force=True)
```

### 幂等性
- 每个字段注入前检查 `hasattr(AgentDefaults, field_name)`
- 已存在则跳过

### model_rebuild 失败
- `model_rebuild` 失败时仅 warning，不阻塞（字段可能仍然通过 `__dict__` 访问可用）

---

## 4. 依赖关系

### 上游依赖
- `nanobot.config.schema.AgentDefaults` — 注入目标

### Sidecar 内部依赖
- `ava.launcher.register_patch` — 自注册机制
- `a_schema_patch` — 互斥关系（fork 存在时本 patch 跳过）

---

## 5. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 字段注入 | 4 个字段正确添加到 AgentDefaults |
| Fork 存在时跳过 | `_ava_fork=True` 时返回 "skipped" |
| 字段已存在时幂等 | 重复调用不报错 |
| model_rebuild 失败 | 仅 warning，不中断 |
| 默认值正确 | 注入字段的默认值与预期一致 |
