---
specanchor:
  level: module
  module_name: "Telegram 批处理 Patch"
  module_path: "ava/patches/channel_patch.py"
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
    - "ava/channels/batcher.py"
    - "ava/launcher.py"
---

# Telegram 批处理 Patch (channel_patch)

## 1. 模块职责
- 为 Telegram 提供两项上游未覆盖的能力：
- **消息批处理**：1 秒窗口内合并同一 chat_id 的多条回复，减少消息闪烁
- **send_delta 修复**：补丁两个上游未处理的边界情况

## 2. 业务规则
- 所有发往 Telegram 的消息先入 MessageBatcher（按 chat_id 分组，1.0s 超时）
- Flush 时构造 OutboundMessage 调用 original_send
- Batcher 延迟初始化（首次发送时创建）
- _channel_instance["ref"] 闭包字典保存实例引用供 callback 使用

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `apply_channel_patch()` | `apply_channel_patch() -> str` | Patch TelegramChannel to add message batching and send_delta fixes. |
| `MessageBatcher` | `class` | Groups messages by key (e.g. chat_id) and flushes after a configurable |
| `_Buffer` | `class` | 核心类 |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| sender_id | instance | _Buffer 运行时字段 |
| chat_id | instance | _Buffer 运行时字段 |
| session_key | instance | _Buffer 运行时字段 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.channels.telegram.TelegramChannel
- nanobot.bus.events.OutboundMessage
- nanobot.utils.helpers.strip_think
- ava.channels.batcher.MessageBatcher

## 5. 已知约束 & 技术债
- [ ] `_stream_end` 时 `buf.message_id is None` 仍是高风险边界，必须 fallback 发送新消息以避免文本丢失。
- [ ] 批处理窗口和 fallback 发送语义变更后，要同步验证 typing 停止、message_id 为空和 chat_id 隔离三条链路。

## 6. TODO
- [ ] 代码行为变化后同步更新接口表、关键文件表和 module-index @ZiyanLin
- [ ] 如上游新增同类能力，重新评估 keep / narrow / delete / upstream 的 patch 策略 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/patches/channel_patch.py`
- **核心链路**: `channel_patch.py` → 上游拦截点 → sidecar 补丁逻辑 → 原始运行时输出
- **数据流**: 触发 patch 注册 → 校验目标存在 → 包装/替换目标方法 → 返回 launcher/调用方可见结果
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/patches/channel_patch.py` | 模块主入口 |
| `ava/channels/batcher.py` | 关联链路文件 |
- **外部依赖**: `ava/channels/batcher.py`、`ava/launcher.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-patches-channel_patch.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
