# AGENTS.md

本文件是给 Codex 使用的项目级约束说明。

## 1. 核心约束（必须遵守）

- 禁止修改 `nanobot/` 目录：所有定制功能必须通过 `ava/patches/*_patch.py` 的 Monkey Patch 实现。
- 唯一例外：仅当以下场景成立时，才允许修改 `nanobot/`：
  - 修复上游 bug；
  - 添加上游通用能力；
  - 本次改动明确目标是向 nanobot 上游提交 PR。
- Sidecar 目录为 `ava/`，启动入口为 `python -m ava`。
- Patch 规范以 `.specanchor/global-patch-spec.md` 为准。

## 2. 仓库结构认知

- `nanobot/`：上游框架代码，默认保持纯净。
- `ava/`：Sidecar 扩展目录。
  - `ava/patches/`：Monkey Patch 文件（按字母序执行）。
  - `ava/forks/`：需要完整替换的上游模块 Fork。
  - `ava/tools/`：自定义工具（如 `claude_code`、`image_gen`、`vision`、`sticker`、`memory_tool`）。
  - `ava/console/`：Web Console 子应用。
  - `ava/storage/`：SQLite 存储层。
  - `ava/agent/`：Agent 扩展模块（记忆、压缩、摘要、命令）。
  - `ava/launcher.py`：Patch 发现与执行入口。
- `.specanchor/`：SpecAnchor 规范文档。
- `tests/`：测试目录。

## 3. 开发约定

- 文档与注释使用中文；代码标识符保持英文。
- 测试框架：`pytest` + `pytest-asyncio`，`asyncio_mode = "auto"`。
- Patch 命名规范：
  - 文件名：`ava/patches/{module}_patch.py`
  - 函数名：`apply_{module}_patch() -> str`
  - 每个 patch 文件末尾必须通过 `register_patch()` 自注册。

## 4. 实施流程（Codex 工作方式）

1. 先判断需求是否可以在 `ava/` 内完成。
2. 如可在 `ava/` 内完成，禁止触碰 `nanobot/`。
3. 如必须改 `nanobot/`，先在说明中明确“例外理由”（bugfix / upstream feature / PR prep），再执行改动。
4. 涉及 patch 时，严格遵循命名和注册规范。
5. 改动后优先补齐或更新对应测试。

## 5. 提交前检查清单

- 是否误改 `nanobot/`（若有，是否具备例外理由并已说明）？
- 新增或修改的 patch 是否符合命名规范并完成 `register_patch()`？
- 文档与注释是否为中文、代码标识符是否保持英文？
- 相关测试是否通过（至少覆盖受影响模块）？
