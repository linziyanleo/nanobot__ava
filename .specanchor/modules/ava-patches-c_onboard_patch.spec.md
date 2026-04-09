---
specanchor:
  level: module
  module_name: "Onboard 兼容 Patch"
  module_path: "ava/patches/c_onboard_patch.py"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-04-02"
  updated: "2026-04-09"
  last_synced: "2026-04-09"
  last_change: "按 SpecAnchor 最新 Module Spec 模板重生，合并 legacy spec 与当前代码扫描结果"
  status: "active"
  depends_on:
    - "ava/launcher.py"
    - "ava/forks/config/schema.py"
---

# Onboard 兼容 Patch (onboard_patch)

## 1. 模块职责
- 目标不是改写整条 onboard 流程，而是修复旧 sidecar config.json 的 refresh 写回语义：
- 保留旧字段和旧 key 形状
- 只补当前 schema 缺失的默认字段
- 不把 extra_config.json 的 overlay 值固化回 config.json

## 2. 业务规则
- **原始行为**：现有配置 + 非 wizard + 选择 refresh 时，执行 `load_config(config_path)` → `save_config(config, config_path)`
- `load_config()` 会先把 `extra_config.json` merge 到 base config，再经当前 schema round-trip，导致旧 sidecar 字段被收缩、overlay 被写回 base config
- **修改后行为**：overwrite 与 wizard 分支保持原样，只重写 refresh 分支
- refresh 分支直接读取原始 `config.json`，执行 `_migrate_config()` 做最小迁移，再用当前 schema 默认结构递归补齐缺失字段而不覆盖原值

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `apply_onboard_patch()` | `apply_onboard_patch() -> str` | 公共函数 |
| `Base` | `class` | 沿用上游 alias / populate 规则的基础模型。 |
| `WhatsAppConfig` | `class` | WhatsApp 渠道配置。 |
| `TelegramConfig` | `class` | Telegram 渠道配置。 |
| `FeishuConfig` | `class` | 飞书渠道配置。 |
| `DingTalkConfig` | `class` | 钉钉渠道配置。 |
| `DiscordConfig` | `class` | Discord 渠道配置。 |
| `EmailConfig` | `class` | Email 渠道配置。 |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| _NO_CHANGE | module | 模块级共享状态或常量 |
| _UPSTREAM | module | 模块级共享状态或常量 |
| _SIDECAR_PROVIDER_NAMES | module | 模块级共享状态或常量 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.cli.commands.onboard
- nanobot.config.loader._migrate_config
- nanobot.config.loader.get_config_path / set_config_path
- a_schema_patch：refresh 兼容层依赖 fork schema 的 Config().model_dump(...) 作为默认结构来源

## 5. 已知约束 & 技术债
- [ ] 只补当前 schema 缺失的默认字段
- [ ] 用当前 schema 默认结构生成“缺失字段清单”
- [ ] 递归补齐缺失字段，但不覆盖原值

## 6. TODO
- [ ] 代码行为变化后同步更新接口表、关键文件表和 module-index @ZiyanLin
- [ ] 如上游新增同类能力，重新评估 keep / narrow / delete / upstream 的 patch 策略 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/patches/c_onboard_patch.py`
- **核心链路**: `c_onboard_patch.py` → 上游拦截点 → sidecar 补丁逻辑 → 原始运行时输出
- **数据流**: 触发 patch 注册 → 校验目标存在 → 包装/替换目标方法 → 返回 launcher/调用方可见结果
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/patches/c_onboard_patch.py` | 模块主入口 |
| `ava/forks/config/schema.py` | 关联链路文件 |
- **外部依赖**: `ava/launcher.py`、`ava/forks/config/schema.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-patches-c_onboard_patch.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
