---
specanchor:
  level: module
  module_name: "Schema Fork Patch"
  module_path: "ava/patches/a_schema_patch.py"
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
    - "ava/forks/config/schema.py"
---

# Schema Fork Patch (schema_patch)

## 1. 模块职责
- AgentDefaults：新增 vision_model、mini_model、image_gen_model、memory_tier、memory_window、context_compression、in_loop_truncation、history_summarizer
- ConsoleConfig：Console 启用/端口/密钥配置
- ClaudeCodeConfig：Claude Code 子代理配置
- PageAgentConfig：page-agent 工具的 LLM / 浏览器 / 截图配置

## 2. 业务规则
- **原始行为**：nanobot.config.schema 定义基础的 Pydantic 配置模型（AgentDefaults、GatewayConfig 等）
- **修改后行为**：整个模块仍由 ava/forks/config/schema.py 提供，但 fork 内部通过 _ava_upstream_schema 继承上游共享类，只对 sidecar 私有字段做最小 override
- **Patch 方式**：importlib.util.spec_from_file_location 加载 fork 模块 → 先把 fork 临时注册到 sys.modules["nanobot.config.schema"]，确保 Pydantic 前向引用绑定当前 fork → 注入 _ava_upstream_schema 与 _ava_fork = True 标记 → 更新包属性与 loader Config 引用

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `apply_schema_patch()` | `apply_schema_patch() -> str` | Replace ``nanobot.config.schema`` with the inherited ava fork. |
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
| _UPSTREAM | module | 模块级共享状态或常量 |
| _SIDECAR_PROVIDER_NAMES | module | 模块级共享状态或常量 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.config.schema — 替换目标
- nanobot.config 包 — 属性更新目标
- ava/forks/config/schema.py — Fork 源文件（必须存在）
- ava.launcher.register_patch — 自注册机制

## 5. 已知约束 & 技术债
- [ ] 若已标记为 True，直接跳过，返回 "schema already patched (skipped)"
- [ ] Fork 文件不存在时优雅降级，返回描述性消息
- [ ] Fork 文件缺失时必须继续保证系统可启动，不能把 sidecar schema 问题扩大成全局启动失败。

## 6. TODO
- [ ] 代码行为变化后同步更新接口表、关键文件表和 module-index @ZiyanLin
- [ ] 如上游新增同类能力，重新评估 keep / narrow / delete / upstream 的 patch 策略 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/patches/a_schema_patch.py`
- **核心链路**: `a_schema_patch.py` → 上游拦截点 → sidecar 补丁逻辑 → 原始运行时输出
- **数据流**: 触发 patch 注册 → 校验目标存在 → 包装/替换目标方法 → 返回 launcher/调用方可见结果
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/patches/a_schema_patch.py` | 模块主入口 |
| `ava/forks/config/schema.py` | 关联链路文件 |
- **外部依赖**: `ava/launcher.py`、`ava/forks/config/schema.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-patches-a_schema_patch.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
