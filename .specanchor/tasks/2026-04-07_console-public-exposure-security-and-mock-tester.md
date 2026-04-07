---
specanchor:
  level: task
  task_name: "Console 公网暴露安全基线与 mock_tester 隔离方案"
  author: "@codex"
  created: "2026-04-07"
  status: "draft"
  last_change: "初始化公网暴露开发标准与 mock-only 测试账号任务 spec"
  related_modules:
    - ".specanchor/global-patch-spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "feat/0.1.1"
---
# SDD Spec: Console 公网暴露安全基线与 `mock_tester` 隔离方案

## 0. Open Questions
- [x] 本任务目标不是“让 6688 先能被公网访问”，而是先建立 `public_dev` 可接受安全基线，再允许暴露。
- [x] 不能只依赖 Cloudflare Tunnel；必须同时补应用层鉴权、会话、默认凭据移除、最小权限和 mock 隔离。
- [x] 本地留给 nanobot 自己登录做样式验证的账号，必须是单独角色，不得读取或改写真实数据。
- [x] 测试账号的真实密码不能进 repo；只能本地生成、本地保存，并且仅 owner 可读。
- [x] 本任务全部在 `ava/`、`console-ui/`、`.specanchor/` 内完成，不修改 `nanobot/`。

## 1. Requirements
- **Goal**: 为 `ava console` 建立一套“可经 Cloudflare Access 暴露的开发态应用层安全标准”，并提供一个仅访问 mock 数据的本地测试账号，供 nanobot/自动化回归登录验证 `console-ui` 样式与交互。
- **In-Scope**:
  - 引入 `public_dev` 暴露模式及其启动前安全校验。
  - 移除默认凭据提示、禁止默认弱密钥、禁止自动创建默认管理员。
  - 把当前前端 `localStorage + Bearer + query token` 方案改为更适合公网暴露的安全会话方案。
  - 新增 `mock_tester` 角色，允许浏览与编辑 mock 数据，但不得触达真实 `workspace`、真实 `~/.nanobot`、真实 agent/gateway。
  - 新增本地 bootstrap 流程，安全生成 `mock_tester` 账号及其本地密码文件。
  - 新增 Cloudflare Access 对接与文档示例，但不把真实 Cloudflare 凭据提交进 repo。
  - 为 `console-ui` 显示清晰的 `MOCK` 状态标识，防止误把 mock 数据当真数据。
- **Out-of-Scope**:
  - 直接上线真实公网域名。
  - 修改 `nanobot/`。
  - 引入完整 RBAC 平台或外部 IAM 重构。
  - 把 mock 模式扩展成完整端到端仿真平台；v1 只覆盖 console 当前主要页面和编辑行为。
- **Success Criteria**:
  - `public_dev` 模式下，如果仍使用默认 `secretKey`、默认账号、默认提示文案、非本地回环绑定，启动直接失败。
  - console 前端不再把访问 token 存进 `localStorage`，WebSocket 也不再通过 URL query 传 token。
  - `mock_tester` 登录后只能看到 mock 数据，并且所有写操作只落到 mock 数据根目录。
  - 本地保存的 `mock_tester` 明文密码只存在 `~/.nanobot/console/local-secrets/` 下且权限为 owner-only；repo 内只允许存 hash 或占位符。
  - `console-ui` 自动化测试可以使用 `mock_tester` 完成登录和编辑验证，而不会改动真实数据。

## 1.1 Context Sources
- 代码来源:
  - `ava/console/auth.py`
  - `ava/console/services/user_service.py`
  - `ava/console/services/file_service.py`
  - `ava/console/routes/auth_routes.py`
  - `ava/console/routes/file_routes.py`
  - `ava/console/routes/chat_routes.py`
  - `ava/console/routes/gateway_routes.py`
  - `ava/patches/console_patch.py`
  - `ava/forks/config/schema.py`
  - `console-ui/src/pages/LoginPage.tsx`
  - `console-ui/src/stores/auth.ts`
  - `console-ui/src/api/client.ts`
- 相关现有 spec:
  - `.specanchor/tasks/2026-04-02_console-ui-page-agent-autotest-spec.md`
- 外部依赖约束:
  - Cloudflare Tunnel / Access 只作为入口保护层，不替代应用层会话与权限控制。

## 2. Research Findings

### 2.1 当前实现的高风险点

- `gateway.console.secretKey` 默认值仍为 `change-me-in-production-use-a-longer-key!`。
- console 当前会把 JWT 直接签发给前端，前端再放入 `localStorage`，且 WebSocket 通过 `?token=` 传递。
- console 默认绑定 `0.0.0.0:6688`，不符合“仅供 cloudflared 本地回源”的最小暴露面。
- `UserService.ensure_default_admin()` 会在无用户时自动创建默认管理员。
- 登录页仍展示固定默认凭据提示。
- 文件服务允许访问两类真实根目录: `workspace` 与 `nanobot(~/.nanobot)`。
- chat / gateway / file / config / token stats 目前都默认指向真实后端服务与真实数据。

### 2.2 结论

- 直接把当前 `localhost:6688` 经 Cloudflare 暴露出去，不属于“有风险但可接受”，而是“不满足公网暴露最低应用层标准”。
- 正确方向不是单点补丁，而是增加一个明确的 `public_dev` 模式，并与 `mock_tester` 权限/数据隔离一起设计。

## 3. Innovate

### Option A: 只加 Cloudflare Tunnel/Access，不改应用

- **Reject**
- 原因:
  - 风险仍在应用层: 默认密钥、默认账号、真实数据、弱会话存储。

### Option B: 禁止公网暴露，只保留本地 console

- **Reject**
- 原因:
  - 不能满足“开发态公网访问”诉求。

### Option C: `public_dev` 模式 + 安全会话 + `mock_tester` mock 沙箱

- **Selected**
- 原因:
  - 同时解决公网暴露最小安全基线与 UI 自动化样式验证需求。
  - 能在不改 `nanobot/` 的前提下，通过 `ava/console` 与 `console-ui` 完成。

## 4. Plan (Contract)

### 4.1 核心安全不变量

- `public_dev` 模式下必须满足:
  - console 只监听 `127.0.0.1`，由 `cloudflared` 本地回源。
  - `secretKey` 不能为默认值，长度至少 32 字符。
  - 不允许自动创建默认管理员。
  - 登录页不允许出现默认凭据文案。
  - Access 边界必须开启，且配置完整；否则 console 启动失败。
  - token 过期时间收紧到短时窗口，默认不超过 60 分钟。
  - 所有公网可达写操作都必须经过 app session + role 检查；不能只信任 Cloudflare。

### 4.2 角色与能力模型

| 角色 | 真实数据读取 | 真实数据写入 | Mock 数据读取 | Mock 数据写入 | Chat/Agent | Gateway Restart | 目标用途 |
|---|---|---|---|---|---|---|---|
| `admin` | 是 | 是 | 否 | 否 | 是 | 是 | 本地管理员 |
| `editor` | 是 | 是 | 否 | 否 | 受现有策略控制 | 否 | 本地编辑 |
| `viewer` | 是 | 否 | 否 | 否 | 只读 | 否 | 本地只读 |
| `mock_tester` | 否 | 否 | 是 | 是 | 否，或仅 mock chat | 否 | 样式验证/自动化 |

### 4.3 `mock_tester` 设计约束

- `mock_tester` 登录后，服务层必须切换到 mock sandbox，上下文中显式标记 `mode=mock`。
- mock 根目录固定为 `~/.nanobot/console/mock_data/`，至少包含:
  - `workspace/`
  - `nanobot/`
  - `config.json`
  - `token_stats.json`
  - `sessions/`
  - `media/`
- 所有 mock 编辑都只写入 mock 根目录，绝不回写真实 `workspace` 或真实 `~/.nanobot`。
- UI 必须显示显著 `MOCK` badge，所有危险操作旁需附加 “editing mock data” 提示。
- `mock_tester` 的密码必须随机生成；repo 内不出现明文密码。
- 明文密码只允许保存在 `~/.nanobot/console/local-secrets/mock_tester_password`，权限要求 `0600`。
- 后端只保存 bcrypt hash；自动化工具读取的是本地密码文件，而不是写死凭据。

### 4.4 会话与认证方案

- 保留 JWT 作为服务端签发格式，但前端不再自行持久化 bearer token 到 `localStorage`。
- 改为 `HttpOnly + Secure + SameSite` cookie 承载 session。
- WebSocket 改用 cookie 鉴权或一次性短时 WS ticket，禁止 `?token=` query 传 token。
- `auth/login` 增加登录限流与失败审计。
- `public_dev` 模式下，启动前校验 Cloudflare Access 配置，并要求边缘层已开启 Access。

### 4.5 File Changes

- `ava/forks/config/schema.py`
  - 新增 `ConsoleExposureConfig`、`ConsoleMockSandboxConfig`、`host`、`exposure_mode`、`require_cloudflare_access`
- `ava/patches/console_patch.py`
  - 改为读取 `gateway.console.host`
  - `public_dev` 模式下执行 fail-fast 安全校验
- `ava/console/auth.py`
  - 支持 cookie-based session
  - 支持 `mock_tester` 角色
  - 去掉 URL query token 依赖
- `ava/console/services/user_service.py`
  - 禁止隐式默认管理员
  - 支持 bootstrap 创建本地账号
- `ava/console/services/security_service.py`
  - 新增
  - 承载启动校验、限流、secret 校验、Cloudflare Access 配置校验
- `ava/console/services/request_context.py`
  - 新增
  - 解析 `real/mock` 模式、角色能力、可访问根目录
- `ava/console/services/file_service.py`
  - 支持 mock 根目录映射
- `ava/console/services/`
  - 新增 mock 适配层: `mock_gateway_service.py`、`mock_chat_service.py`、`mock_stats_service.py`、`mock_media_service.py`
- `ava/console/app.py`
  - 根据 user role 注入 real/mock service graph
- `ava/console/routes/*.py`
  - 按 `mock_tester` 能力矩阵收紧真实后端入口
- `ava/console/bootstrap.py`
  - 新增本地账号 bootstrap 入口
- `console-ui/src/pages/LoginPage.tsx`
  - 删除默认凭据提示
- `console-ui/src/stores/auth.ts`
  - 从 token localStorage 迁移到 cookie session
- `console-ui/src/api/client.ts`
  - 改为 `credentials: "include"`，移除 bearer/query token 逻辑
- `console-ui/src/`
  - 新增 mock badge / mock mode UX 标识
- `docs/ops/console-public-dev.md`
  - 新增公网暴露开发标准、cloudflared 示例与本地 bootstrap 流程

### 4.6 Public Interfaces

#### 配置接口

```json
{
  "gateway": {
    "console": {
      "enabled": true,
      "host": "127.0.0.1",
      "port": 6688,
      "secretKey": "<required-non-default>",
      "tokenExpireMinutes": 60,
      "exposureMode": "local",
      "requireCloudflareAccess": false,
      "cloudflareAccess": {
        "teamName": "",
        "audTag": []
      },
      "mockSandbox": {
        "enabled": true,
        "username": "console-ui-smoke",
        "dataRoot": "~/.nanobot/console/mock_data",
        "passwordFile": "~/.nanobot/console/local-secrets/mock_tester_password"
      }
    }
  }
}
```

#### 本地 bootstrap 接口

- `python -m ava.console.bootstrap create-admin --username <name> --password-stdin`
- `python -m ava.console.bootstrap ensure-mock-tester --username console-ui-smoke --password-file ~/.nanobot/console/local-secrets/mock_tester_password`

### 4.7 Implementation Checklist

- [ ] 移除登录页默认凭据提示。
- [ ] `public_dev` 模式下禁用默认 `secretKey`、默认 admin 创建与 `0.0.0.0` 监听。
- [ ] 前端移除 `localStorage` token 持久化与 URL query token。
- [ ] WebSocket 改为 cookie 或一次性票据鉴权。
- [ ] 新增 `mock_tester` 角色与权限矩阵。
- [ ] 所有 mock 读写都走 `~/.nanobot/console/mock_data/`，绝不访问真实根目录。
- [ ] 新增本地 `mock_tester` 密码文件生成逻辑，并设置 owner-only 权限。
- [ ] `console-ui` 自动化测试配置改为读取本地密码文件，不写死凭据。
- [ ] 新增启动前安全校验，未满足公网暴露基线时拒绝启动 `public_dev`。
- [ ] 新增 Cloudflare Access 示例文档，但不提交真实域名、aud、token、密钥。
- [ ] 清理当前测试账号/默认账号文案对外暴露问题。

### 4.8 Test Coverage

- `tests/console/test_security_service.py`
  - `public_dev` 下默认 `secretKey`、`0.0.0.0`、缺失 Access 配置时启动失败
- `tests/console/test_auth_cookie_mode.py`
  - 登录后使用 cookie，会话刷新、登出、过期、限流
- `tests/console/test_mock_tester_policy.py`
  - `mock_tester` 无法访问真实数据、无法触发 restart、无法进入真实 chat
- `tests/console/test_mock_file_overlay.py`
  - mock 写入只改变 `mock_data/`，不影响真实 `workspace` / `~/.nanobot`
- `tests/console/test_bootstrap_local_accounts.py`
  - 本地生成 `mock_tester` 密码文件、权限正确、repo 内无明文泄露
- `tests/ui/test_login_page_security.ts`
  - 登录页不显示默认凭据
- `tests/ui/test_mock_badge.ts`
  - `mock_tester` 登录后页面出现 `MOCK` 标识且编辑对象为 mock 数据
- `tests/security/test_no_console_plaintext_secrets.py`
  - 禁止 repo 内出现测试账号明文密码、Cloudflare 凭据、默认弱密钥

## 5. Execute Log

- [ ] 当前仅生成 task spec，尚未进入实现。
- [ ] 本 spec 默认覆盖并替换“直接把 6688 暴露出去”的开发路径。

## 6. Review Verdict

- Spec coverage: `PASS`
- Security direction: `PASS`
- Mock isolation clarity: `PASS`
- Residual risk:
  - 若继续保留当前 token localStorage 或默认凭据文案，则公网暴露仍应视为 `BLOCKED`

## 7. Plan-Execution Diff

- Any deviation from plan: `None`
- 备注:
  - 本任务先解决真正的问题: 建立可接受的应用层安全标准，而不是先开公网入口。
  - 更准确的问题不是“Cloudflare 有没有风险”，而是“当前 console 是否达到可被公网暴露的应用层安全标准”；本 spec 就是为这个差距而写。
