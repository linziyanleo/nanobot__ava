# Module Spec: skills_patch — SkillsLoader 三源发现与禁用过滤

> 文件：`ava/patches/skills_patch.py`
> 状态：✅ 已实现
> 执行顺序：字母序第 8 位（`skills_patch.py`）

---

## 1. 模块职责

扩展 `SkillsLoader` 的技能发现与加载逻辑，使其同时支持：

1. `workspace/skills/` 原始工作区技能
2. `ava/skills/` Sidecar 自带技能
3. `~/.agents/skills/` 外部安装技能
4. `nanobot/skills/` 上游内置技能兜底

并通过 SQLite `skill_config` 表过滤被禁用的技能，避免其进入 agent 上下文。

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `SkillsLoader.__init__` | 方法替换 | 将 builtin skills 重定向到 `ava/skills/`，并保存原始 `nanobot/skills/` 目录 |
| `SkillsLoader.list_skills` | 方法替换 | 追加 `.agents/` 与上游 fallback，并过滤 disabled skills |
| `SkillsLoader.load_skill` | 方法替换 | 按 `workspace -> ava -> .agents -> nanobot` 顺序加载技能 |

---

## 3. 关键行为

- `ava/skills/` 优先级高于 `nanobot/skills/`
- `.agents/skills/` 可为真实目录或 symlink
- SQLite 中 `enabled = 0` 的技能不会出现在 `list_skills()` 结果中
- 读取数据库失败时不阻塞主流程，按“无禁用项”降级
- 缺少 `SkillsLoader.__init__/list_skills/load_skill` 任一拦截点时，patch 必须 skip

---

## 4. 依赖关系

### 上游依赖
- `nanobot.agent.skills.SkillsLoader`

### Sidecar 内部依赖
- `ava.storage.get_db()` — disabled skills 数据来源
- `ava/skills/` — Sidecar 技能目录

---

## 5. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 应用成功 | `apply_skills_patch()` 可执行且返回 patched 结果 |
| 幂等性 | 二次 apply 返回 skipped |
| 拦截点替换 | `__init__` / `list_skills` / `load_skill` 被替换 |
| 拦截点缺失 | 缺失任一方法时优雅跳过 |
| disabled 过滤 | 被禁用技能不会出现在结果中 |
