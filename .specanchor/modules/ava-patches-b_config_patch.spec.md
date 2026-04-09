---
specanchor:
  level: module
  module_name: "配置字段注入 Patch"
  module_path: "ava/patches/b_config_patch.py"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-03-26"
  updated: "2026-04-09"
  last_synced: "2026-04-09"
  last_change: "按 SpecAnchor 最新 Module Spec 模板重生，合并 legacy spec 与当前代码扫描结果"
  status: "active"
  depends_on:
    - "ava/launcher.py"
    - "ava/patches/a_schema_patch.py"
---

# 配置字段注入 Patch (config_patch)

## 1. 模块职责
- 在未启用 fork schema 的情况下，作为降级路径向 `AgentDefaults` 动态注入 sidecar 需要的附加字段。
- 与 `a_schema_patch` 互斥；fork 存在时当前 patch 只负责明确跳过，不重复改写 schema。
- 保证老配置路径仍可读，但不把长期标准停留在运行时打补丁。

## 2. 业务规则
- **前置检查**：若 sys.modules["nanobot.config.schema"]._ava_fork 为 True，说明 fork 已加载，本 patch 跳过
- **原始行为**：AgentDefaults 仅包含上游定义的字段
- **修改后行为**：动态添加 4 个字段，调用 model_rebuild(force=True) 重建 Pydantic 模型

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `apply_config_patch()` | `apply_config_patch() -> str` | 公共函数 |
| `apply_schema_patch()` | `apply_schema_patch() -> str` | Replace ``nanobot.config.schema`` with the inherited ava fork. |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| 运行时状态 | — | 当前模块以局部变量和调用方注入对象为主 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.config.schema.AgentDefaults — 注入目标
- ava.launcher.register_patch — 自注册机制
- a_schema_patch — 互斥关系（fork 存在时本 patch 跳过）
- 每个字段注入前检查 hasattr(AgentDefaults, field_name)

## 5. 已知约束 & 技术债
- [ ] `_ava_fork=True` 时必须返回 `skipped`，避免和 `a_schema_patch` 产生双重注入。

## 6. TODO
- [ ] 代码行为变化后同步更新接口表、关键文件表和 module-index @ZiyanLin
- [ ] 如上游新增同类能力，重新评估 keep / narrow / delete / upstream 的 patch 策略 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/patches/b_config_patch.py`
- **核心链路**: `b_config_patch.py` → 上游拦截点 → sidecar 补丁逻辑 → 原始运行时输出
- **数据流**: 触发 patch 注册 → 校验目标存在 → 包装/替换目标方法 → 返回 launcher/调用方可见结果
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/patches/b_config_patch.py` | 模块主入口 |
| `ava/patches/a_schema_patch.py` | 关联链路文件 |
- **外部依赖**: `ava/launcher.py`、`ava/patches/a_schema_patch.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-patches-b_config_patch.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
