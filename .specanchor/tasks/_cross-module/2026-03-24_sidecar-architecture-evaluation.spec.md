---
specanchor:
  level: task
  task_name: "Sidecar 架构评估与分支策略重构"
  author: "@fanghu"
  assignee: "@fanghu"
  reviewer: ""
  created: "2026-03-24"
  status: "draft"
  last_change: "Execute 完成——配置隔离全部实现"
  related_modules:
    - ".specanchor/modules/nanobot.spec.md"
    - ".specanchor/modules/console-ui.spec.md"
    - ".specanchor/modules/nanobot-channels.spec.md"
  related_global:
    - ".specanchor/global/architecture.spec.md"
    - ".specanchor/global/coding-standards.spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "REVIEW"
  branch: "feat/0.0.1"
---

# SDD Spec: Sidecar 架构评估与分支策略重构

## 0. Open Questions

- [ ] upstream (HKUDS/nanobot) 的更新频率和 breaking change 密度如何？是否值得频繁同步？
- [ ] 是否存在 upstream 即将合入的重大重构（如 provider 层重写、session 架构变更）？
- [ ] 当前项目的 console-ui 和 console 后端是否可能反哺 upstream？
- [ ] `config.json` 中的 API Key 等敏感信息是否需要从版本控制中分离？

## 1. Requirements (Context)

- **Goal**: 评估 Sidecar 架构 + MonkeyPatch 方案在当前项目的适用性，确定最优的上游同步策略和配置管理方案
- **In-Scope**:
  - 评估 Sidecar（独立 patch 目录）vs Fork（当前模式）vs 混合方案
  - 分支策略设计：是否需要一条干净跟踪 upstream 的分支
  - 配置分层：`config.json` + `extra_config.json` 拆分方案
- **Out-of-Scope**:
  - 实际迁移执行（本 Spec 仅做研究和规划）
  - upstream 功能的反向贡献

- **Schema**: sdd-riper-one（推荐原因：架构级决策需要严格的研究→方案对比→计划审批流程）

## 1.1 Context Sources

- Requirement Source: 用户需求 + `2026-03-24-15-48-文档-Sidecar架构与MonkeyPatch实践说明.md`
- Design Refs: Sidecar 架构文档（`cafeext/` 模式）
- Chat/Business Refs: 当前 `feat/0.0.1` 分支 vs `upstream/main` 差异分析
- Extra Context: `sync-upstream.sh` 现有同步脚本

## 1.5 Codemap Used (Feature/Project Index)

- Codemap Mode: `project`
- Codemap File: `.specanchor/project-codemap.md`
- Key Index:
  - Entry Points: `nanobot/__main__.py` → CLI, `nanobot/console/app.py` → Web Console
  - Core Logic: `nanobot/agent/loop.py`, `nanobot/agent/subagent.py`, `nanobot/agent/context.py`
  - Cross-Module Flows: Channel → bus → Agent → Session → Storage
  - Dependencies: FastAPI, Typer, Pydantic v2, httpx, litellm
  - Frontend: `console-ui/` (React + Vite, 完全独立模块)

## 2. Research Findings

### 2.1 当前项目现状量化

| 维度 | 数据 |
| --- | --- |
| 分支 | `feat/0.0.1`（主开发分支） |
| vs upstream 总差异 | 233 files, +40,102 / -739 lines |
| nanobot/ 核心改动文件 | ~60 个文件 |
| 全新模块 | `nanobot/console/`（18 文件）, `console-ui/`（整个前端项目） |
| 深度改写文件 | `loop.py` +736, `subagent.py` +1077, `commands.py` +971, `cron/service.py` +350 |
| 新增工具 | `claude_code.py`, `image_gen.py`, `memory_tool.py`, `sticker.py`, `vision.py` |
| 配置扩展 | `schema.py` +174 行（新增 contextCompression, historySummarizer, heartbeat, claudeCode 等） |
| 现有同步机制 | `sync-upstream.sh` 脚本 + `feat/merge-upstream-v0.1.4.post4` 分支 |
| Git remotes | origin (GitHub), gitlab (Alibaba), upstream (HKUDS/nanobot) |

### 2.2 改动分类分析

#### 可分离层（适合 Sidecar 或独立模块）
- `console-ui/` — 完全独立的前端项目，无 nanobot 代码依赖
- `nanobot/console/` — 新增模块，理论上可作为插件存在，但依赖 AgentLoop 内部接口
- 新增工具文件 (`claude_code.py`, `image_gen.py`, `sticker.py`, `vision.py`) — 通过 ToolRegistry 注册，可外置
- `workspace/` — 完全独立，已是外部目录

#### 深度耦合层（不适合 MonkeyPatch）
- `agent/loop.py` — 核心循环重写，+736 行改动涉及 CC 任务集成、进度回调、token 统计、多处内部逻辑
- `agent/subagent.py` — +1077 行，几乎是重写
- `agent/context.py` — +155 行，上下文构建逻辑深度修改
- `agent/memory.py` — +136 行，记忆系统扩展
- `cli/commands.py` — +971 行，大量新 CLI 命令
- `config/schema.py` — +174 行，配置模型大幅扩展

#### 适度修改层（可考虑 Patch 但有风险）
- `channels/telegram.py` — +227 行，功能增强
- `channels/manager.py` — +15 行，小改
- `channels/feishu.py` — +88 行
- `agent/tools/web.py` — +172 行

### 2.3 Sidecar + MonkeyPatch 方案评估

**适用条件 vs 当前情况**：

| 文档描述的适用场景 | 当前项目实际 | 匹配度 |
| --- | --- | --- |
| "轻量级拦截" — 安全确认、提示词替换 | 核心循环重写 | ❌ 严重不匹配 |
| 上游代码保持 100% 纯净 | 60+ 核心文件被修改 | ❌ 无法回退到纯净 |
| Patch 作用于入口/出口位置 | 改动深入中间业务逻辑 | ❌ 违反最小化拦截准则 |
| `git pull` 无冲突更新 | 当前需要 merge 脚本 | ⚠️ 部分改善 |
| 私有配置隔离 | config.json 含 API Keys | ✅ 有价值 |

**核心风险**：
1. MonkeyPatch 的方法签名依赖——upstream 重构时 `loop.py` 的方法签名变更会导致 patch 静默失效
2. 调试困难——运行时行为与源码不一致
3. 重建成本——将 1000+ 行的 `subagent.py` 改动转为 patch 等于重写一遍
4. 测试覆盖——patch 后的行为需要独立测试体系

### 2.4 配置分层分析

当前 `config.json` (~250 行) 包含：
- **upstream 原有**: `agents.defaults` (部分), `channels` (部分), `providers`, `gateway`
- **自定义扩展**: `contextCompression`, `historySummarizer`, `heartbeat`, `token_stats`, `claudeCode`, `tools.restrictToWorkspace/restrictToConfigFile`
- **敏感信息**: 多个 API Key、Token

拆分 `extra_config.json` 的收益：
- ✅ 清晰区分 upstream 兼容配置 vs 私有扩展
- ✅ API Key 分离，降低泄露风险
- ✅ upstream 更新 config schema 时减少冲突
- ⚠️ 需要修改 `config/loader.py` 支持配置合并
- ⚠️ 需要修改 `config/schema.py` 的 Pydantic 模型

### 2.5 分支策略分析

**当前策略**：`feat/0.0.1` 直接在 fork 上开发，通过 `sync-upstream.sh` 定期合并 upstream

**新策略候选**：

| 策略 | 描述 | 成本 | 收益 |
| --- | --- | --- | --- |
| A: 维持现状 + 优化 | 保持 Fork，改进 merge 脚本 | 低 | 稳定，已验证可行 |
| B: 双分支 | `main` 跟 upstream + `feat/*` 做定制 | 中 | 同步更干净 |
| C: Sidecar 全量迁移 | 新建 `ext/` 目录，核心代码回退到 upstream | 极高 | 理想但不现实 |
| D: 混合方案 | 可分离部分外置 + 核心保持 Fork | 中 | 平衡点 |

## 2.1 Next Actions

- 下一步：进入 Innovate 阶段，对策略 A/B/D 进行详细方案设计和对比
- 排除策略 C（Sidecar 全量迁移），原因：40K+ 行深度改动无法通过 MonkeyPatch 重建

## 3. Innovate (Options & Decision)

### Option A: 维持 Fork + 渐进优化

**描述**：保持当前 `feat/0.0.1` 的 Fork 开发模式，但在以下维度做渐进改进：

1. **配置分层**: 引入 `extra_config.json`，`config/loader.py` 实现 deep merge
2. **工具外置**: 新增工具 (`claude_code.py`, `vision.py` 等) 通过插件目录加载而非内嵌
3. **同步脚本优化**: 增强 `sync-upstream.sh`，自动标记冲突文件 vs 无冲突文件

- Pros:
  - 零迁移成本，在现有基础上渐进改进
  - 已验证可行，`sync-upstream.sh` + merge 分支已有实践
  - 不打断当前开发节奏
- Cons:
  - 每次 upstream 大更新仍有合并冲突风险
  - 核心改动与 upstream 代码混在一起，难以区分"我的"vs"upstream的"

### Option B: 双分支策略

**描述**：

- `main` 分支：纯粹跟踪 upstream，定期 `git pull upstream main`
- `feat/0.0.1`（或 `develop`）分支：从 `main` rebase/merge，承载所有定制
- 优势在于 `main` 始终是干净的 upstream mirror，便于快速评估 upstream 变更

1. **配置分层**: 同 Option A
2. **分支规范**: `main` 禁止直接 commit，仅接受 upstream merge
3. **定期同步**: `main` 更新后，在 `feat/0.0.1` 上 merge main

- Pros:
  - `main` 作为 upstream 基准，方便 diff 对比
  - 明确区分"上游变更"和"自有变更"
  - 便于评估 upstream 新功能是否需要集成
- Cons:
  - 合并冲突本质没有减少，只是推到了 `feat/0.0.1 ← main` 这一步
  - 需要维护两条分支的纪律
  - 当前 `main` 分支可能已有自定义 commit，需要清理

### Option D: 混合方案（推荐）

**描述**：结合 Sidecar 思想 + Fork 实践，在不全盘重构的前提下做最大化分离：

1. **配置分层**（立即可做）:
   - 新增 `extra_config.json` 管理自定义扩展配置
   - `config/loader.py` 实现 base + extra deep merge
   - `.gitignore` 忽略 `extra_config.json`（含敏感信息）

2. **工具插件化**（中期）:
   - 在 `nanobot/agent/tools/` 下新增 `ext/` 子目录
   - `registry.py` 扫描 `ext/` 自动注册，upstream 更新不影响
   - 将 `claude_code.py`, `image_gen.py`, `sticker.py`, `vision.py`, `memory_tool.py` 迁入

3. **独立模块外置**（中期）:
   - `console-ui/` 已经独立，无需变动
   - `nanobot/console/` 保持在 nanobot 目录但用清晰的 `__init__.py` 隔离

4. **分支策略**（即刻开始）:
   - 清理 `main` 为纯 upstream mirror
   - 开发保持在 `feat/0.0.1` 或 `develop`
   - 同步流程：`upstream/main → main → merge into feat/0.0.1`

5. **核心改动保持 Fork**:
   - `loop.py`, `subagent.py`, `context.py`, `commands.py` 等深度改写文件保持直接修改
   - 在 `.specanchor/` 中维护改动清单，便于 merge 时定位冲突

- Pros:
  - 对"可分离"部分采用 Sidecar 思想，降低与 upstream 的摩擦面
  - 对"深度耦合"部分保持实用的 Fork 方式，避免 MonkeyPatch 的脆弱性
  - 配置分层立即可做，投入产出比最高
  - 渐进式执行，不打断当前开发
- Cons:
  - 不是"完美分离"，核心改动仍然与 upstream 混合
  - 工具插件化需要改动 `registry.py` 的加载逻辑
  - 需要团队纪律：新的定制化功能优先放入 `ext/` 或 `extra_config`

### Decision

- **Selected**: Option A 的最小化版本——仅做 config.json 隔离 + 上游 PR 审查流程
- **Why**:
  1. 配置隔离是投入产出比最高的改进，立即可做
  2. 大架构变动（工具插件化、分支策略重组）风险高，暂不执行
  3. 每周上游 PR 审查作为轻量流程，不需要代码变更
  4. 核心原则：**先做最小有效改进，观察效果再决定下一步**

## 4. Plan (Contract)

### 4.1 File Changes

| 文件 | 变更说明 |
| --- | --- |
| `nanobot/config/loader.py` | 新增 `_deep_merge()` 工具函数；修改 `load_config()` 加载 `extra_config.json` 并 deep merge |
| `.gitignore` | 新增 `extra_config.json` 忽略规则 |
| `nanobot/console/services/config_service.py` | 在 `EDITABLE_CONFIGS` 中新增 `extra_config.json` 条目 |

### 4.2 Signatures

```python
# nanobot/config/loader.py

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. override values take precedence."""

def load_config(config_path: Path | None = None) -> Config:
    # 现有逻辑 + 额外加载 extra_config.json 并 deep merge
```

### 4.3 Implementation Checklist

- [ ] 1. 在 `loader.py` 中实现 `_deep_merge(base, override)` 递归合并函数
- [ ] 2. 修改 `load_config()` 在加载 `config.json` 后，查找同目录下的 `extra_config.json`，如果存在则 deep merge
- [ ] 3. 在 `.gitignore` 中添加 `extra_config.json`
- [ ] 4. 在 `config_service.py` 的 `EDITABLE_CONFIGS` 中添加 `extra_config.json`
- [ ] 5. 将当前 `~/.nanobot/config.json` 中的敏感信息（API Keys、Tokens）和自定义扩展提取到 `~/.nanobot/extra_config.json`

### 4.4 设计要点

**加载优先级**: `config.json`（base）← `extra_config.json`（overlay，优先级更高）

**Deep Merge 语义**:
- 字典递归合并：`extra` 中的 key 覆盖 `base` 中的同名 key
- 非字典值直接覆盖
- `extra` 中不存在的 key 保留 `base` 的值

**Save 行为**: `save_config()` 不变，仍写入 `config.json`。`extra_config.json` 由用户手动管理。这意味着 `nb onboard` 会将合并后的完整配置写入 `config.json`——可接受，因为 onboard 操作很少执行。

**Console UI 支持**: `extra_config.json` 在 Console 配置页面可查看和编辑，与 `config.json` 并列显示。

## 5. Execute Log

- [x] Step 1: `nanobot/config/loader.py` — 实现 `_deep_merge()` 递归合并 + 修改 `load_config()` 加载同目录 `extra_config.json` 并 deep merge
- [x] Step 2: `.gitignore` — 添加 `extra_config.json` 忽略规则
- [x] Step 3: `nanobot/console/services/config_service.py` — 在 `EDITABLE_CONFIGS` 添加 `extra_config.json`
- [x] Step 4: `console-ui/src/pages/ConfigPage/index.tsx` — 添加 Tab 切换（主配置 / 扩展配置）
- [x] Step 5: `console-ui/src/pages/ConfigPage/ExtraConfigEditor.tsx` — 新建扩展配置 JSON 编辑器组件（含创建/编辑/保存 + JSON 校验 + 模板提示）
- [x] Step 6: 创建 `config.json.template` 和 `extra_config.json.template` 模板文件（提交到 Git）
- [x] Step 7: 创建 `~/.nanobot/extra_config.json` 初始文件（从 config.json 提取敏感信息）
- [x] 验证: TypeScript 类型检查通过，Python deep merge 单元测试通过，config 加载正确合并

## 6. Review Verdict

- Spec coverage: PASS — 所有 Checklist 项已完成
- Behavior check: PASS — deep merge 逻辑验证通过，前端编译通过
- Regression risk: Low — `load_config` 行为向后兼容（无 extra_config.json 时行为不变）
- Module Spec 需更新: No — 不涉及架构变更
- Follow-ups:
  - 可选：将 `config.json` 中的敏感信息清空，只保留非敏感默认值
  - 可选：给 `extra_config.json` 添加 JSON Schema 验证
  - 可选：在 `nb onboard` 中自动引导用户创建 `extra_config.json`

## 7. Plan-Execution Diff

- Plan 中无 console-ui Tab 切换和 ExtraConfigEditor 组件（用户在 Plan Approved 时追加了前端适配需求）→ 已在 Execute 中补充实现
- Plan 中无模板文件（用户在 Plan Approved 时追加了 template 需求）→ 已补充 `config.json.template` 和 `extra_config.json.template`
