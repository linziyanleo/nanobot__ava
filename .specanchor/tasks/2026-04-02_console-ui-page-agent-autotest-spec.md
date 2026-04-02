---
specanchor:
  level: task
  task_name: "console-ui 自回归测试闭环（PageAgent + Playwright + 截图/重启汇报）"
  author: "@codex"
  created: "2026-04-02"
  status: "draft"
  last_change: "初版任务 spec 建立，锁定为 PageAgent core + Playwright runner + ava tool"
  related_modules:
    - ".specanchor/modules/tools_patch_spec.md"
    - ".specanchor/modules/console_patch_spec.md"
    - ".specanchor/modules/config_patch_spec.md"
    - ".specanchor/modules/loop_patch_spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "refactor/sidecar"
---

# SDD Spec: console-ui 自回归测试闭环（PageAgent + Playwright + 截图/重启汇报）

## 0. Open Questions

- [x] 默认测试目标采用 `managed_vite`，而不是直接测试 `console-ui/dist`
- [x] PageAgent 只作为页内语义执行器，浏览器生命周期、断言、截图、进程管理仍由外层 runner 控制
- [x] 默认汇报方式为截图；仅当工具自己管理了 Vite 进程时才支持 `restart_frontend`
- [x] 截图归档复用 `MediaService` / `media_records`，不新增独立截图存储系统
- [x] v1 只覆盖登录和关键页面导航冒烟，不覆盖真实聊天发送、配置写入、gateway 重启

## 1. Requirements

- **Goal**: 让 nanobot 能自行对 `console-ui` 执行前端自回归测试，在失败时产出结构化报告与截图，在修复后能重启托管前端并再次回归，在成功或失败后都能截图汇报修复进度。
- **In-Scope**:
  - 新增一个 sidecar 工具，供 agent 直接触发 `console-ui` 冒烟回归
  - 新增一个 Node 侧浏览器 runner，负责 Playwright 浏览器控制与 PageAgent 调用
  - 新增一个最小 smoke suite，覆盖登录与关键页面导航
  - 新增前端托管进程管理能力：启动、状态、重启
  - 新增截图与 JSON 报告落盘，并把截图写入现有 media 记录
  - 新增一个面向 agent 的 skill，固定“测试 → 读报告 → 修复 → 重启/重测 → 汇报”的工作流
- **Out-of-Scope**:
  - 修改 `nanobot/`
  - 把 PageAgent 浏览器扩展或官方 MCP server 作为默认主路径
  - 实现完整 CI 平台、多浏览器矩阵、并行分布式执行
  - 在 v1 自动修改后端配置、数据库或 gateway 行为
  - 在 v1 覆盖 Chat 页真实消息流、Config 页写入保存、Users 页编辑等高副作用流程
- **Success Criteria**:
  - agent 默认工具集中可见 `console_ui_autotest`
  - `run_suite("smoke_ui")` 返回结构化 JSON，包含步骤结果、报告路径、截图路径、media record id
  - `managed_vite` 模式下能在 Windows 环境稳定启动并重启 `console-ui`
  - 回归截图能在 console 的 Media 页面被查询和查看
  - smoke suite 在本地已启动 console backend 的前提下可稳定通过

## 1.1 Context Sources

- 需求来源:
  - 用户要求：让 nanobot 使用 `page-agent` 对 `console-ui` 做自回归测试，并在测试结束后重启前端服务或截图汇报修复进度
- 代码来源:
  - `console-ui/package.json`
  - `console-ui/vite.config.ts`
  - `console-ui/src/App.tsx`
  - `console-ui/src/pages/LoginPage.tsx`
  - `console-ui/src/components/layout/navItems.ts`
  - `ava/patches/tools_patch.py`
  - `ava/console/app.py`
  - `ava/console/services/media_service.py`
  - `ava/console/services/gateway_service.py`
- 规范来源:
  - `AGENTS.md`
  - `.specanchor/global-patch-spec.md`
  - `.specanchor/modules/tools_patch_spec.md`
  - `.specanchor/modules/console_patch_spec.md`

## 2. Research Findings

### 2.1 现有前端与后端形态

- `console-ui` 是独立 Vite React 应用，已有 `dev / build / preview` 脚本。
- `console-ui/vite.config.ts` 已将 `/api` 代理到 `NANOBOT_CONSOLE_PORT`，天然适合“本地托管前端 + 已运行 console backend”的开发回归模式。
- `ava/console/app.py` 会在 `console-ui/dist` 存在时挂载静态资源；这说明“生产构建模式”可行，但不适合作为自修复主回路，因为每轮修复后都要 build。
- `LoginPage.tsx` 已暴露稳定登录表单；默认凭据文案为 `admin / admin`，适合 deterministic login。
- `navItems.ts` 已定义核心导航页，可作为 smoke suite 的最小覆盖面。

### 2.2 现有 sidecar 能力可复用点

- `ava/patches/tools_patch.py` 已是自定义工具的统一注入点，适合新增 `console_ui_autotest`。
- `ava/console/services/media_service.py` 已能记录图片产物并被 console 展示；测试截图应直接复用它。
- `ava/console/services/gateway_service.py` 现有的 `restart()` 是 gateway 专用，且脚本链明显偏 Unix/bash，不适合直接拿来管理前端 dev server。
- `loop_patch.py` 已给工具提供 `token_stats` / `media_service` / `db` 注入能力，新工具应延续这条依赖注入路径。

### 2.3 对 PageAgent 的工程判断

- PageAgent 适合作为“页内语义执行器”，不应独自承担浏览器拉起、断言、失败归档、进程管理和截图归档。
- 仅用 Playwright 虽然更确定性，但会失去“让 nanobot 像人一样理解页面并操作”的价值。
- 最合理路径是：`Playwright` 负责浏览器与断言，`PageAgent` 负责页内自然语言动作，`ava tool` 负责 orchestration。

## 3. Innovate

### Option A: 直接接 PageAgent 扩展 / MCP server

- Pros:
  - 与官方示例表面上更接近
- Cons:
  - 额外依赖浏览器扩展或 MCP server 进程
  - 无法自然承载 Windows 下的前端进程管理、截图归档、结构化报告
  - 与当前仓库的 Python sidecar 能力耦合差

### Option B: 纯 Playwright 硬编码选择器回归

- Pros:
  - 自动化最稳，测试行为最可预测
- Cons:
  - 失去 PageAgent 语义操作价值
  - 不满足“让 nanobot 自己做”的主诉求

### Option C: PageAgent core + Playwright runner + ava tool（选中）

- Pros:
  - 把 PageAgent 放在它最擅长的页内语义层
  - 外围仍保留确定性断言、截图和进程控制
  - 最符合 sidecar 约束和当前仓库结构
- Cons:
  - 需要跨 Python / Node 两侧各加一层薄封装

### Decision

- Selected: `Option C`
- Why:
  - 这是兼顾“能落地”“可测试”“真能被 agent 调用”的最小工程闭环
  - 它把 PageAgent 放在正确位置，而不是误当成完整测试框架

## 4. Plan (Contract)

### 4.1 Architecture Decision

- 默认运行模式为 `managed_vite`：
  - 工具负责在 `console-ui/` 下拉起 `npm run dev -- --host 127.0.0.1 --port <port>`
  - 启动前注入环境变量 `NANOBOT_CONSOLE_PORT=6688`
  - 浏览器访问地址固定为 `http://127.0.0.1:<managed_port>`
- `console_backend` 必须已运行；工具只检查其健康性，不负责启动整个 gateway。
- 登录步骤不用 PageAgent，统一用 Playwright 定位输入框和按钮完成，以降低模型抖动。
- 页面内导航与操作说明使用 PageAgent。
- 每一步执行后都由 Playwright 执行断言；PageAgent 结果不能单独作为“通过”依据。
- 截图文件写入 `~/.nanobot/media/generated/`，再通过 `MediaService.write_record()` 写记录。
- 默认 post action 为 `screenshot`；只有当当前前端进程由工具自己拉起时，才允许 `restart_frontend`。

### 4.2 File Changes

- `ava/forks/config/schema.py`
  - 为 `ToolsConfig` 新增 `console_ui_autotest` 配置模型
- `ava/patches/b_config_patch.py`
  - 为未启用 fork schema 的兜底路径动态注入同名配置字段
- `ava/tools/console_ui_autotest.py`
  - 实现工具主体、状态文件、子进程管理、runner 调用、截图归档、结构化结果
- `ava/tools/__init__.py`
  - 导出 `ConsoleUiAutotestTool`
- `ava/patches/tools_patch.py`
  - 注入 `console_ui_autotest`
- `console-ui/package.json`
  - 新增 `page-agent`、`playwright`
- `console-ui/e2e/page-agent-runner.mjs`
  - 实现浏览器控制、PageAgent 调用、截图与 JSON 报告
- `console-ui/e2e/suites/smoke_ui.yaml`
  - 定义最小冒烟回归场景
- `ava/skills/console_ui_regression/SKILL.md`
  - 定义 agent 的固定自修复工作流
- `tests/tools/test_console_ui_autotest.py`
  - 工具单测
- `tests/patches/test_tools_patch.py`
  - 工具注册补测

### 4.3 Public Interfaces

#### 配置接口

```json
{
  "tools": {
    "consoleUiAutotest": {
      "enabled": true,
      "targetMode": "managed_vite",
      "baseUrl": "http://127.0.0.1:4173",
      "backendConsolePort": 6688,
      "managedPort": 4173,
      "authUsername": "admin",
      "authPasswordEnv": "NANOBOT_CONSOLE_PASSWORD",
      "pageAgentModel": "",
      "pageAgentApiBase": "",
      "pageAgentApiKeyEnv": "PAGE_AGENT_API_KEY",
      "language": "zh-CN",
      "suite": "smoke_ui",
      "postAction": "screenshot",
      "artifactDir": "~/.nanobot/console-ui-autotest",
      "maxRepairLoops": 3
    }
  }
}
```

#### 工具接口

- `console_ui_autotest.run_suite(suite?: str, post_action?: str) -> dict`
- `console_ui_autotest.start_frontend(port?: int) -> dict`
- `console_ui_autotest.restart_frontend() -> dict`
- `console_ui_autotest.status() -> dict`

#### `run_suite()` 返回格式

```json
{
  "success": true,
  "suite": "smoke_ui",
  "target_mode": "managed_vite",
  "target_url": "http://127.0.0.1:4173",
  "run_id": "20260402_120000_abcd",
  "steps": [
    {
      "name": "open_config",
      "success": true,
      "summary": "navigated to config page",
      "assertion": "pathname=/config"
    }
  ],
  "artifacts": {
    "report_json": "C:/Users/.../report.json",
    "screenshots": [
      "C:/Users/.../.nanobot/media/generated/console-ui-20260402-120000-final.png"
    ],
    "media_record_ids": ["console-ui-20260402-120000-final"]
  },
  "post_action": {
    "type": "screenshot",
    "executed": true,
    "message": "final screenshot captured"
  }
}
```

### 4.4 Smoke Suite Definition

`smoke_ui.yaml` 固定包含以下步骤：

1. `login`
   - Playwright 输入用户名/密码并提交
   - 断言跳转到 `/`
2. `dashboard`
   - PageAgent 打开控制台首页并等待稳定
   - 断言页面存在 Dashboard 主容器和状态卡
3. `config`
   - PageAgent 导航到配置页
   - 断言 `pathname === "/config"`
4. `skills`
   - PageAgent 导航到技能页
   - 断言 `pathname === "/skills"`
5. `tokens`
   - PageAgent 导航到 Token 统计页
   - 断言 `pathname === "/tokens"`
6. `users`
   - PageAgent 导航到用户页
   - 断言 `pathname === "/users"` 且主表格存在
7. `final_screenshot`
   - Playwright 截最终图

### 4.5 Self-Repair Workflow Contract

`console_ui_regression` skill 的固定步骤：

1. 先调用 `console_ui_autotest.run_suite()`
2. 若通过：
   - 输出成功摘要
   - 附最后截图路径或 media 记录
3. 若失败：
   - 读取 `report_json`
   - 读取失败截图
   - 使用 `read_file` / `edit_file` / `claude_code` 修复前端代码
   - 调用 `console_ui_autotest.restart_frontend()`
   - 再次运行 `run_suite()`
4. 同一失败签名连续 2 次不变即停止
5. 总修复轮次上限为 `maxRepairLoops=3`

### 4.6 Implementation Checklist

- [ ] 1. 在 `ava/forks/config/schema.py` 增加 `ConsoleUiAutotestConfig`
- [ ] 2. 在 `ava/patches/b_config_patch.py` 增加同名 fallback 字段注入
- [ ] 3. 新增 `ava/tools/console_ui_autotest.py`，实现 `run_suite/start_frontend/restart_frontend/status`
- [ ] 4. 为前端 dev server 建立独立状态文件，路径固定为 `~/.nanobot/console-ui-autotest/frontend-state.json`
- [ ] 5. `start_frontend()` 仅允许托管 `console-ui/` 目录下的 Vite 进程，不做任意命令执行
- [ ] 6. `restart_frontend()` 只重启由工具管理且状态文件可识别的进程
- [ ] 7. 工具对目标 URL 做本地地址限制，只允许 `127.0.0.1` / `localhost`
- [ ] 8. 在 `console-ui/package.json` 增加 `page-agent` 和 `playwright`
- [ ] 9. 编写 `console-ui/e2e/page-agent-runner.mjs`，支持 suite、target URL、artifactDir 参数
- [ ] 10. 登录流程使用 Playwright 实现，不交给 PageAgent
- [ ] 11. 页面操作由 PageAgent 执行，但每一步必须跟随 Playwright 断言
- [ ] 12. 失败时保存失败截图；结束时无论成败都保存最终截图
- [ ] 13. 使用 `MediaService.write_record()` 记录截图，不新增截图专用 DB 表
- [ ] 14. 在 `ava/tools/__init__.py` 和 `ava/patches/tools_patch.py` 注册新工具
- [ ] 15. 新增 `ava/skills/console_ui_regression/SKILL.md`，固化修复回归工作流
- [ ] 16. 补齐 Python 单测与 patch 测试
- [ ] 17. 提供一条最小手动验收命令与环境说明

## 5. Test Coverage

### 5.1 自动化测试

| ID | 类型 | 文件 | 覆盖内容 |
|----|------|------|----------|
| T1 | Unit | `tests/tools/test_console_ui_autotest.py` | 默认配置加载与 camelCase/snake_case 兼容 |
| T2 | Unit | `tests/tools/test_console_ui_autotest.py` | `start_frontend()` 在 Windows 下生成正确命令与环境变量 |
| T3 | Unit | `tests/tools/test_console_ui_autotest.py` | `status()` 能返回托管进程状态与端口信息 |
| T4 | Unit | `tests/tools/test_console_ui_autotest.py` | `restart_frontend()` 在无状态文件或无 PID 时优雅失败 |
| T5 | Unit | `tests/tools/test_console_ui_autotest.py` | `run_suite()` 成功路径能解析 runner JSON 并返回统一结构 |
| T6 | Unit | `tests/tools/test_console_ui_autotest.py` | `run_suite()` 失败路径能保留报告路径、失败截图路径、错误摘要 |
| T7 | Unit | `tests/tools/test_console_ui_autotest.py` | 本地地址限制生效，非 localhost 目标被拒绝 |
| T8 | Unit | `tests/tools/test_console_ui_autotest.py` | `postAction=screenshot` 与 `postAction=restart_frontend` 分支行为正确 |
| T9 | Unit | `tests/tools/test_console_ui_autotest.py` | 截图写入 media record 的字段格式正确 |
| T10 | Patch | `tests/patches/test_tools_patch.py` | `console_ui_autotest` 被正确注入默认工具集合 |
| T11 | Contract | `tests/tools/test_console_ui_autotest.py` | runner 返回缺字段时工具能报错且不中断主进程 |
| T12 | Contract | `tests/tools/test_console_ui_autotest.py` | 同一失败签名重复出现时停止继续修复的判定逻辑 |

### 5.2 手动验收

| ID | 场景 | 验收标准 |
|----|------|----------|
| M1 | 已启动 `python -m ava`，再由工具启动 `managed_vite` | 浏览器可打开登录页，API 通过 Vite proxy 正常工作 |
| M2 | 运行 `console_ui_autotest.run_suite("smoke_ui")` | Dashboard / Config / Skills / Tokens / Users 全部通过 |
| M3 | 人为改坏一个导航 label 或路由 | 回归失败，生成失败截图和 JSON 报告 |
| M4 | 修复前端代码后执行 `restart_frontend()` 再重测 | 工具能重启前端并重新通过 smoke suite |
| M5 | 打开 console 的 Media 页面 | 能看到本次回归产生的截图记录 |

### 5.3 不做自动化覆盖的内容

- 真实 PageAgent 线上模型调用不纳入默认自动化测试，避免把外部 API 稳定性引入仓库测试。
- 这部分改为手动验收前提：
  - 已配置 `PAGE_AGENT_API_KEY`
  - 已配置 `pageAgentModel` / `pageAgentApiBase` 或能从现有 provider 继承
- 自动化测试只验证 orchestration contract，不验证外部模型质量。

## 6. Acceptance Criteria

- 新工具能从 agent 默认工具列表中被发现
- smoke suite 默认在 `managed_vite` 模式下可运行
- 失败后至少产出一个失败截图和一个 JSON 报告
- 成功后至少产出一个最终截图并登记到 Media
- 自修复循环不会无限重试
- 全程不修改 `nanobot/`

## 7. Execute Log

- [ ] 尚未进入 Execute
- [ ] 等待按本 spec 实现

## 8. Review Verdict

- Spec coverage: `PASS`
- Behavior check: `N/A`
- Regression risk: `Medium`
- Main risk:
  - PageAgent 的外部模型行为存在波动，因此必须坚持“PageAgent 负责动作，Playwright 负责断言”的双层结构

## 9. Plan-Execution Diff

- Any deviation from plan: `None`
