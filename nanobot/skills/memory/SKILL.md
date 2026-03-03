---
name: memory
description: Three-scope categorized memory with identity resolution and auto-consolidation.
always: false
---

# Memory

## Architecture

三维度记忆体系：按**对象**分层，按**时间**分文件。

```
memory/
├── MEMORY.md              # Global 长期记忆（跨用户共享事实）
├── HISTORY.md             # Global 时间线日志（append-only）
├── identity_map.yaml      # 身份映射 channel:chat_id → person
├── self/
│   └── MEMORY.md          # Nanobot 自身记忆（身份、能力、约定）
└── persons/
    └── <person>/
        ├── MEMORY.md      # 个人长期记忆
        ├── HISTORY.md     # 个人时间线
        └── sources/       # 渠道级笔记 (<channel>_<id>.md)
```

## Three Scopes

| Scope | 文件路径 | 加载到 context | 用途 |
|-------|---------|---------------|------|
| **global** | `memory/MEMORY.md` | ✅ 始终 | 跨用户共享的稳定事实 |
| **self** | `memory/self/MEMORY.md` | ✅ 始终 | Nanobot 自身记忆 |
| **person** | `memory/persons/<person>/MEMORY.md` | ✅ 身份解析后 | 特定用户的偏好/关系/约定 |

每个 scope 的 `HISTORY.md` 都是 append-only 时间线，**不**加载到 context，通过 `search_history` 检索。

## Identity Resolution

`identity_map.yaml` 将 `channel:chat_id` 映射到自然人：

```yaml
persons:
  leo:
    display_name: "Leo / 主人"
    ids:
      - channel: telegram
        id: ["12345678", "87654321"]
      - channel: cli
        id: ["direct"]
```

同一 person 可挂载多渠道、多账号，记忆自动聚合。

## memory Tool

优先使用 `memory` 工具操作，不要直接编辑 memory 文件。

| action | 说明 |
|--------|------|
| `recall` | 查看当前/指定 person 的记忆 |
| `remember` | 写入稳定事实（需指定 `scope`: global / person / source） |
| `search_history` | 关键词搜索历史，支持 `since`/`until`/`channel` 过滤，无匹配时自动搜 sessions |
| `map_identity` | 建立 channel:chat_id → person 映射 |

## MEMORY.md vs HISTORY.md

**MEMORY.md** — 只写稳定、可复用、影响未来决策的事实：

- 用户偏好（"不喜欢频繁汇报"）
- 身份信息（"位置: 杭州"）
- 长期目标、重要约定

**HISTORY.md** — 时间线事件，每条以 `[YYYY-MM-DD HH:MM]` 开头：

- 对话摘要、关键决策
- 一次性事件记录

## Auto-consolidation

会话增长到阈值时自动触发：

1. LLM 从旧消息中提取 `history_entry` / `memory_update` / `person_memory_update` / `self_memory_update`
2. 规则层过滤：去重、拦截时间戳条目进入 MEMORY.md
3. Person 记忆通过 `CategorizedMemoryStore.on_consolidate()` 同步

无需手动管理，但可通过 `memory` 工具主动写入重要事实。

## Writing Guidelines

写入前问自己：

1. 下周/下个月还会用得上吗？
2. 会影响未来的决策吗？
3. 是稳定事实还是临时状态？

三个都是"是"→ `MEMORY.md`；否则 → `HISTORY.md` 或不记。
