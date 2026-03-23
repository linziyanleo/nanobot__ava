---
specanchor:
  level: task
  task_name: "新增微信 Channel 支持"
  author: "@Ziyan Lin"
  assignee: "@Ziyan Lin"
  reviewer: "@Ziyan Lin"
  created: "2026-03-23"
  status: "draft"
  last_change: "Task Spec 创建"
  related_modules:
    - ".specanchor/modules/nanobot-channels.spec.md"
  related_global:
    - ".specanchor/global/coding-standards.spec.md"
    - ".specanchor/global/architecture.spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "feat/0.0.1"
---

# SDD Spec: 新增微信 Channel 支持

## 0. Open Questions
- [ ] None

## 1. Requirements (Context)
- **Goal**: 为 nanobot 新增微信消息通道，支持 QR 码登录、Long-poll 收消息、发送文本消息
- **In-Scope**:
  - WeixinChannel 类实现（继承 BaseChannel）
  - QR 码登录流程（通过 bus 推送二维码 URL）
  - Long-poll 收消息循环
  - 文本消息发送
  - Token 持久化到 ~/.nanobot/weixin_token.json
  - WeixinConfig 配置类
  - ChannelManager 注册
- **Out-of-Scope**:
  - 非文本消息类型（图片、视频等，仅 log warning 跳过）
  - 微信群消息
  - 修改现有 channel 逻辑
- **Schema**: sdd-riper-one（推荐原因：新增功能模块，标准开发流程）

## 1.1 Context Sources
- Requirement Source: 用户需求描述
- Design Refs: 微信协议 API（ilinkai.weixin.qq.com）
- Chat/Business Refs: N/A
- Extra Context: 参考 telegram.py 实现风格

## 2. Research Findings

### 2.1 BaseChannel 接口分析
- `BaseChannel(ABC)` 接受 `(config, bus)` 参数
- 必须实现：`start()`, `stop()`, `send(msg: OutboundMessage)`
- 内置 `_handle_message(sender_id, chat_id, content, media, metadata, session_key)` 处理入站
- `is_allowed(sender_id)` 基于 `config.allow_from` 做 ACL
- `name` 类属性标识 channel 名称
- `_running` 标志位控制运行状态

### 2.2 Channel 注册模式（manager.py）
- 硬编码 if-else 模式：`if config.channels.<name>.enabled → lazy import → 实例化`
- 大部分 channel 只传 `(config, bus)`，Telegram 和 Feishu 额外传 voice 配置
- 微信 channel 遵循简单模式：`WeixinChannel(config, bus)`

### 2.3 Config 模式（schema.py）
- 所有 Config 继承 `Base`（支持 camelCase/snake_case 双模式）
- 标准字段：`enabled: bool = False`, `allow_from: list[str]`
- 在 `ChannelsConfig` 中注册：`weixin: WeixinConfig = Field(default_factory=WeixinConfig)`

### 2.4 微信 API 协议
- Base URL: `https://ilinkai.weixin.qq.com`
- 登录：`POST /v1/login/qrcode` → 返回二维码 URL，`POST /v1/login/check` → 轮询获取 token
- 收消息：`GET /v1/updates?timeout=30` (Long-poll, Authorization: Bearer {token})
- 发消息：`POST /v1/message/send` (body: {contextToken, content, type: "text"})
- 消息字段：msgId, fromUser, toUser, content, type, contextToken

### 2.5 风险
- 微信 token 有效期不明确，需要 token 刷新/重新登录机制
- Long-poll 可能因网络问题断开，需要重连逻辑

## 2.1 Next Actions
- 编写 Plan，定义文件变更和实现清单

## 3. Innovate (Optional: Options & Decision)
### Skip (for small/simple tasks)
- Skipped: true
- Reason: 架构明确（遵循现有 Channel 模式），无需多方案比较

## 4. Plan (Contract)

### 4.1 File Changes
- `nanobot/channels/weixin.py`（新建）: WeixinChannel 完整实现
- `nanobot/config/schema.py`（修改）: 新增 WeixinConfig 类 + ChannelsConfig 添加 weixin 字段
- `nanobot/channels/manager.py`（修改）: 注册 weixin channel
- `.specanchor/modules/weixin.md`（新建）: weixin 模块设计文档

### 4.2 Signatures
- `class WeixinConfig(Base)`: enabled, token, api_base, allow_from, poll_timeout
- `class WeixinChannel(BaseChannel)`:
  - `name = "weixin"`
  - `__init__(self, config: WeixinConfig, bus: MessageBus)`
  - `async def start(self) -> None` — QR 登录 + Long-poll 循环
  - `async def stop(self) -> None` — 优雅退出
  - `async def send(self, msg: OutboundMessage) -> None` — 发送文本消息
  - `async def _login(self) -> str` — QR 码登录，返回 token
  - `async def _poll_updates(self) -> None` — Long-poll 收消息循环
  - `def _load_token(self) -> str | None` — 从文件加载持久化 token
  - `def _save_token(self, token: str) -> None` — 持久化 token 到文件

### 4.3 Implementation Checklist
- [ ] 1. 在 config/schema.py 添加 WeixinConfig 类
- [ ] 2. 在 ChannelsConfig 添加 weixin 字段
- [ ] 3. 创建 nanobot/channels/weixin.py，实现 WeixinChannel
- [ ] 4. 实现 token 持久化（load/save）
- [ ] 5. 实现 QR 登录流程（_login）
- [ ] 6. 实现 Long-poll 收消息循环（_poll_updates）
- [ ] 7. 实现 send() 发送文本消息
- [ ] 8. 在 manager.py 注册 weixin channel
- [ ] 9. 创建 .specanchor/modules/weixin.md 设计文档

## 5. Execute Log
（待填充 — EXECUTE 阶段）

## 6. Review Verdict
（待填充 — REVIEW 阶段）

## 7. Plan-Execution Diff
（待填充）
