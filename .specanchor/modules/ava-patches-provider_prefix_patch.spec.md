---
specanchor:
  level: module
  module_name: "Provider 前缀兼容 Patch"
  module_path: "ava/patches/provider_prefix_patch.py"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-04-09"
  updated: "2026-04-09"
  last_synced: "2026-04-09"
  last_change: "明确为旧版 yunwu/zenmux 前缀配置的迁移垫片，并登记后续删除方向"
  status: "active"
  depends_on:
    - "ava/launcher.py"
---

# Provider 前缀兼容 Patch (provider_prefix_patch)

## 1. 模块职责
- 为 sidecar 私有 OpenAI-compatible provider 保留旧模型前缀兼容：
- yunwu/...
- zenmux/...
- 不影响已有 upstream provider spec 的正常路由。
- 仅在 provider 缺少 `_spec` 时生效，避免影响已完成 ProviderSpec 迁移的配置。

## 2. 业务规则
- nanobot.providers.openai_compat_provider.OpenAICompatProvider._build_kwargs
- 保留原始方法引用并打 patched 标记，重复 apply 不得产生副作用
- 目标拦截点不存在时必须 warning + skip，不能静默失败
- 补丁逻辑优先收敛在入口/出口层，避免把 sidecar 规则深入写进上游中段实现

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `apply_provider_prefix_patch()` | `apply_provider_prefix_patch() -> str` | 为缺少 registry spec 的 sidecar provider 补齐模型前缀剥离逻辑。 |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| _SIDECAR_MODEL_PREFIXES | module | 模块级共享状态或常量 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- 严格遵循 patch-governance：能 patch 不 fork，能 fork 不改上游
- 返回值使用人类可读描述，方便 launcher 汇总 patch 应用结果
- 对应验证优先落在 tests/patches 或 guardrail 测试，保持可回归

## 5. 已知约束 & 技术债
- [ ] 二次调用 apply_provider_prefix_patch() 必须返回 skipped。
- [ ] 该 patch 是迁移垫片，不应演化为长期 provider 规范；旧配置迁完后应直接删除。

## 6. TODO
- [ ] 代码行为变化后同步更新接口表、关键文件表和 module-index @ZiyanLin
- [ ] 如上游新增同类能力，重新评估 keep / narrow / delete / upstream 的 patch 策略 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/patches/provider_prefix_patch.py`
- **核心链路**: `provider_prefix_patch.py` → 上游拦截点 → sidecar 补丁逻辑 → 原始运行时输出
- **数据流**: 触发 patch 注册 → 校验目标存在 → 包装/替换目标方法 → 返回 launcher/调用方可见结果
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/patches/provider_prefix_patch.py` | 模块主入口 |
- **外部依赖**: `ava/launcher.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-patches-provider_prefix_patch.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
