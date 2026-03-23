---
specanchor:
  level: task
  task_name: "评估为 nanobot 新增 Weixin Channel 的可行性"
  author: "@git_user"
  created: "2026-03-23"
  status: "review"
  last_change: "完成 Question/Explore/Findings，等待 Findings Reviewed 门禁确认"
  related_modules: []
  related_global: []
  writing_protocol: "research"
  research_phase: "FINDINGS"
  branch: "feat/0.0.1"
---

# Research: 评估为 nanobot 新增 Weixin Channel 的可行性

## 1. Research Question

- **核心问题**: 当前 nanobot 是否可以基于 `@tencent-weixin/openclaw-weixin` 新增一个可用的 Weixin channel。
- **调研范围**: 渠道插件形态兼容性、运行时依赖、接入路径、改造成本、主要风险。
- **范围边界（不调研什么）**: 不做生产级实现，不做真实微信账号联调，不做完整安全审计。
- **成功标准（什么算调研完成）**: 给出明确可行性判断（能/不能直接接）、可落地路线、关键阻塞点和下一步动作。
- **决策背景**: 现有 nanobot 已支持多渠道（Telegram/Feishu/DingTalk/QQ/WhatsApp 等），希望补齐微信生态入口。

## 2. Explore

### 2.1 调研方法

- 阅读 `@tencent-weixin/openclaw-weixin` npm README 与 unpkg 源码入口（`package.json`、`index.ts`、`src/channel.ts`）。
- 分析 nanobot 渠道架构（`nanobot/channels/*`、`nanobot/channels/manager.py`、`nanobot/config/schema.py`）。
- 对比已有 Node bridge 模式（`bridge/src/*` + `nanobot/channels/whatsapp.py`）与微信插件模式差异。
- 盘点 CLI 接入面（`nanobot/cli/commands.py`）与测试覆盖形态（`tests/test_*channel*.py`）。

### 2.2 调研过程

#### 方向 1: 直接复用 `@tencent-weixin/openclaw-weixin`

- 该包是 **OpenClaw 插件**，入口 `index.ts` 直接依赖 `openclaw/plugin-sdk`，通过 `api.registerChannel` 和 `api.registerCli` 完成注册。
- 插件内部运行依赖 OpenClaw runtime（routing/session/reply/channelRuntime），不是一个独立可直接调用的 SDK。
- `package.json` 声明 `node >=22`，而 nanobot 当前 bridge 工程是独立 Node 进程模式，不具备 OpenClaw 插件宿主。
- 结论：**无法在 nanobot 中“开箱即用”直接安装并启用该插件**。

#### 方向 2: 参考其协议实现 nanobot 原生 Weixin channel

- 微信侧协议已公开：`getupdates` 长轮询、`sendmessage`、`getuploadurl`、`getconfig`、`sendtyping`。
- 现有 nanobot channel 基础能力满足：入站消息总线、出站发送、allowlist、会话键、媒体目录。
- 可复用模式：
  - 入站轮询/重连：参考 `telegram.py`（长轮询循环）
  - 媒体与多格式处理：参考 `feishu.py`、`dingtalk.py`
  - Node bridge 辅助登录：参考 `whatsapp.py` + `bridge/`
- 结论：**技术上可行，但需要二次实现，不是低成本“装包即得”**。

#### 方向 3: 引入 OpenClaw 作为 sidecar 宿主

- 可让 OpenClaw 承载微信插件，再通过中间桥与 nanobot 对接。
- 优点是复用官方插件逻辑；缺点是引入双运行时（nanobot + openclaw）与双配置体系，运维和排障复杂度显著上升。
- 结论：作为短期验证可行，但不建议作为长期主路径。

### 2.3 实验/原型（如有）

- 本轮未执行代码原型，仅完成静态结构与协议层可行性评估。
- 如进入实现，建议先做 1 天 PoC：只打通文本收发与登录流程，再扩展媒体与 typing。

## 3. Findings

### 3.1 关键事实

1. nanobot 渠道是 Python 主体（`BaseChannel` + `ChannelManager` + `Config`），必要时可外挂 Node bridge（WhatsApp 已验证）。
2. `@tencent-weixin/openclaw-weixin` 不是通用库，而是 OpenClaw 插件，强依赖 `openclaw/plugin-sdk` 和 OpenClaw runtime 生命周期。
3. 因运行时耦合，无法直接在 nanobot 中 `npm install` 后无改造启用。
4. 微信后端 API 协议完整可见，具备“按协议重写”条件，因此 **新增 Weixin channel 在工程上可行**。
5. 最大风险不在代码结构，而在登录授权稳定性、会话上下文 token 管理、媒体加密上传链路与长期维护成本。

### 3.2 对比分析（如有多方案）

| 维度 | 方案 A：直接复用 openclaw 插件 | 方案 B：nanobot 原生实现（推荐） | 方案 C：OpenClaw sidecar |
| --- | --- | --- | --- |
| 落地可行性 | 低（运行时不兼容） | 高 | 中 |
| 开发量 | 低（理论）/高（实际改造） | 中高 | 中 |
| 运维复杂度 | 中 | 低中 | 高 |
| 对现架构侵入 | 高 | 中 | 高 |
| 长期维护 | 不确定 | 可控 | 复杂 |
| 首版周期（估算） | 不可控 | 3-6 天（文本+登录+基础测试） | 2-4 天 PoC，长期不优 |

### 3.3 Trade-offs

- **方案 A（直接复用）**:
  - Pros: 理论上复用官方实现。
  - Cons: 与 nanobot 架构不兼容，工程风险最高。
- **方案 B（原生实现）**:
  - Pros: 与现有 channel 体系一致，测试与发布链路统一，长期可维护。
  - Cons: 需要自行实现登录/轮询/媒体链路，初期开发投入较高。
- **方案 C（sidecar）**:
  - Pros: 初期可快速验证微信连通性。
  - Cons: 双系统耦合，配置和故障域复杂，后续治理成本高。

### 3.4 未解决的问题

- 微信登录态失效和多账号并发策略是否需要与现有 `channels login` 命令统一。
- 是否接受 Node >=22 作为新增微信链路前置要求（当前 bridge 默认 Node >=20）。
- 媒体加密上传是否先做图片/文件，还是一期即覆盖视频/语音。
- 目标是“微信（个人）”还是“企业微信/WeCom”，二者协议和合规边界不同。

## 4. Challenge & Follow-up

> 此阶段需在用户确认 Findings 后继续（gate: `Findings Reviewed`）。

### 4.1 Agent 追问

- [待 `Findings Reviewed` 后填写]

### 4.2 用户反馈

- [待 `Findings Reviewed` 后填写]

### 4.3 方向调整（基于追问）

- [待 `Findings Reviewed` 后填写]

## 5. Conclusion

### 5.1 Action Items

- [ ] 用户确认 `Findings Reviewed`，进入 Challenge 阶段。
- [ ] 明确目标渠道类型（微信个人号 / 企业微信）。
- [ ] 若选择方案 B，启动 PoC（文本收发 + 登录 + 最小测试）。

### 5.2 最终建议

- **推荐方案**: [待 `Findings Reviewed` 后填写]
- **推荐理由**: [待 `Findings Reviewed` 后填写]
- **风险提示**: [待 `Findings Reviewed` 后填写]
- **下一步**: [待 `Findings Reviewed` 后填写]
