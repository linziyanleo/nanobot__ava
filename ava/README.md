# Ava Sidecar Quick Start

`ava/` 是这个仓库里的 sidecar 扩展层。

如果你要使用 sidecar patch、生效后的 schema fork、Console、SQLite storage、自定义 tools 或扩展 skills，不要直接运行 `nanobot ...`，而要在项目环境里运行 `python -m ava ...`。

## 1. 安装依赖

推荐使用 `uv`：

```bash
uv sync
```

也可以使用 `pip`：

```bash
pip install -e .
```

如果已经激活了项目虚拟环境，可以直接运行 `python -m ava ...`。  
如果没有激活环境，推荐统一使用 `uv run python -m ava ...`。

## 2. 初始化 Ava 配置

默认初始化：

```bash
uv run python -m ava onboard
```

交互式 wizard：

```bash
uv run python -m ava onboard --wizard
```

多实例配置：

```bash
uv run python -m ava onboard --config ~/.nanobot-telegram/config.json --workspace ~/.nanobot-telegram/workspace
```

说明：

- `python -m ava onboard` 会先应用 `ava/patches/*`，再进入上游 CLI。
- 因此生成出来的 `config.json` 会带上 Ava sidecar 期望的 schema 和 onboarding 语义。
- 如果你要初始化 sidecar 兼容配置，不要使用 `nanobot onboard`。

## 3. 运行 Ava

启动 gateway：

```bash
uv run python -m ava gateway
```

启动 agent：

```bash
uv run python -m ava agent -m "Hello"
```

指定配置和工作区：

```bash
uv run python -m ava gateway --config ~/.nanobot-telegram/config.json --workspace ~/.nanobot-telegram/workspace
```

## 4. `ava` 与 `nanobot` 的区别

| 入口 | 行为 |
| --- | --- |
| `nanobot ...` | 直接进入上游 CLI，不会先应用 `ava` sidecar patches |
| `python -m ava ...` | 先执行 `ava.launcher.apply_all_patches()`，再进入上游 CLI |

当前稳定入口是：

```bash
uv run python -m ava <command>
```

## 5. 何时必须使用 Ava 入口

以下场景都应该使用 `python -m ava ...`：

- 初始化或刷新 sidecar 配置
- 运行带 Console 的 gateway
- 使用 SQLite storage / custom tools / patched skills loader
- 验证 `ava/patches/*` 是否按预期生效

如果你只想运行原生上游 `nanobot`，才使用 `nanobot ...`。

## 6. Supervisor 与生命周期

Ava 采用 supervisor-first 的生命周期设计：重启由外部 supervisor（Docker / systemd）负责拉起新进程，Ava 自身只负责优雅退出。

Docker Compose 示例：

```yaml
services:
  ava:
    build: .
    command: python -m ava gateway
    restart: unless-stopped
    environment:
      - AVA_SUPERVISOR=docker
```

systemd 示例：

```ini
[Service]
ExecStart=/path/to/uv run python -m ava gateway
Restart=always
RestartSec=5
Environment=AVA_SUPERVISOR=systemd
```

本地开发（无 supervisor）：

```bash
uv run python -m ava gateway
```

## 7. Console 本地账号与 Mock 存储

Console 的账号、明文密码文件和 mock 数据分成两层维护：

- repo 内维护版本化 mock bundle 源：
  - `ava/console/mock_bundle/`
- 本地运行时可写 mock 副本：
  - `~/.nanobot/console/mock_data/`
- 本地账号 hash 存储：
  - `~/.nanobot/console/users.json`
- 本地明文密码文件：
  - `~/.nanobot/console/local-secrets/nanobot_password`
  - `~/.nanobot/console/local-secrets/mock_tester_password`

约束如下：

- `nanobot` 是本地管理员账号，供本机登录和验证 Console 使用。
- `mock_tester` 是本地 mock-only 测试账号，只能看到并编辑 `~/.nanobot/console/mock_data/`。
- repo 内不保存上述两个账号的明文密码，只保存运行时生成后的 bcrypt hash。
- `mock.nanobot.db` 不作为 repo 内长期维护的二进制真源；repo 维护的是 `ava/console/mock_bundle/mock_seed.json` 和 `ava/console/mock_bundle/MOCK_DATA_CONTRACT.md`，运行时再生成 `~/.nanobot/console/mock_data/mock.nanobot.db`。
