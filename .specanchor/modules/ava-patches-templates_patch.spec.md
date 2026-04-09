---
specanchor:
  level: module
  module_name: "模板覆盖 Patch"
  module_path: "ava/patches/templates_patch.py"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-04-09"
  updated: "2026-04-09"
  last_synced: "2026-04-09"
  last_change: "按 SpecAnchor 最新 Module Spec 模板重生，合并 legacy spec 与当前代码扫描结果"
  status: "active"
  depends_on:
    - "ava/launcher.py"
    - "ava/templates/AGENTS.md"
    - "ava/templates/TOOLS.md"
    - "ava/templates/SOUL.md"
---

# 模板覆盖 Patch (templates_patch)

## 1. 模块职责
- 用 ava/templates/ 覆盖工作区 bootstrap 模板的运行时拷贝。
- 保持上游模板可升级，同时让 sidecar 的 AGENTS.md、SOUL.md、TOOLS.md、记忆模板持续生效。

## 2. 业务规则
- nanobot.utils.helpers.sync_workspace_templates
- 保留原始方法引用并打 patched 标记，重复 apply 不得产生副作用
- 目标拦截点不存在时必须 warning + skip，不能静默失败
- 补丁逻辑优先收敛在入口/出口层，避免把 sidecar 规则深入写进上游中段实现

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `apply_templates_patch()` | `apply_templates_patch() -> str` | 公共函数 |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| _AVA_TPL_DIR | module | 模块级共享状态或常量 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- 严格遵循 patch-governance：能 patch 不 fork，能 fork 不改上游
- 返回值使用人类可读描述，方便 launcher 汇总 patch 应用结果
- 对应验证优先落在 tests/patches 或 guardrail 测试，保持可回归

## 5. 已知约束 & 技术债
- [ ] 需随着代码继续演进同步更新本 Spec，避免再次出现 legacy 术语漂移。

## 6. TODO
- [ ] 代码行为变化后同步更新接口表、关键文件表和 module-index @ZiyanLin
- [ ] 如上游新增同类能力，重新评估 keep / narrow / delete / upstream 的 patch 策略 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/patches/templates_patch.py`
- **核心链路**: `templates_patch.py` → 上游拦截点 → sidecar 补丁逻辑 → 原始运行时输出
- **数据流**: 触发 patch 注册 → 校验目标存在 → 包装/替换目标方法 → 返回 launcher/调用方可见结果
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/patches/templates_patch.py` | 模块主入口 |
| `ava/templates/AGENTS.md` | 关联链路文件 |
| `ava/templates/TOOLS.md` | 关联链路文件 |
| `ava/templates/SOUL.md` | 关联链路文件 |
- **外部依赖**: `ava/launcher.py`、`ava/templates/AGENTS.md`、`ava/templates/TOOLS.md`、`ava/templates/SOUL.md`

## 8. 迁移说明
- 本文件由 legacy spec `ava-patches-templates_patch.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
