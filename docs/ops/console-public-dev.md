# Console Public Dev Baseline

本文档定义 `ava console` 通过 Cloudflare Tunnel/Access 做开发态公网暴露时的最小应用层安全基线。

## 1. 目标

- 允许开发态远程访问 Console。
- 不把真实 `localhost:6688` 直接裸露到公网。
- 保留一个本地 `mock_tester` 账号用于样式验证和自动化测试。
- 确保 `mock_tester` 只能读写 mock 数据，不会碰真实数据。

## 2. 必须满足的条件

当 `gateway.console.publicDev=true` 时，启动前必须同时满足：

- `gateway.console.host=127.0.0.1`
- `gateway.console.secretKey` 不是默认值，且长度至少 32
- `gateway.console.tokenExpireMinutes <= 60`
- `gateway.console.sessionCookieSecure=true`
- `gateway.console.cloudflareAccessTeamDomain` 已配置
- `gateway.console.cloudflareAccessAudience` 已配置

未满足任一条件时，Console 启动直接失败。

## 3. 本地账号与存储

- 真实账号 hash：
  - `~/.nanobot/console/users.json`
- 本地管理员明文密码：
  - `~/.nanobot/console/local-secrets/nanobot_password`
- mock 测试账号明文密码：
  - `~/.nanobot/console/local-secrets/mock_tester_password`
- mock 可写运行时目录：
  - `~/.nanobot/console/mock_data/`
- repo 中的 mock bundle 源：
  - `ava/console/mock_bundle/`

说明：

- repo 不保存上述两个账号的明文密码。
- repo 不维护二进制 `mock.nanobot.db` 真源，而是维护：
  - `ava/console/mock_bundle/mock_seed.json`
  - `ava/console/mock_bundle/MOCK_DATA_CONTRACT.md`
- 运行时自动生成：
  - `~/.nanobot/console/mock_data/mock.nanobot.db`

## 4. mock_tester 权限边界

`mock_tester` 登录后：

- 允许：
  - 配置页读取和编辑 mock config
  - Memory 页读取和编辑 mock workspace 文件
  - Media 页读取和删除 mock media 记录
  - Token Stats 页读取 mock token 数据
  - Scheduled Tasks 页编辑 mock cron/config
- 禁止：
  - 真实 workspace / 真实 `~/.nanobot`
  - live chat
  - gateway restart / rebuild
  - bg tasks
  - page-agent
  - 用户管理

UI 会显示 `MOCK SANDBOX` 标识，防止误把 mock 数据当成真数据。

## 5. Cloudflared 示例

```yaml
tunnel: <your-tunnel-id>
credentials-file: /path/to/<your-tunnel-id>.json

ingress:
  - hostname: console-dev.example.com
    service: http://127.0.0.1:6688
  - service: http_status:404
```

Cloudflare Access 侧至少需要：

- 只允许你的身份源账号访问
- 开启 MFA
- 缩短 session 生命周期
- 应用 audience 与本地 `cloudflareAccessAudience` 对齐

## 6. 建议配置片段

```json
{
  "gateway": {
    "console": {
      "enabled": true,
      "host": "127.0.0.1",
      "port": 6688,
      "secretKey": "replace-with-a-strong-random-secret",
      "tokenExpireMinutes": 60,
      "publicDev": true,
      "sessionCookieName": "ava_console_session",
      "sessionCookieSecure": true,
      "sessionCookieSameSite": "lax",
      "cloudflareAccessTeamDomain": "example.cloudflareaccess.com",
      "cloudflareAccessAudience": "your-access-audience"
    }
  }
}
```
