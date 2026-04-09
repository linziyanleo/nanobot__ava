---
specanchor:
  level: module
  module_name: "技能加载 Patch"
  module_path: "ava/patches/skills_patch.py"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-04-01"
  updated: "2026-04-09"
  last_synced: "2026-04-09"
  last_change: "同步 post-merge 技能治理：删除无行为差异 shadow skills，仅保留 sidecar 增量 skill 覆盖"
  status: "active"
  depends_on:
    - "ava/launcher.py"
    - "ava/skills/README.md"
---

# 技能加载 Patch (skills_patch)

## 1. 模块职责
- 扩展 `SkillsLoader` 的技能发现与加载逻辑，同时支持工作区技能、sidecar 自带技能和 `~/.agents/skills/` 外部安装技能。
- 维持 sidecar 优先于上游默认技能目录的覆盖关系。
- 在列举技能时统一过滤 SQLite 中被禁用的技能项。

## 2. 业务规则
- ava/skills/ 优先级高于 nanobot/skills/
- 同行为 shadow skill 删除后，loader 应自动回退到 nanobot/skills/；当前 sidecar 只保留有增量的 `cron` / `tmux` / `memory` 及 repo 专用 skills
- .agents/skills/ 可为真实目录或 symlink
- SQLite 中 enabled = 0 的技能不会出现在 list_skills() 结果中
- 读取数据库失败时不阻塞主流程，按“无禁用项”降级

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `apply_skills_patch()` | `apply_skills_patch() -> str` | 公共函数 |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| _AVA_SKILLS_DIR | module | 模块级共享状态或常量 |
| _PROJECT_ROOT | module | 模块级共享状态或常量 |
| _AGENTS_SKILLS_DIR | module | 模块级共享状态或常量 |
| _NANOBOT_SKILLS_DIR | module | 模块级共享状态或常量 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.agent.skills.SkillsLoader
- ava.storage.get_db() — disabled skills 数据来源
- ava/skills/ — Sidecar 技能目录

## 5. 已知约束 & 技术债
- [ ] `SkillsLoader.list_skills` 需要同时追加 `.agents/` 与上游 fallback，并过滤 disabled skills。
- [ ] 缺少 SkillsLoader.__init__/list_skills/load_skill 任一拦截点时，patch 必须 skip
- [ ] 二次 apply 必须返回 `skipped`，不能重复包裹加载逻辑。

## 6. TODO
- [ ] 代码行为变化后同步更新接口表、关键文件表和 module-index @ZiyanLin
- [ ] 如上游新增同类能力，重新评估 keep / narrow / delete / upstream 的 patch 策略 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/patches/skills_patch.py`
- **核心链路**: `skills_patch.py` → 上游拦截点 → sidecar 补丁逻辑 → 原始运行时输出
- **数据流**: 触发 patch 注册 → 校验目标存在 → 包装/替换目标方法 → 返回 launcher/调用方可见结果
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/patches/skills_patch.py` | 模块主入口 |
| `ava/skills/README.md` | 关联链路文件 |
- **外部依赖**: `ava/launcher.py`、`ava/skills/README.md`

## 8. 迁移说明
- 本文件由 legacy spec `ava-patches-skills_patch.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
