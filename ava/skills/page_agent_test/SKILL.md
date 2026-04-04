---
name: page-agent-test
description: 通用前端页面回归测试协议。针对指定页面执行"导航→截图→视觉验证→自动修复"循环，适用于任何前端项目。当用户说"测一下这个页面"、"验证前端改动"、"跑个 smoke test"时触发。
metadata: {"nanobot":{"emoji":"🔍"}}
---

# Page Agent Test — 通用前端页面回归测试

针对一个或多个前端页面执行结构化的 smoke 检查，失败时尝试自动修复。

**定位**：这是基于 page_agent + vision 的 best-effort 测试协议，不是确定性自动化测试框架。pass/fail 判定依赖 vision 模型的主观分析。

## 工具链

| 步骤 | 工具 | 用途 |
|------|------|------|
| 页面操作 | `page_agent` (execute) | 导航、点击、填表 |
| 截图 | `page_agent` (screenshot) | 截图存档 |
| 视觉验证 | `vision` | 判断 UI 是否符合预期 |
| 路由检查 | `page_agent` (get_page_info) | 确认 URL 和页面标题 |
| 代码修复 | `claude_code` (standard) | 后台修复代码，可在 /bg-tasks 观测 |
| 重建 | `exec` | 执行构建命令 |

## 输入参数

用户需要提供（或由上层 skill 传入）：

| 参数 | 必需 | 说明 |
|------|------|------|
| `base_url` | 是 | 测试基础 URL，如 `http://127.0.0.1:6688` |
| `pages` | 是 | 要测试的页面列表（见格式） |
| `login` | 否 | 登录信息（username、password、login_url） |
| `project_path` | 否 | 前端项目路径（修复时使用） |
| `build_command` | 否 | 重建命令（如 `npm run build`） |
| `max_fix_rounds` | 否 | 最大修复轮数，默认 2 |

### pages 格式

每个页面条目包含：

```yaml
- path: "/bg-tasks"          # 页面路径
  label: "后台任务"            # 显示名称
  nav_instruction: "点击左侧导航栏中的'后台任务'菜单项"  # 导航指令（可选，默认直接访问 URL）
  verify_prompt: |            # vision 验证提示（必需）
    这是一个后台任务页面的截图。请判断：
    1. 页面是否显示了任务列表或空状态提示
    2. 页面布局是否正常，没有报错
    请明确回答每项是否满足。
```

## 执行协议

### 阶段 0：环境准备

1. 检查目标 `base_url` 是否可达
2. 如果提供了 `login`，执行登录流程
3. 记录 session_id，后续复用

### 阶段 1：逐页测试

对 `pages` 列表中的每个页面，执行以下三段式：

```
1. 导航
   - 如果有 nav_instruction：用 page_agent(execute) 执行导航指令
   - 否则：直接访问 base_url + path

2. 验证
   - page_agent(get_page_info) → 从 "URL: " 行检查路径是否匹配
   - page_agent(screenshot) → 提取截图路径
   - vision(url=<截图路径>, prompt=<verify_prompt>) → 获取判定

3. 判定
   - URL 包含预期路径 且 vision 确认页面正常 → PASS
   - 否则 → FAIL，记录失败原因
```

### 阶段 2：测试报告

汇总所有页面结果：

```markdown
## Page Agent Test Report

**时间**: <当前时间>
**目标**: <base_url>
**结果**: <PASS / FAIL>

| # | 页面 | 路径 | URL 检查 | 视觉验证 | 状态 |
|---|------|------|----------|----------|------|
| 1 | ... | ... | ... | ... | PASS/FAIL |

### 失败详情
- 页面 X: <原因>
  - 截图: <路径>
```

### 阶段 3：自动修复（仅在有失败且提供了 project_path 时）

```
修复循环（最多 max_fix_rounds 轮）：

1. 分析失败原因（vision 重新分析 + 路由检查）
2. 调用 claude_code 修复代码
   - 等待后台任务完成（用 /task 检查状态）
3. 执行 build_command 重建
4. 重新测试失败的页面
5. 如果同一页面连续 2 轮失败且问题相同 → 停止
```

## 注意事项

- **session_id 复用**：所有操作共用一个浏览器会话
- **截图路径传递**：从 page_agent screenshot 返回文本的 `Path: ` 行提取
- **超时处理**：page_agent 操作超时直接标记 FAIL
- **修复范围**：只改 project_path 下的文件，不改其他目录
- **非确定性**：pass/fail 基于 vision 模型判断，存在误判可能

## 简单调用示例

用户说"测一下后台任务页"时，自动构建参数：

```
base_url: http://127.0.0.1:6688
login: { username: admin, password: admin, login_url: /login }
pages:
  - path: /bg-tasks
    label: 后台任务
    verify_prompt: "页面是否正常显示，有任务列表或空状态提示？"
project_path: <workspace>/console-ui
build_command: npm run build
```
