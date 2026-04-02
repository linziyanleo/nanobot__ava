---
specanchor:
  level: task
  task_name: "网关生命周期重构与旧 restart_gateway 下线"
  author: "@SDD-RIPER-ONE"
  created: "2026-04-02"
  status: "draft"
  last_change: "初始化 supervisor-first 生命周期重构任务 spec"
  related_modules:
    - ".specanchor/global-patch-spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "refactor/sidecar"
---

# SDD Spec: 网关生命周期重构与旧 `restart_gateway` 下线

## 0. Open Questions

- [x] crash 自动拉起由宿主 supervisor 负责，不再内置 watchdog。
- [x] 支持面以 `systemd` / Docker 为主，不设计 `launchd`。
- [x] 删除 `ava/skills/restart_gateway/`，不做兼容保留。
- [x] 新能力形态为 `ava/tools/gateway_control.py` + 共享生命周期后端，不再是 skill。
- [x] 不再内置 Telegram 重启汇报。
- [x] secret-scanning `#1` 作为结构性清理的一部分处理，不做本次历史重写。

## 1. Requirements (Context)

- **Goal**: 把“挂掉后如何重新拉起”重构为 supervisor-first 方案，并统一手动重启、状态查询、退出语义，彻底下线旧 `restart_gateway`。
- **In-Scope**:
  - 在 `ava/` 内新增共享生命周期后端，负责 runtime 状态、重启请求、退出协调、元数据落盘。
  - 新增 `ava/tools/gateway_control.py`，提供 `status` / `restart` 两个生命周期控制动作。
  - 改造 Console Gateway API 与服务层，统一走共享生命周期后端，不再 shell 到 skill 脚本。
  - 删除 `ava/skills/restart_gateway/` 整个目录及其所有引用。
  - 更新 README / 运维文档，使 supervisor 示例统一使用 Sidecar 入口 `python -m ava gateway`。
  - 增加 secret regression 防线，防止 bot token、私钥等运行时密钥再次进入仓库。
- **Out-of-Scope**:
  - 修改 `nanobot/` 目录。
  - 内置 `launchd` / `at` / watchdog。
  - Telegram 自动重启汇报或任何重启后消息通知链路。
  - 本次执行 git 历史净化、filter-repo、BFG 或其他 rewrite-history 操作。

### 1.1 Context Sources

- Requirement Source:
  - 用户明确要求删除旧 `restart_gateway`，按最优实践重新设计“nanobot 挂掉后如何重新拉起”的机制。
  - 用户明确要求新增 `.specanchor/tasks` 下的实现级 task spec，包含 Checklist 与 test 覆盖。
- Design Refs:
  - `AGENTS.md`
  - `.specanchor/global-patch-spec.md`
  - `ava/launcher.py`
  - `ava/patches/console_patch.py`
  - `ava/patches/tools_patch.py`
- Runtime / Ops Refs:
  - `Dockerfile`
  - `docker-compose.yml`
  - `README.md`
- Code Refs:
  - `ava/console/services/gateway_service.py`
  - `ava/console/models.py`
  - `ava/console/routes/gateway_routes.py`
  - `ava/console/services/config_service.py`
  - `ava/tools/`
  - `ava/skills/restart_gateway/`
- Security Refs:
  - GitHub secret-scanning alert `#1`
  - 历史提交 `25e5493d8c51350332065bed9c76da7241ee546d`

## 2. Research Findings

### 2.1 已确认事实

1. **Sidecar 真实启动入口已经是 `python -m ava`**
   - `Dockerfile` 当前为：
     - `ENTRYPOINT ["python", "-m", "ava"]`
     - `CMD ["gateway"]`
   - 这说明 Sidecar 正确启动路径已存在，生命周期方案必须围绕 `ava` 入口设计，而不是继续围绕 `nanobot gateway`。

2. **Docker 已经具备 supervisor 能力**
   - `docker-compose.yml` 中 `nanobot-gateway` 服务已经配置：
     - `restart: unless-stopped`
   - 这意味着容器场景下的 crash 自动恢复本应由容器平台负责，而不是由 skill 脚本在进程内自建 watchdog。

3. **README 仍有大量旧入口表述**
   - `README.md` 当前仍多处使用 `nanobot gateway`、`ExecStart=%h/.local/bin/nanobot gateway` 等示例。
   - 这与仓库级约束“Sidecar 目录为 `ava/`，启动入口为 `python -m ava`”不一致。
   - 新生命周期方案必须顺手统一涉及 supervisor 的文档入口。

4. **现有 `restart_gateway` 设计方向应废弃**
   - 旧实现位于 `ava/skills/restart_gateway/`，包含：
     - `restart_gateway.sh`
     - `restart_wrapper.sh`
     - `restart_daemon.sh`
     - `at_report.sh`
     - `gateway_watchdog.sh`
     - `com.nanobot.gateway.watchdog.plist`
   - 其核心特征是：
     - 通过 shell 包装层串联延迟重启、状态汇报、进程拉起。
     - 依赖 `at`、`launchd`、`nohup`、`ps/grep/pgrep`。
     - 存在机器路径、平台路径和运维假设耦合。
     - Console 当前通过 `ava/console/services/gateway_service.py` shell 到该 skill 脚本。
   - 该方向与 supervisor-first 生命周期管理相冲突，应整体下线而非继续修补。

5. **GitHub secret-scanning `#1` 已锁定为结构性治理问题**
   - GitHub alert `#1` 首次位置为：
     - 提交：`25e5493d8c51350332065bed9c76da7241ee546d`
     - 路径：`nanobot/skills/restart_gateway/scripts/at_report.sh:25`
   - secret 类型为：`telegram_bot_token`
   - GitHub 当前状态为：`resolved`
   - GitHub 当前 resolution 为：`revoked`
   - 结论：
     - 密钥本身已撤销，但架构问题仍在。
     - 需要通过删除旧重启脚本体系、禁止 repo 内硬编码通知密钥、补充 secret regression 测试，完成结构性清理。

### 2.2 设计结论

- 生命周期设计要分层：
  - **Supervisor 层**：负责 crash 后重拉。
  - **Ava 进程内层**：负责状态记录、重启请求、优雅退出、API/Tool 统一接入。
- `restart` 不应再承担“拉起新进程”的职责，而应变成“当前进程有状态地退出，由 supervisor 拉起”。
- “自动汇报”“watchdog”“平台专属 daemon 配置”不应再与基础 restart 能力绑定。

## 3. Innovate (Options & Decision)

### Option A: 继续修旧 shell skill

- 描述：保留 `ava/skills/restart_gateway/`，继续修 `at`、watchdog、路径硬编码和 Console shell 调用。
- 结论：**拒绝**
- 原因：
  - 继续维持错误分层。
  - 与 supervisor-first 原则冲突。
  - 复杂度高，测试脆弱，平台耦合严重。

### Option B: 仓库内自带 watchdog / 自建保活器

- 描述：删除旧 skill，但在 `ava/` 中用 Python 或 shell 重新做一套跨平台 watchdog。
- 结论：**拒绝**
- 原因：
  - 依然把宿主进程管理职责塞回应用内部。
  - 会重复实现 Docker / systemd 已经成熟提供的能力。
  - 仍然会带来平台差异和运维歧义。

### Option C: supervisor-first + `ava` 生命周期控制后端

- 描述：Crash 自动恢复完全依赖 Docker `restart` 或 `systemd Restart=always`；`ava` 只负责状态、重启请求、优雅退出与统一控制面。
- 结论：**选中**
- 原因：
  - 分层清晰。
  - 与现有 Docker / Linux Service 方向一致。
  - 最容易获得可靠性、可测试性和文档一致性。

## 4. Plan (Contract)

### 4.1 File Changes

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 1 | `ava/runtime/lifecycle.py` | 新增 | 生命周期后端，负责 runtime 状态、重启请求、退出协调、元数据 |
| 2 | `ava/tools/gateway_control.py` | 新增 | 生命周期控制工具，仅提供 `status` / `restart` |
| 3 | `ava/patches/tools_patch.py` | 修改 | 注册 `gateway_control` 工具 |
| 4 | `ava/patches/console_patch.py` | 修改 | Gateway 启动时初始化 runtime 状态、PID、重启协调 |
| 5 | `ava/console/services/gateway_service.py` | 修改 | 移除 shell subprocess，改走共享生命周期后端 |
| 6 | `ava/console/models.py` | 修改 | `GatewayStatus` 增加 `supervised` / `supervisor` / `restart_pending` |
| 7 | `ava/console/routes/gateway_routes.py` | 修改 | 继续保留 restart/status API，但改为共享后端语义 |
| 8 | `ava/console/services/config_service.py` | 修改 | 移除 `restart_gateway.json` 可编辑配置入口 |
| 9 | `ava/skills/restart_gateway/` | 删除 | 删除旧 skill 全目录 |
| 10 | `README.md` | 修改 | 将生命周期 / supervisor 相关示例统一到 `python -m ava gateway` |
| 11 | 生命周期运维文档 | 新增 | 说明 Docker / systemd 的推荐部署与重启语义 |
| 12 | `tests/runtime/test_lifecycle_manager.py` | 新增 | 生命周期后端测试 |
| 13 | `tests/tools/test_gateway_control.py` | 新增 | 新工具测试 |
| 14 | `tests/console/test_gateway_service.py` | 新增或修改 | Console 生命周期服务测试 |
| 15 | `tests/patches/test_console_patch_lifecycle.py` | 新增 | Console patch 生命周期接线测试 |
| 16 | `tests/security/test_no_embedded_secrets.py` | 新增 | secret regression 测试 |
| 17 | `tests/console/test_config_service.py` | 新增或修改 | 验证 `restart_gateway.json` 已移除 |

### 4.2 Interfaces / Signatures

#### `ava/runtime/lifecycle.py`

- 提供统一生命周期管理器，至少覆盖以下职责：
  - 写入 `~/.nanobot/runtime/` 下的 runtime 状态文件。
  - 记录当前 PID、启动时间、是否受 supervisor 管理、最近退出原因。
  - 接收并落盘重启请求。
  - 协调优雅退出与 `force=true` 下的强制退出。
  - 清理 stale restart request 与 transient 状态。

#### `ava/tools/gateway_control.py`

- 工具名称：`gateway_control`
- 动作集合：
  - `status`
  - `restart`
- 约束：
  - `restart` 仅允许在 `cli` / `console` 上下文执行。
  - `restart` 在 unsupervised 模式下返回明确的 unsupported 结果。
  - `restart` 不直接拉起新进程。

#### `GatewayStatus`

- 新增字段：
  - `supervised: bool`
  - `supervisor: str | None`
  - `restart_pending: bool`

### 4.3 Implementation Checklist

- [ ] 1. 在 spec 中明确“禁止修改 `nanobot/`，本任务全部在 `ava/` 完成”。
- [ ] 2. 明确旧 `restart_gateway` 全目录删除，不保留脚本兼容层。
- [ ] 3. 明确新运行时目录使用 `~/.nanobot/runtime/`。
- [ ] 4. 明确 runtime 状态文件至少包含：当前 PID、启动时间、是否受 supervisor 管理、待处理重启请求、最后一次退出原因。
- [ ] 5. 明确 `gateway_control.restart` 只负责“请求当前进程优雅退出”，不负责自行拉起新进程。
- [ ] 6. 明确 crash 自动恢复依赖 Docker `restart` 或 `systemd Restart=always`。
- [ ] 7. 明确 unsupervised 启动下 `restart` 返回“unsupported without supervisor”。
- [ ] 8. 明确 `force=true` 语义为缩短优雅退出等待后硬退出，不做 `kill + nohup`。
- [ ] 9. 明确 Console `POST /api/gateway/restart` 与 tool 共用同一后端。
- [ ] 10. 明确 remote chat channel 禁止调用 `gateway_control.restart`。
- [ ] 11. 明确删除 `restart_gateway.json` 与所有 Telegram 汇报配置路径。
- [ ] 12. 明确 README / ops 文档的 supervisor 样例统一为 Sidecar 入口 `python -m ava gateway`。
- [ ] 13. 明确 secret-scanning 修复写入 spec：仓库内不得再存放 bot token、私钥、频道 ID 等运行时密钥。
- [ ] 14. 明确实现后需清理所有对 `restart_gateway`、`at_report`、`gateway_watchdog`、`launchd` 的引用。

### 4.4 Test Coverage

#### `tests/runtime/test_lifecycle_manager.py`

- 启动时写入 runtime 状态。
- 重启请求落盘与去重。
- graceful timeout 后 forced exit 分支。
- stale restart request 清理。

#### `tests/tools/test_gateway_control.py`

- `status` 返回 runtime + supervisor 信息。
- `restart` 参数校验。
- 非 `cli` / `console` 上下文拒绝重启。
- unsupervised 模式拒绝重启。

#### `tests/console/test_gateway_service.py`

- Console restart/status 走共享后端而非 shell。
- 返回 `restart_pending`、`supervised`、`supervisor`。

#### `tests/patches/test_console_patch_lifecycle.py`

- Gateway 启动时写 PID/runtime 状态。
- 重启请求触发后进入退出协调分支。
- 退出时清理 transient 状态。

#### `tests/security/test_no_embedded_secrets.py`

- 扫描 `ava/`、`.specanchor/`、`tests/`，禁止出现：
  - Telegram bot token
  - 私钥 PEM
  - OpenSSH private key
  - 常见 PAT 模式
- 允许 README 中的占位符示例。
- 禁止真实值进入仓库。

#### `tests/console/test_config_service.py`

- `restart_gateway.json` 不再出现在可编辑配置列表中。

#### 文档验收场景

- Docker Compose 继续使用现有 `restart: unless-stopped`。
- systemd 示例统一为 `ExecStart=python -m ava gateway`。
- README 不再把新生命周期方案指向 `nanobot gateway`。

## 5. Execute Log

- [ ] 尚未进入 Execute。
- [ ] 当前文档仅锁定实现边界、接口形态、Checklist 与测试要求。

## 6. Review Verdict

- Spec coverage: `PASS`
- Behavior check: `N/A（当前为任务 spec，尚未实施）`
- Regression risk: `Low（当前仅新增 task spec，不改运行时代码）`
- Follow-ups:
  - 实施阶段严格限定在 `ava/` 内完成。
  - 删除旧 `restart_gateway` 前先统一替换所有调用点。

## 7. Plan-Execution Diff

- Any deviation from plan: `None`
- 备注：
  - 本 spec 为实现级任务单，不是讨论稿。
  - 所有关键决策已锁定，不留待实现者二次决策。
  - 本任务与当前工作区中未提交的 `restart_gateway` 改动不做兼容，最终方向是整体替换。
