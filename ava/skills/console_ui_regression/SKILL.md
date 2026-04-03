---
name: console-ui-regression
description: Console-UI 自回归 smoke 检查。当需要对 console-ui 进行开发后验证、或排查页面问题时触发。使用 page_agent 操作页面、screenshot + vision 验证视觉效果、claude_code 修复代码，形成"测试→截图→识图→修复→重建→重测"的编排循环。这是一个基于 agent 编排的 best-effort smoke 脚本，不是确定性自动化测试框架。
metadata: {"nanobot":{"emoji":"🧪"}}
---

# Console-UI 自回归 Smoke 检查

对 console-ui 执行端到端 smoke 检查，并在失败时尝试自动修复、重建、重测。

**定位说明**：这是一个纯 skill 编排方案，利用现有工具链（page_agent + vision + claude_code）组成 best-effort smoke 检查。它不提供确定性 Playwright 断言，不保证 100% 可靠的 pass/fail 判定。如果项目后续实现了 `console_ui_autotest` 工具（带 Playwright 断言层），应优先使用该工具替代本 skill 的测试执行部分。

## 工具链

本 skill 不引入任何新工具，完全基于现有能力编排：

| 步骤 | 工具 | 用途 |
|------|------|------|
| 页面操作 | `page_agent` (execute) | 自然语言导航、点击、填表 |
| 截图 | `page_agent` (screenshot) | 每步截图存 MediaService |
| 视觉验证 | `vision` | 读截图，判断 UI 是否符合预期 |
| 页面信息 | `page_agent` (get_page_info) | 获取当前 URL 和标题（纯文本） |
| 代码修复 | `claude_code` (sync) | 调用 Claude Code 修改前端代码 |
| 前端重建 | `exec` | 在 console-ui 目录下重新构建 |
| Gateway 重启 | `restart_gateway` skill | 重载后端（有条件使用） |

### 工具返回值说明

page_agent 所有动作返回的都是**纯文本字符串**，不是结构化对象：

- `execute` 返回格式：`[PageAgent] session=<id>\nURL: <url>\nTitle: <title>\n\n<执行结果描述>`
- `screenshot` 返回格式：`[PageAgent Screenshot]\nPath: <文件路径>\nMedia record: <record_id>`
- `get_page_info` 返回格式：`URL: <url>\nTitle: <title>\nViewport: <viewport>`

验证时需要从这些文本中读取信息，例如从 get_page_info 的返回文本中查看 URL 行是否包含预期路径。不要假设能用 `===` 或字段访问的方式取值。

## 前置条件

执行前确认以下条件，不满足则中止并告知用户：

1. **Gateway 已运行**：用 exec 检查 nanobot gateway 进程是否存活
2. **Console 可访问**：用 page_agent 打开 `http://127.0.0.1:6688/login`，确认页面可达
3. 如果 console 不可访问，提示用户先启动：`python -m ava`

## 执行流程

### 阶段 0：环境准备

1. 检查 gateway 进程是否存活
2. 用 page_agent 打开 `http://127.0.0.1:6688/login`，确认页面可达
3. 记录返回文本中的 session_id，后续所有操作复用同一会话

### 阶段 1：Smoke 测试

按以下顺序逐步执行。每一步都是三个动作：**操作 → 截图 → 验证**。

#### 步骤 1: 登录

登录是确定性操作，不应依赖 PageAgent 的语义理解来降低模型抖动风险。使用 page_agent 时给出精确的 DOM 操作指令，而不是模糊的自然语言：

```
操作: page_agent(action="execute", url="http://127.0.0.1:6688/login",
        instruction="在用户名输入框中清空并输入 admin，在密码输入框中清空并输入 admin，然后点击 Sign In 按钮",
        session_id="<sid>")

截图: page_agent(action="screenshot", session_id="<sid>")
  → 从返回文本的 "Path: " 行提取截图文件路径

路由检查: page_agent(action="get_page_info", session_id="<sid>")
  → 从返回文本的 "URL: " 行检查是否不再包含 /login

视觉验证: vision(url="<上面提取的截图路径>", prompt="这是一个后台管理系统的页面截图。请判断：
  1. 页面是否已离开登录页（不再显示登录表单和 Sign In 按钮）
  2. 是否显示了控制台/仪表盘内容
  3. 是否有类似'欢迎回来'的字样
  请明确回答每项是否满足。")
```

判定标准：URL 不含 /login 且 vision 确认已离开登录页 → PASS。

#### 步骤 2: Dashboard（首页）

```
操作: 登录成功后应自动跳转到首页，无需额外导航

路由检查: get_page_info → "URL: " 行应包含端口后直接是 "/" 或为空路径

截图 + 视觉验证: vision prompt:
  "这是一个后台管理系统的首页截图。请判断：
  1. 是否显示了欢迎语（如'欢迎回来'）
  2. 是否有 Gateway 状态区域（显示运行状态、PID、端口等信息）
  3. 是否有快捷操作卡片
  4. 整体布局是否正常，没有明显错位、空白或报错
  请明确回答每项是否满足。"
```

#### 步骤 3: 配置页

```
操作: page_agent(action="execute", session_id="<sid>",
        instruction="点击左侧导航栏中的'配置'菜单项")

路由检查: get_page_info → "URL: " 行应包含 /config

截图 + 视觉验证: vision prompt:
  "这是一个配置页面的截图。请判断：
  1. 页面是否显示了配置编辑器或配置内容
  2. 是否有保存或刷新按钮
  3. 页面是否完整加载，没有空白或报错
  请明确回答每项是否满足。"
```

#### 步骤 4: 定时任务页

```
操作: page_agent(action="execute", session_id="<sid>",
        instruction="点击左侧导航栏中的'定时任务'菜单项")

路由检查: get_page_info → "URL: " 行应包含 /tasks

截图 + 视觉验证: vision prompt:
  "这是一个定时任务页面的截图。请判断：
  1. 页面是否显示了任务列表或空状态提示
  2. 页面布局是否正常，没有报错
  请明确回答每项是否满足。"
```

#### 步骤 5: 记忆页

```
操作: page_agent(action="execute", session_id="<sid>",
        instruction="点击左侧导航栏中的'记忆'菜单项")

路由检查: get_page_info → "URL: " 行应包含 /memory

截图 + 视觉验证: vision prompt:
  "这是一个记忆管理页面的截图。请判断：
  1. 页面是否显示了记忆编辑区域或内容
  2. 页面是否正常渲染，没有空白或报错
  请明确回答每项是否满足。"
```

#### 步骤 6: 技能 & 工具页

```
操作: page_agent(action="execute", session_id="<sid>",
        instruction="点击左侧导航栏中的'技能 & 工具'菜单项")

路由检查: get_page_info → "URL: " 行应包含 /skills

截图 + 视觉验证: vision prompt:
  "这是一个技能和工具管理页面的截图。请判断：
  1. 页面是否显示了技能或工具的列表
  2. 列表中是否有可识别的条目
  3. 页面是否正常渲染
  请明确回答每项是否满足。"
```

#### 步骤 7: Token 统计页

```
操作: page_agent(action="execute", session_id="<sid>",
        instruction="点击左侧导航栏中的'Token 统计'菜单项")

路由检查: get_page_info → "URL: " 行应包含 /tokens

截图 + 视觉验证: vision prompt:
  "这是一个 Token 统计页面的截图。请判断：
  1. 页面是否显示了统计相关内容（图表、表格或数字）
  2. 页面是否正常渲染，没有空白或报错
  请明确回答每项是否满足。"
```

#### 步骤 8: 用户管理页

```
操作: page_agent(action="execute", session_id="<sid>",
        instruction="点击左侧导航栏中的'用户'菜单项")

路由检查: get_page_info → "URL: " 行应包含 /users

截图 + 视觉验证: vision prompt:
  "这是一个用户管理页面的截图。请判断：
  1. 页面是否显示了用户列表或管理表格
  2. 表格中是否有至少一行用户数据
  3. 页面是否正常渲染
  请明确回答每项是否满足。"
```

#### 步骤 9: 收尾

```
操作: page_agent(action="execute", session_id="<sid>",
        instruction="点击左侧导航栏中的'控制台'菜单项，回到首页")
截图: page_agent(action="screenshot", session_id="<sid>") → 作为最终截图归档
关闭: page_agent(action="close_session", session_id="<sid>")
```

### 阶段 2：生成测试报告

将所有步骤的结果汇总为结构化报告：

```
## Console-UI Smoke 检查报告

**时间**: <当前时间>
**目标**: http://127.0.0.1:6688
**结果**: <PASS / FAIL>
**类型**: agent 编排 smoke 检查（非确定性断言）

### 步骤结果

| # | 步骤 | 预期路由 | URL 检查 | 视觉验证 | 状态 |
|---|------|----------|----------|----------|------|
| 1 | 登录 | 离开 /login | ... | ... | PASS/FAIL |
| 2 | Dashboard | / | ... | ... | PASS/FAIL |
| ... | ... | ... | ... | ... | ... |

### 失败详情（如有）

- 步骤 X: <具体失败原因>
  - 截图路径: <从 screenshot 返回文本提取的 Path>
  - Media record: <从 screenshot 返回文本提取的 record id>
  - 视觉分析: <vision 返回的判断>

### 截图归档

所有截图已存入 MediaService，可在 Console 的"生成图片"页面查看。
```

### 阶段 3：自动修复循环（仅在有失败时）

如果阶段 1 中有步骤失败，进入修复循环：

```
修复循环（最多 3 轮）:

1. 分析失败原因
   - 用 vision 重新分析失败步骤的截图，获取具体的视觉问题描述
   - 结合路由检查结果和 page_agent execute 返回的执行摘要文本
   - 判断是前端代码问题还是后端/数据问题

2. 修复代码（仅限前端问题）
   - 调用 claude_code(mode="sync", prompt="根据以下测试失败信息修复 console-ui 代码：
     <失败报告，包含 vision 分析结果和路由检查结果>
     注意：只修改 console-ui/ 目录下的文件。不要修改 nanobot/ 或 ava/ 目录。",
     project_path="<项目根目录>")

3. 重建前端
   - exec: 在 console-ui 目录下执行 npm run build
   - 等待构建完成
   - 如果构建失败，记录错误并交给下一轮 claude_code 修复

4. 重启 Gateway（让后端加载新的 dist）
   - 先用 exec 检查 restart_gateway skill 的前置条件：
     检查 at 命令是否可用（exec: which at）
     检查操作系统是否为 macOS 或 Linux
   - 如果前置条件满足：使用 restart_gateway skill
   - 如果前置条件不满足（如 at 不可用）：
     降级方案——直接用 exec 手动重启 gateway：
     先 kill 旧进程，再 nohup 启动新进程
   - 等待 gateway 启动（轮询进程状态，最多等 15 秒）

5. 重新执行阶段 1 的全部步骤

6. 判断是否继续循环
   - 如果全部通过 → 输出成功报告，退出循环
   - 如果同一步骤连续 2 轮失败且问题本质相同 → 停止，报告"无法自动修复"
   - 如果还有失败但有进展（失败步骤减少或变化）→ 继续下一轮
   - 如果达到 3 轮上限 → 停止，输出最终报告
```

## 错误签名判定

"同一错误"的判断标准：

- 同一步骤失败
- 失败路由相同
- vision 分析描述的核心问题相同（如"页面空白"、"元素缺失"等）

不要对描述做精确字符串匹配，而是语义判断：两轮失败是否本质上是同一个问题。

## 自定义测试

除了默认的 smoke 测试，用户可能要求测试特定功能。此时调整流程：

1. 用户描述要测试的功能（如"测试配置页的保存功能"）
2. 用 page_agent 执行用户描述的操作流程
3. 每步仍然遵循"操作 → 截图 → 验证"三段式
4. vision 的验证 prompt 根据用户的预期调整
5. 失败时同样进入修复循环

## 注意事项

- **session_id 复用**：整个测试流程复用同一个 session_id，避免反复启动浏览器。session_id 从第一次 page_agent execute 返回文本的 `session=` 部分提取
- **vision 调用频率**：每个步骤调用一次 vision，不要对同一截图重复分析
- **截图路径传递**：从 page_agent screenshot 返回文本的 `Path: ` 行提取文件路径，传给 vision 的 url 参数
- **修复范围**：自动修复只改 `console-ui/` 下的文件，绝不改 `nanobot/` 或 `ava/`
- **超时处理**：如果 page_agent 某步操作超时，直接标记该步骤为 FAIL，不要无限等待
- **并发限制**：page_agent 最多 5 个并发会话，本 skill 只用 1 个即可
- **非确定性声明**：本 skill 的 pass/fail 判定基于 vision 模型的主观分析，存在误判可能。关键发布前应配合人工确认
