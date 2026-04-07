---
name: console-ui-regression
description: Console-ui 专属回归 verifier 资产。提供页面注册表、文件到页面映射、baseline smoke 规则和源码推断线索。优先由 console_ui_dev_loop 间接使用；只有用户明确要求“只做 console-ui smoke / regression，不进入开发闭环”时才直接触发。
metadata: {"nanobot":{"emoji":"🧪"}}
---

# Console-UI Regression

这是 `console_ui_dev_loop` 的 repo-specific verifier 资产，不是主开发闭环。

- 它负责：页面注册、文件到页面映射、回归范围建议
- 它不负责：coding orchestration、默认自动修复、后台任务等待协议

## 使用原则

- 若任务是“修复 console-ui 并持续回归直到通过”，优先用 `console_ui_dev_loop`
- 若任务只是“对 console-ui 指定页面做一次 smoke / regression”，可直接用本 skill

## 页面注册表

| key | path | source |
|-----|------|--------|
| `login` | `/login` | `console-ui/src/pages/LoginPage.tsx` |
| `dashboard` | `/` | `console-ui/src/pages/DashboardPage.tsx` |
| `config` | `/config` | `console-ui/src/pages/ConfigPage/index.tsx` |
| `tasks` | `/tasks` | `console-ui/src/pages/ScheduledTasksPage.tsx` |
| `bg-tasks` | `/bg-tasks` | `console-ui/src/pages/BgTasksPage.tsx` |
| `memory` | `/memory` | `console-ui/src/pages/MemoryPage.tsx` |
| `skills` | `/skills` | `console-ui/src/pages/SkillsPage.tsx` |
| `chat` | `/chat` | `console-ui/src/pages/ChatPage/index.tsx` |
| `tokens` | `/tokens` | `console-ui/src/pages/TokenStatsPage.tsx` |
| `users` | `/users` | `console-ui/src/pages/UsersPage.tsx` |

## 文件 -> 页面映射

| 文件路径模式 | 页面范围 |
|-------------|----------|
| `pages/DashboardPage*` | `dashboard` |
| `pages/ConfigPage*` | `config` |
| `pages/ScheduledTasksPage*` | `tasks` |
| `pages/BgTasksPage*` | `bg-tasks` |
| `pages/MemoryPage*` | `memory` |
| `pages/SkillsPage*` | `skills` |
| `pages/ChatPage*` | `chat` |
| `pages/TokenStatsPage*` | `tokens` |
| `pages/UsersPage*` | `users` |
| `components/layout/*` | 当前页面 + `dashboard` |
| `api/*` | `baseline_smoke`，必要时升级到更大范围 |
| `stores/*` | `baseline_smoke`，必要时升级到更大范围 |

## 回归协议

1. 选范围
   - `explicit_pages`
   - `changed_files` 映射
   - `baseline_smoke`

2. 对每个页面生成验证线索
   - 从源码提取标题、关键按钮、空状态、错误提示
   - 形成 checkpoint 或 verify hint

3. 执行验证
   - 先 `page_agent(..., response_format="json")`
   - 再按需升级 `screenshot + vision`

## 特殊规则

- `users` 是权限敏感页面；若当前登录角色不满足，应显式 `skip` 或 `escalate`
- 不要把本 skill 的一次性 smoke 结果误当成完整 acceptance gate
- 关键发布前仍建议配合人工确认
