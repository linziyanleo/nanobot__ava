# Page Selection

## 优先级

页面范围按以下顺序确定：

1. `explicit_pages`
2. `changed_files` -> 页面映射
3. `baseline_smoke`
4. `full_checklist`

默认中间轮次只扩到 `baseline_smoke`，不要直接全量。

## Console-UI 页面注册表

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
| `api/*` | `baseline_smoke`，必要时升级到 `full_checklist` |
| `stores/*` | `baseline_smoke`，必要时升级到 `full_checklist` |

## 特殊规则

- `users` 是权限敏感页面；若当前登录角色不满足要求，应返回 `manual_auth_required` 或显式 `skip`，不要把它当普通前端失败。
- 登录页与主应用页是不同边界；不要因为进入了 `/login` 就误判所有业务页失败。
- 当 `changed_files` 只落在单页内部时，不要无条件扩大到全量回归。
