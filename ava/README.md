# Ava Sidecar Quick Start

`ava/` 是这个仓库里的 Sidecar 扩展层。

如果你想使用 Sidecar patch 生效后的行为，例如：

- 继承式 schema fork
- 兼容旧 sidecar config 的 `onboard` 初始化 / refresh / wizard save
- Gateway 自动挂载 Console
- SQLite storage、自定义 tools、扩展 skills

不要直接运行 `nanobot ...`，而要在项目环境里运行 `python -m ava ...`。

## 1. 安装项目依赖

推荐使用 `uv`：

```bash
uv sync
```

也可以使用 `pip`：

```bash
pip install -e .
```

如果你已经激活了项目虚拟环境，可以直接用 `python -m ava ...`。
如果没有激活环境，推荐统一用 `uv run python -m ava ...`。

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

- `python -m ava onboard` 会先应用 `ava/patches/*`，再进入上游 CLI
- 因此写出的 `config.json` 会带上 Ava patch 期望的 schema / onboard 语义
- 如果你要初始化 Sidecar 兼容配置，不要用 `nanobot onboard`

## 3. 运行 Ava

启动网关：

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

当前打包配置只暴露了 `nanobot` console script，`ava` 还没有单独的安装后命令入口。
所以在这个仓库 checkout 里，Ava 的稳定用法就是：

```bash
uv run python -m ava <command>
```

## 5. 什么时候必须用 Ava 入口

以下场景都应该使用 `python -m ava ...`：

- 初始化或刷新 Sidecar 配置
- 运行带 Console 的 gateway
- 使用 SQLite storage / custom tools / patched skills loader
- 验证 `ava/patches/*` 是否按预期生效

如果你只是想运行原生上游 `nanobot`，才使用 `nanobot ...`。
