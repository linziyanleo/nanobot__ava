---
specanchor:
  level: module
  module_name: "消息通道"
  module_path: "nanobot/channels"
  version: "1.0.0"
  owner: "@Ziyan Lin"
  author: "@Ziyan Lin"
  reviewers: []
  created: "2026-03-23"
  updated: "2026-03-23"
  last_synced: "2026-03-23"
  last_change: "初始创建"
  status: active
  depends_on:
    - "nanobot/bus"
    - "nanobot/config"
---

# 消息通道 (Channels)

## 1. 模块职责
- 提供统一的 BaseChannel 抽象接口（start/stop/send）
- 管理多种聊天平台的消息收发（Telegram, Discord, Slack, Feishu, DingTalk, QQ, Matrix, WhatsApp, Email, Mochat）
- 通过 ChannelManager 统一注册、启停、路由出站消息

## 2. 业务规则
- 每个 Channel 通过 config.enabled 控制是否启用
- allow_from 列表控制访问权限，空列表拒绝所有，"*" 允许所有
- 消息通过 bus 发布/订阅，Channel 不直接调用 Agent

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|-----------|------|------|
| `BaseChannel` | `ABC(config, bus)` | 抽象基类：start/stop/send |
| `ChannelManager` | `(config, bus)` | 管理所有 channel 的启停和消息路由 |

### 3.2 BaseChannel 接口
| 方法 | 签名 | 说明 |
|------|------|------|
| `start()` | `async -> None` | 启动并监听消息 |
| `stop()` | `async -> None` | 停止并清理资源 |
| `send(msg)` | `async (OutboundMessage) -> None` | 发送出站消息 |
| `_handle_message()` | `async (sender_id, chat_id, content, ...) -> None` | 处理入站消息 |

## 4. 模块内约定
- 新增 Channel 需：1) 创建 channel .py 文件 2) 在 config/schema.py 添加 Config 3) 在 manager.py 注册
- Channel 类 name 属性必须唯一
- 使用 httpx.AsyncClient 做 HTTP 请求，loguru 做日志

## 5. 已知约束 & 技术债
- [ ] manager.py 中 channel 注册是硬编码 if-else，非插件化

## 7. 代码结构
- **入口**: `nanobot/channels/__init__.py`
- **核心链路**: `用户消息 → Channel.start() → _handle_message() → bus → Agent → Channel.send()`
- **关键文件**:
  | 文件 | 职责 |
  |------|------|
  | `base.py` | BaseChannel 抽象接口 |
  | `manager.py` | ChannelManager 注册、启停、路由 |
  | `telegram.py` | Telegram Bot 实现 |
  | `batcher.py` | 消息批处理工具 |
- **外部依赖**: `httpx`, `loguru`, `nanobot.bus`, `nanobot.config`
