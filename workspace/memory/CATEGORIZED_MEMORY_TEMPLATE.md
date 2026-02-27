# Categorized Memory 模板

本文件说明分类记忆的目录结构和文件格式，供 agent 和用户参考。

> 模型的“最短可执行规约”请以 `workspace/TOOLS.md` → `Categorized Memory` 为准；本文件保留更完整的结构说明（人类参考）。

## 目录结构

```
workspace/memory/
├── MEMORY.md                     # 全局共享记忆 (所有用户通用)
├── HISTORY.md                    # 全局共享历史 (grep 可搜索)
├── ava/
│   └── MEMORY.md                 # Ava 自身长期记忆（人格/成长/长期约定）
├── identity_map.yaml             # 身份映射配置
├── CATEGORIZED_MEMORY_TEMPLATE.md # 本模板文件
└── persons/                      # 按自然人分类存储
    ├── <person_name>/
    │   ├── MEMORY.md             # Person 级长期记忆 (跨渠道聚合)
    │   ├── HISTORY.md            # Person 级历史记录
    │   └── sources/              # 按来源渠道细分
    │       ├── telegram_<id>.md  # Telegram 渠道的记忆笔记
    │       ├── dingtalk_<id>.md  # DingTalk 渠道的记忆笔记
    │       └── cli_direct.md     # CLI 渠道的记忆笔记
    └── anonymous/                # 未映射身份的记忆暂存
        └── sources/
            ├── telegram_<id>.md
            └── ...
```

## 记忆层次

### 1. 全局记忆 (Global)

- **文件**: `memory/MEMORY.md`, `memory/HISTORY.md`
- **用途**: 所有用户共享的事实（不放用户专属细节）
- **注入时机**: 始终加载到 system prompt

### 2. Ava 自身记忆 (Ava Self)

- **文件**: `memory/ava/MEMORY.md`
- **用途**: Ava 人设成长、长期自我约定、可复用行为偏好
- **注入时机**: 始终加载到 system prompt

### 3. Person 级记忆 (Person)

- **文件**: `memory/persons/<name>/MEMORY.md`
- **用途**: 某个自然人的跨渠道聚合记忆（偏好、身份信息、重要事实）
- **注入时机**: 身份识别成功后自动注入 system prompt
- **写入来源**: consolidation 自动同步 + agent 通过 memory tool 主动写入

### 4. Source 级记忆 (Source)

- **文件**: `memory/persons/<name>/sources/<channel>_<id>.md`
- **用途**: 特定渠道的细粒度笔记（仅在该渠道上下文中有意义的信息）
- **注入时机**: 不自动注入 prompt，agent 通过 memory tool 按需加载
- **写入来源**: agent 通过 memory tool 的 `remember` action (scope=source)

## identity_map.yaml 格式

```yaml
persons:
  <person_key>:                # 唯一标识 (英文小写，用于目录名)
    display_name: "显示名称"    # 自然语言名称
    ids:
      - channel: telegram       # 渠道名
        id: ["12345678"]        # ID 数组，支持同渠道多账号
      - channel: cli
        id: ["direct"]
```

### id 字段说明

- **类型**: 字符串数组 (`list[str]`)，也向后兼容纯字符串
- **含义**: 同一个人可以在同一渠道有多个 ID（如多个 Telegram 账号）
- **匹配规则**: 任意一个 ID 匹配即识别为该 person

## Person MEMORY.md 模板

```markdown
# <Display Name> 的个人记忆

## 基本信息
- 姓名: ...
- 常用渠道: ...

## 偏好
- 技术偏好: ...
- 沟通风格: ...

## 重要事实
- ...

## 项目相关
- ...
```

## memory tool 操作对照

| 操作 | 影响层级 | 文件路径 |
|------|---------|---------|
| `recall` (scope=person) | Person | `persons/<name>/MEMORY.md` |
| `recall` (scope=source) | Source | `persons/<name>/sources/<channel>_<id>.md` |
| `remember` (scope=person) | Person | `persons/<name>/MEMORY.md` |
| `remember` (scope=source) | Source | `persons/<name>/sources/<channel>_<id>.md` |
| `search_history` | Global + Person | `HISTORY.md` + `persons/<name>/HISTORY.md` |
| `map_identity` | Config | `identity_map.yaml` |
| `list_persons` | Config | `identity_map.yaml` (读取) |
| Consolidation (自动) | Global + Person | 全局 + person 级同步 |
