# Chat（聊天会话）

**路由**: `/chat`
**页面标题**: 聊天 / 会话名称
**权限**: 非 viewer（admin / editor / mock_tester）

## 可操作元素

| 元素 | 类型 | 作用 |
|------|------|------|
| 渠道标签（Telegram / Console / CLI / Cron / Heartbeat / Other） | Tab 切换 | 按渠道筛选会话列表 |
| New Chat 按钮 | 按钮 | 创建新聊天会话 |
| 会话列表项 | 可点击列表 | 点击切换显示对应会话消息记录 |
| Refresh 按钮 | 按钮 | 刷新当前会话消息 |
| Search 按钮 | 按钮 | 搜索消息内容 |
| 消息气泡 Copy 按钮 | 按钮 | 复制消息文本 |
| Token badge | 标签/链接 | 显示该消息 token 消耗，点击跳转 Token 统计页 |

## 会话列表显示信息

- 会话名称（截断）
- 消息数量
- 相对时间
- Token 消耗（M）
- 工具调用次数
- 状态标签（活跃 / legacy）

## 检查项

| check_id | 检查内容 | 断言方式 |
|-----------|---------|---------|
| `chat.route` | URL 为 `/chat` | `page.url` |
| `chat.heading` | 标题"聊天"可见 | `page_state.headings` |
| `chat.channel_tabs` | 渠道标签可见（至少有 Telegram / Console） | `page_state.buttons` |
| `chat.new_chat_btn` | New Chat 按钮存在 | `page_state.buttons` |
| `chat.session_list` | 会话列表可见（或空状态提示） | `page_state` 文本 |
| `chat.no_error` | 无错误提示 | `page_state.alerts` 为空 |

## instruction 示例

"检查渠道标签（Telegram / Console 等）是否可见，左侧是否有会话列表，New Chat 按钮是否存在"
