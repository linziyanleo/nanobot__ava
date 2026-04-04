---
name: console-ui-regression
description: Console-UI 回归测试。当需要验证 console-ui 的页面改动时触发。默认只测用户指定的页面/功能，显式要求"全量回归"时才跑完整页面清单。验证标准从页面源码动态推断，无需手动维护。
metadata: {"nanobot":{"emoji":"🧪"}}
---

# Console-UI 回归测试

对 console-ui 的页面执行 smoke 回归检查。

**与 page-agent-test 的关系**：本 skill 是 console-ui 专属的 `page-agent-test` 协议封装。对非 console-ui 项目，直接用 `page-agent-test`。

## 执行策略

| 用户指令 | 行为 |
|----------|------|
| "测一下后台任务页" | 只测 `/bg-tasks` |
| "验证配置页和用户页" | 只测 `/config` + `/users` |
| "跑全量回归" / "全量 smoke" | 测所有注册页面 |
| "测一下改动" (给了文件路径) | 按文件→页面映射自动选择 |

### 文件→页面映射

| 文件路径模式 | 对应页面 key |
|-------------|-------------|
| `pages/DashboardPage*` | dashboard |
| `pages/ConfigPage*` | config |
| `pages/ScheduledTasksPage*` | tasks |
| `pages/BgTasksPage*` | bg-tasks |
| `pages/MemoryPage*` | memory |
| `pages/SkillsPage*` | skills |
| `pages/TokenStatsPage*` | tokens |
| `pages/UsersPage*` | users |
| `pages/LoginPage*` | login |
| `pages/ChatPage*` | chat |
| `components/layout/*` | dashboard + 当前页面 |
| `api/*`, `stores/*` | 全量回归 |

## 测试配置

```yaml
base_url: http://127.0.0.1:6688
login:
  username: admin
  password: admin
  login_url: /login
project_path: console-ui
build_command: npm run build
max_fix_rounds: 2
```

## 页面注册表

只记录结构性信息。验证标准在运行时从源码动态生成（见"动态验证"段落）。

| key | label | path | nav_instruction | source |
|-----|-------|------|-----------------|--------|
| login | 登录 | /login → / | 输入 admin/admin，点 Sign In | `pages/LoginPage.tsx` |
| dashboard | 控制台 | / | 点击'控制台'菜单 | `pages/DashboardPage.tsx` |
| config | 配置 | /config | 点击'配置'菜单 | `pages/ConfigPage/index.tsx` |
| tasks | 定时任务 | /tasks | 点击'定时任务'菜单 | `pages/ScheduledTasksPage.tsx` |
| bg-tasks | 后台任务 | /bg-tasks | 点击'后台任务'菜单 | `pages/BgTasksPage.tsx` |
| memory | 记忆 | /memory | 点击'记忆'菜单 | `pages/MemoryPage.tsx` |
| skills | 技能 & 工具 | /skills | 点击'技能 & 工具'菜单 | `pages/SkillsPage.tsx` |
| chat | 聊天 | /chat | 点击'聊天'菜单 | `pages/ChatPage/index.tsx` |
| tokens | Token 统计 | /tokens | 点击'Token 统计'菜单 | `pages/TokenStatsPage.tsx` |
| users | 用户 | /users | 点击'用户'菜单 | `pages/UsersPage.tsx` |

## 动态验证

不硬编码 `verify_prompt`。每个页面的验证标准在运行时按以下流程生成：

```
1. 读取页面源码
   read_file(console-ui/src/<source>)

2. 推断验证标准
   从源码中提取：
   - 页面标题 / heading 文本
   - 关键 UI 元素（按钮、表格、卡片、空状态提示）
   - 条件渲染的分支（如"有数据时显示列表，无数据时显示空状态"）

3. 生成 verify_prompt
   "这是 {label} 页面的截图。请判断：
   1. 页面是否正常加载（非空白、非 loading 卡死、无 JS 报错）
   2. 路由是否正确（URL 包含 {path}）
   3. [从源码推断的关键元素] 是否可见
   请明确回答每项。"
```

**基础健康检查**（所有页面共享，即使跳过源码分析也要检查）：

```
- 页面已完成加载（非白屏、非无限 loading）
- 无可见的 JS 错误 / crash 页面
- 路由 URL 正确
- 侧边栏导航正常可见
```

## 测试协议

### 前置条件

1. Gateway 已运行
2. Console 可访问
3. 不满足则中止

### 执行流程

```
1. 登录（除非只测不需登录的页面）

2. 对选中的每个页面：
   a. 读源码 → 生成 verify_prompt（首次执行该页面时）
   b. 导航：page_agent(execute, instruction=<nav_instruction>)
   c. 路由检查：page_agent(get_page_info) → URL 包含预期 path
   d. 截图：page_agent(screenshot) → 提取截图路径
   e. 验证：vision(url=<截图>, prompt=<verify_prompt>)
   f. 判定：URL 正确 + vision 确认 → PASS，否则 FAIL

3. 报告：汇总结果

4. 修复循环（有失败时）：
   claude_code 修复 → exec 重建 → 重测
   最多 max_fix_rounds 轮

5. 收尾：关闭浏览器会话
```

### 报告格式

```markdown
## Console-UI 测试报告

**时间**: <当前时间>
**范围**: <targeted: 后台任务, 配置 / full: 全量>
**结果**: <PASS / FAIL>

| # | 页面 | 路由 | URL | 视觉 | 状态 |
|---|------|------|-----|------|------|

### 失败详情
- 页面 X: <原因>
  - 截图: <路径>
```

## 注意事项

- session_id 复用，page_agent 返回值是纯文本
- 修复范围仅限 `console-ui/` 目录
- 非确定性 pass/fail，关键发布前配合人工确认
- 新增页面时在"页面注册表"中添加一行即可，无需写 verify_prompt
