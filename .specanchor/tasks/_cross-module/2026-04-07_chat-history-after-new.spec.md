---
specanchor:
  level: task
  task_name: "修复 /new 后 ChatPage 历史丢失并引入 conversation 视图"
  author: "@fanghu"
  created: "2026-04-07"
  status: "in_progress"
  last_change: "Execute 完成：session_messages conversation 持久化、active-only load/save、conversation API 与 ChatPage 历史只读视图已落地并通过定向验证"
  related_modules:
    - ".specanchor/modules/ava-patches-storage_patch.spec.md"
    - ".specanchor/modules/ava-patches-loop_patch.spec.md"
    - ".specanchor/modules/ava-patches-console_patch.spec.md"
    - ".specanchor/modules/ava-agent-commands.spec.md"
  related_tasks:
    - ".specanchor/tasks/_cross-module/2026-04-05_token-stats-jump-after-new.spec.md"
    - ".specanchor/tasks/2026-04-03_console-realtime-dataflow-enhancement.md"
  related_global:
    - ".specanchor/global-patch-spec.md"
    - ".specanchor/global/architecture.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "REVIEW"
  branch: "feat/0.1.1"
---

# SDD Spec: 修复 /new 后 ChatPage 历史丢失并引入 conversation 视图

## 0. Open Questions

- [x] `/new` 时是否应该真的新建一条顶层 `sessions` 记录？
  - **结论：不应该。**
  - 原因：`session_key` 当前承载的是渠道会话身份（如 `telegram:8589721068`），也是 observe WebSocket、live session 装载和 console 路由的稳定锚点。`/new` 更像同一 transport session 下切出新的逻辑 conversation，而不是创建新的 transport session。

- [x] Token Status / `token_usage` 能不能作为聊天历史的恢复来源？
  - **结论：不能。**
  - 原因：`token_usage` 记录的是调用统计与部分上下文快照，不是原始消息真相源；它无法无损恢复 `session_messages` 的角色序列、tool calls 和原始消息体。

- [x] 这次是否需要额外建一张 `session_conversations` 表？
  - **结论：第一阶段不需要。**
  - 原因：最小有效方案是给 `session_messages` 增加 `conversation_id`，并继续用 `sessions.metadata.conversation_id` 作为当前 active conversation 指针；conversation 列表的 preview / 计数 / 时间可由聚合查询派生。

- [x] `GET /api/chat/messages` 在加了 `conversation_id` 之后，默认返回“全部历史”还是“当前 active conversation”？
  - **结论：默认必须返回 active conversation。**
  - 原因：否则现有 ChatPage 调用方在不传 `conversation_id` 时会一次拿到所有历史分段，直接破坏当前“正在对话的上下文窗口”语义。

- [x] 本轮是否需要修改 `nanobot/command/builtin.py`？
  - **结论：默认不改。**
  - 原因：按 Sidecar 约束，优先在 `ava/patches/*` 中围绕现有 `/new` 流程做前置轮换与事件广播；只有确认 monkey patch 无法达成时，才重新评估是否触发 upstream bugfix 例外。

## 1. Requirements

### 1.1 Goal

修复 Chat 页面在 Telegram 或其他 IM 场景下执行 `/new` 后历史消息被清空的问题，让 `/new` 只重置**后续对话上下文**，不删除旧消息；同时在 ChatPage 左侧把同一 `session_key` 下的不同逻辑 conversation 作为可切换历史项展示。

### 1.2 In-Scope

- 为 `session_messages` 增加 conversation 分段能力，保证 `/new` 后旧消息继续保留
- 让 `sessions.metadata` 明确记录当前 active conversation，并据此决定 live session 的 load/save 边界
- 新增按 `session_key` 列出 conversation 摘要的后端 API
- 让 ChatPage 在同一 `session_key` 下展示 conversation 子列表，并支持切换查看历史 conversation
- 历史 conversation 视图为只读；active conversation 保持实时 observe / live chat 能力
- 兼容 legacy 历史记录（`conversation_id=''`）的展示与读取
- 增加窄测试，锁死 `/new` 不再清空历史消息这一主合同

### 1.3 Out-of-Scope

- 不把 `/new` 改造成真正的新 `session_key`
- 不以 `token_usage` 替代 `session_messages` 作为聊天历史来源
- 不在第一阶段引入新的 `session_conversations` 汇总表
- 不追求对旧历史做完美 conversation 边界回填
- 不重做 SceneTabs / MessageBubble / ChatInput 的基本交互模型
- 不修改 `nanobot/`，除非后续验证 monkey patch 路径不可行且满足 upstream 例外条件

### 1.4 Success Criteria

- `/new` 后旧 `session_messages` 不再被整段删除
- 同一 `session_key` 下可以存在多个 conversation 分段，并能按时间顺序列出
- `SessionManager._load` 或等效装载路径只把 active conversation 的消息装回内存，不把旧 conversation 混入当前上下文
- `GET /api/chat/messages?session_key=...` 默认只返回 active conversation；指定 `conversation_id` 时可查看历史 conversation
- ChatPage 左侧能看到当前 chat 下的历史 conversation 列表；切历史项时页面进入只读模式
- observe / WebSocket 在 `/new` 后能感知新 conversation 产生，并将前端切到新的 active conversation
- 至少有一条回归测试证明：执行 `/new` 后，旧消息仍可在历史 conversation 中读取

### 1.5 Context Sources

- Requirement Source: 用户要求“`/new` 应该只清空上下文，不应清空显示的聊天记录；希望左侧能看到之前记录并开启新会话”
- Related Existing Work:
  - `.specanchor/tasks/_cross-module/2026-04-05_token-stats-jump-after-new.spec.md`
  - `conversation_id` 已用于 token stats 分段，但尚未闭合到 `session_messages` 历史保留与 ChatPage sessionization
- Likely Touch Points:
  - `ava/storage/database.py`
  - `ava/patches/storage_patch.py`
  - `ava/patches/loop_patch.py`
  - `ava/console/services/chat_service.py`
  - `ava/console/routes/chat_routes.py`
  - `console-ui/src/pages/ChatPage/index.tsx`
  - `console-ui/src/pages/ChatPage/SessionSidebar.tsx`
  - `console-ui/src/pages/ChatPage/MessageArea.tsx`
  - `console-ui/src/pages/ChatPage/types.ts`

## 2. Research Findings

### 2.1 当前计划里判断正确的部分

- 问题根因不只是“前端没分组”，而是 `/new` 之后 `session_messages` 的历史在存储层被清掉
- 需要一个独立于 `session_key` 的 conversation 级锚点，来表达“同一 Telegram chat 下多段逻辑会话”
- 前端不应该继续把一个 `session_key` 直接等同于一个永远单段的聊天窗口

### 2.2 当前计划里容易把实现带偏的部分

1. **“左侧新开一个 session”是 UI 语义，不应直接映射为新的顶层 `sessions` 行**
   - 真正应该新增的是同一 `session_key` 下的 `conversation_id`
   - 左侧可以把它渲染成“像新 session 一样的子项”，但 transport/session 真相源仍然是原 `session_key`

2. **只改 `session_messages` 表还不够，必须同时改 load/save 语义**
   - 如果只给消息表加 `conversation_id`，但 `save()` 仍在 `mem_count < db_count` 时整段删库重写，那么历史仍会被删
   - 如果 `load()` 仍把该 `session_key` 下所有消息都装回内存，那么当前 live conversation 会重新吃到旧历史

3. **`GET /api/chat/messages` 的默认行为不能维持“无 filter 返回全部消息”**
   - conversation 化之后，默认返回全部消息会让 ChatPage 在 active 模式下拿到所有历史分段
   - 正确默认值应是：不传 `conversation_id` 时，按 `sessions.metadata.conversation_id` 返回当前 active conversation

4. **“显示字段”不需要落库成单独列**
   - `first_message_preview`、`message_count`、`created_at`、`updated_at` 都可以由 `session_messages` 聚合得到
   - 第一阶段不必再引入 display-only 列或新 summary 表，避免双写一致性问题

### 2.3 关键闭环缺口

- **存储闭环**：`session_messages.conversation_id` + active conversation pointer + scoped rewrite
- **运行时闭环**：`/new` 前置轮换 active conversation，并广播前端可消费的 conversation 变更事件
- **展示闭环**：conversation list API + messages API active-default contract + ChatPage 二级列表与只读历史态

### 2.4 Next Actions

- 以“同一 `session_key` 下的 conversation 分段”取代“真建新 session”的设计表述
- 将 `storage_patch` 的 save/load contract 明确写成本次第一优先级
- 将 ChatPage API contract 明确为“list conversations + get active/history messages”，避免 UI 改造脱离后端边界

## 3. Innovate

### Option A：`/new` 时直接新建一条顶层 `sessions` 记录

- Pros:
  - 前端列表看起来最直接
  - 不需要 conversation 子列表心智模型
- Cons:
  - 会破坏 `session_key` 当前的 transport 身份语义
  - 需要重新定义 observe WebSocket、live chat 绑定和 session list 去重
  - 同一 Telegram chat 会出现多个“假 session”，运维与调试语义变差

### Option B：保持同一 `session_key`，新增 `conversation_id` 分段，并在 UI 上渲染为该 session 下的历史子项

- Pros:
  - 与当前 `session_key` 语义兼容
  - 能复用已经存在的 `conversation_id` 运行时概念
  - 改动最小，但足以修复历史保留、active 上下文装载和 ChatPage 查看历史三件事
- Cons:
  - 需要同时改 storage / API / UI 三层 contract
  - 需要前端明确 active conversation 与 historical conversation 的只读边界

### Option C：不改 `session_messages`，只拿 `token_usage` 的 `conversation_id` 做历史展示

- Pros:
  - 看起来能少改 DB
- Cons:
  - 无法恢复原始消息内容，不能支持 MessageArea 正常展示
  - 只能看到统计，不是真正的聊天历史

### Decision

- Selected: **Option B**
- Why:
  - 这是首个能同时满足“保留原始聊天记录”“不破坏 live session 语义”“左侧可视化历史 conversation”的最小闭环方案
  - 也是与 2026-04-05 已落地的 token stats `conversation_id` 语义最一致的路径

### Skip

- Skipped: false
- Reason: 这是跨 storage / runtime / console-ui 的多模块任务，且数据丢失是实质性问题，不适合跳过方案比较

## 4. Plan (Contract)

### 4.1 Data Contract

- `session_messages` 新增：
  - `conversation_id TEXT NOT NULL DEFAULT ''`
- 新增索引：
  - `idx_session_messages_conv_seq(session_id, conversation_id, seq)`
- `sessions.metadata.conversation_id`
  - 继续作为当前 active conversation 指针
  - `/new` 时轮换为新的 id
- `conversation` 列表响应字段：
  - `conversation_id`
  - `first_message_preview`
  - `message_count`
  - `created_at`
  - `updated_at`
  - `is_active`
  - `is_legacy`（可选，仅响应层 synthetic 标记，不额外落库）

### 4.2 File Changes

- `ava/storage/database.py`
  - 为 `session_messages` 增加 `conversation_id` migration
  - 增加 `(session_id, conversation_id, seq)` 索引

- `ava/patches/storage_patch.py`
  - 写入消息时带上当前 active `conversation_id`
  - 当内存消息变短或被 `/new` 清空时，只清理当前 active conversation 的行，不删除其他 conversation 历史
  - 从 SQLite 重建 Session 时，只装载 active conversation 的消息列表
  - legacy 兼容：active pointer 缺失且旧消息只有空 `conversation_id` 时，将空字符串视作 legacy active conversation

- `ava/patches/loop_patch.py`
  - 在 `/new` 触发时前置轮换 `session.metadata.conversation_id`
  - 广播 `conversation_rotated` observe 事件，供 ChatPage 刷新 conversation 列表并自动切到新 active conversation
  - 保持不修改 `nanobot/command/builtin.py` 作为默认实施路径

- `ava/console/services/chat_service.py`
  - 新增 `list_conversations(session_key)` 聚合查询
  - `get_messages(session_key, conversation_id=None)` 改为：
    - 未传 `conversation_id`：返回 active conversation 消息
    - 传入 `conversation_id`：返回指定 conversation 的消息

- `ava/console/routes/chat_routes.py`
  - 新增 `GET /api/chat/conversations?session_key=...`
  - 扩展 `GET /api/chat/messages` 的 `conversation_id` 参数
  - 保持现有 session list API 稳定，不把顶层 session list 改成“每个 conversation 一项”

- `console-ui/src/pages/ChatPage/types.ts`
  - 新增 `ConversationMeta`
  - 为 `SessionMeta` 增加 active `conversation_id`

- `console-ui/src/pages/ChatPage/index.tsx`
  - 新增 `activeConversation` 状态
  - 加载 session 后按需拉取 conversation 列表
  - observe 收到 `conversation_rotated` 后刷新并切到新 active conversation

- `console-ui/src/pages/ChatPage/SessionSidebar.tsx`
  - 保持第一层 scene/session_key 结构
  - 在 session_key 下新增 conversation 子列表，而不是制造假的顶层 session

- `console-ui/src/pages/ChatPage/MessageArea.tsx`
  - 当前 active conversation 保持实时能力
  - 历史 conversation 显示“历史记录 / 只读”状态，并隐藏输入框

- `tests/patches/test_storage_patch.py`
  - 增加 `/new` 后保留旧 `session_messages` 的回归测试
  - 增加 active conversation load-only 测试

- `tests/patches/test_loop_patch.py`
  - 增加 `/new` 轮换 active conversation 并广播事件的测试

- `tests/console/test_chat_service.py`
  - 新增 conversation list 与 active-default messages contract 测试

### 4.3 Signatures

- `ChatService.list_conversations(session_key: str) -> list[dict[str, Any]]`
- `ChatService.get_messages(session_key: str, conversation_id: str | None = None) -> list[dict[str, Any]]`
- `ConversationMeta = { conversation_id, first_message_preview, message_count, created_at, updated_at, is_active, is_legacy? }`

### 4.4 Implementation Checklist

- [x] 1. 为 `session_messages` 增加 `conversation_id` 字段与索引
- [x] 2. 调整 `storage_patch`：save 只重写当前 active conversation，保留旧 conversation 历史
- [x] 3. 调整 `storage_patch`：load 只装载 active conversation，避免旧历史重新进入 live 上下文
- [x] 4. 在 `loop_patch` 中为 `/new` 前置轮换 active conversation，并广播 `conversation_rotated`
- [x] 5. 新增 `GET /api/chat/conversations`，并将 `GET /api/chat/messages` 改为 active-default contract
- [x] 6. ChatPage 左侧加入 conversation 子列表，点击历史 conversation 时切只读模式
- [x] 7. 兼容 legacy `conversation_id=''` 的历史记录展示
- [x] 8. 增加 storage / loop / chat service 的窄测试

## 5. Execute Log

- [x] 2026-04-07：收到 `Plan Approved`，进入 Execute；按 `database/storage_patch -> chat_service/routes -> ChatPage -> tests` 顺序落地。
- [x] 2026-04-07：`ava/storage/database.py` 为 `session_messages` 补 `conversation_id` 列与 `(session_id, conversation_id, seq)` 索引，并兼容 legacy SQLite 升级。
- [x] 2026-04-07：`ava/patches/storage_patch.py` 改为 conversation-scoped save/load，`/new` 后旧 conversation 历史不再因整 session rewrite 被删。
- [x] 2026-04-07：`ava/console/services/chat_service.py` / `ava/console/routes/chat_routes.py` 新增 conversation 列表接口，并将消息接口改成 active-default contract。
- [x] 2026-04-07：ChatPage 新增同一 `session_key` 下的 conversation 子列表、历史 conversation 只读态，以及 `conversation_rotated` 事件响应。
- [x] 2026-04-07：定向验证通过：`pytest tests/patches/test_storage_patch.py tests/patches/test_loop_patch.py tests/console/test_chat_service.py -q` => `28 passed`；前端类型检查通过：`bun x tsc -b`（当前环境无 `npm`，因此未用 `npm exec -- tsc -b`）。

## 6. Review Verdict

- Spec coverage: PASS
- Behavior check: PASS
- Regression risk: Medium-Low
- Follow-ups:
  - 若后续要让 ChatPage 一进入某 scene 就预展开所有 session 的 conversation 列表，可再做纯前端体验迭代；本轮先保持“只加载当前选中 session 的 conversation 列表”以收窄改动。
  - `ava-patches-storage_patch.spec.md` 后续应同步这次的 active-only load/save 合同，避免模块文档继续停留在“整 session 增量 append”表述。

## 7. Plan-Execution Diff

- 计划里原本将前端验证写成 `npm` 路径；实际执行时当前环境没有 `npm`，改用同仓库已可用的 `bun x tsc -b` 完成 TypeScript 校验。
- 计划里没有单独强调“空 active conversation 也要在 conversation 列表中可见”；实际实现中在 `chat_service.list_conversations()` 增加了 synthetic active conversation 条目，以覆盖 `/new` 后尚未产生新消息的空会话态。
