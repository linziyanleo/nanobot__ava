---
specanchor:
  level: task
  task_name: "console 公网访问安全加固（校验与默认安全配置）"
  author: "@git_user"
  assignee: "@git_user"
  reviewer: "@git_user"
  created: "2026-03-24"
  status: "draft"
  last_change: "Task Spec 创建（仅文档设计）"
  related_modules:
    - ".specanchor/modules/nanobot.spec.md"
    - ".specanchor/modules/console-ui.spec.md"
  related_global:
    - ".specanchor/global/architecture.spec.md"
    - ".specanchor/global/coding-standards.spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "feat/0.0.1"
---

# SDD Spec: console 公网访问安全加固（校验与默认安全配置）

## 0. Open Questions

- [ ] 公网访问的部署形态：是否统一通过反向代理（Nginx/Caddy/Traefik）终止 TLS？
- [ ] 是否需要 IP allowlist（仅特定 IP/VPN 可访问）作为硬门槛？
- [ ] 是否接受 WebSocket 使用 query 参数携带 token（如不接受，需要 cookie/短 token/会话绑定替代方案）？

## 1. Requirements (Context)

- **Goal**: 为 console 在公网访问场景提供“默认安全”的校验与加固方案，避免明显的低门槛风险（配置错误、弱默认、跨域泄露、暴力破解等）。
- **In-Scope**:
  - 明确后端安全校验点（auth、CORS、WS、rate limit、安全头、默认账号策略）
  - 明确前端安全约束（token 存储、URL 泄露、权限显示、错误处理）
  - 输出落地改造清单（代码 + 部署建议），但本任务不直接实现
- **Out-of-Scope**:
  - 完整渗透测试与合规审计
  - WAF/IDS 等高级安全设施部署

## 1.1 Context Sources

- Evidence: `nanobot/console/middleware.py` 当前 CORS 为 `allow_origins=["*"]` 且 `allow_credentials=True`
- Evidence: `nanobot/console/auth.py` WebSocket 通过 query 参数 `token` 获取用户
- Evidence: `nanobot/console/services/user_service.py` 默认会创建 `admin/admin` 账号

## 2. Research Findings

- 风险点 A（高）：`allow_origins=["*"] + allow_credentials=True` 组合在浏览器安全模型下非常危险，容易造成跨站凭据泄露/绕过预期边界。
- 风险点 B（中高）：WebSocket token 在 URL query 中传播，可能被反向代理日志、浏览器历史、监控系统记录。
- 风险点 C（高）：默认 `admin/admin` 在公网部署是高危，需要强制修改或禁用默认账号。
- 风险点 D（中）：缺少登录限流/锁定策略，容易被暴力破解；缺少统一安全响应头（CSP/HSTS/Frame-Options）。

## 2.1 Next Actions

- 将“安全校验”拆成可执行 checklist，并和部署文档绑定。

## 3. Innovate (Optional: Options & Decision)

### Option A（推荐）

- 方案：应用层 + 部署层组合加固：
  - 应用层：限制 CORS、登录限流、默认账号硬性策略、基础安全头
  - 部署层：TLS、反代访问控制、日志脱敏
- Pros：投入小、收益大，适合公网最小安全基线
- Cons：仍需要部署方正确配置反代

### Option B

- 方案：将 console 完全置于内网/VPN，仅通过堡垒机访问
- Pros：安全性最佳
- Cons：使用门槛更高

### Decision

- Selected: Option A
- Why: 兼顾可用性与安全基线，能快速规避“明显高危默认配置”。

## 4. Plan (Contract)

### 4.1 File Changes（规划）

- `nanobot/console/middleware.py`: CORS 改为白名单（配置化），禁止 `* + credentials`。
- `nanobot/console/auth.py`: WS token 方案评估（短 token / cookie / 绑定 session 的一次性 token）。
- `nanobot/console/routes/auth_routes.py`: 登录失败审计已存在，补充登录限流/账号锁定策略。
- `nanobot/console/services/user_service.py`: 默认 admin 策略改为“首次启动必须设置强密码/禁用默认账号”。
- `nanobot/console/app.py`: 安全响应头中间件（CSP/HSTS/X-Frame-Options/Referrer-Policy）。
- `console-ui/src/api/client.ts`: 评估 token 存储策略（localStorage 风险，是否切换 httpOnly cookie）。
- 文档：新增 `SECURITY.md` 或在现有 README/部署文档中增加公网部署 checklist（待定位项目约定位置）。

### 4.2 Signatures（概念级）

- `setup_cors(app, allow_origins: list[str], allow_credentials: bool) -> None`
- `rate_limit_login(username, ip) -> allow/deny`
- `security_headers_middleware(request, response) -> response`

### 4.3 Implementation Checklist（安全校验清单）

- [ ] 1. **CORS**：默认只允许同源；如需跨域，必须显式配置 allowlist；禁止 `* + credentials`。
- [ ] 2. **Auth**：强制更改默认账号；密码策略（最小长度/复杂度）；可选 2FA/OTP（后续）。
- [ ] 3. **WS Token**：避免 token 出现在 URL 日志链路；如保留 query token，至少开启短期 token + 绑定 user/session + 旋转策略。
- [ ] 4. **Rate limit**：对 `/api/auth/login` 增加 IP + username 维度限流/锁定；失败次数写审计。
- [ ] 5. **Security Headers**：CSP（至少 default-src/self）、HSTS（仅 HTTPS）、X-Frame-Options、Referrer-Policy、X-Content-Type-Options。
- [ ] 6. **Audit**：保留登录成功/失败日志；敏感字段不落日志（已存在 mask_config，需扩展覆盖）。
- [ ] 7. **部署基线**：必须 TLS；反代层开启访问日志脱敏；建议加 IP allowlist / BasicAuth 二次防线。

## 5. Execute Log

- [ ] 待执行（本次仅输出文档与计划）

## 6. Review Verdict

- Spec coverage: TBD
- Behavior check: TBD
- Regression risk: TBD
- Module Spec 需更新: Yes（实现后需同步更新 `nanobot.spec.md`/`console-ui.spec.md` 的安全约定）
- Follow-ups: TBD

## 7. Plan-Execution Diff

- 待执行后补充
