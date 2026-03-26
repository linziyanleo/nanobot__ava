# CLAUDE.md

## 核心规则

- **禁止修改 `nanobot/` 目录**：所有定制功能通过 `ava/patches/*_patch.py` 的 Monkey Patch 实现
- 唯一例外：修复上游 bug 或添加上游功能、准备给 nanobot 提 PR 时，才允许修改 `nanobot/` 文件
- Sidecar 目录：`ava/`，启动入口：`python -m ava`
- Patch 规范见 `.specanchor/global-patch-spec.md`

## 项目结构

- `nanobot/` — 上游框架代码（保持纯净）
- `ava/` — Sidecar 扩展目录
  - `ava/patches/` — Monkey Patch 文件（8 个，按字母序执行）
  - `ava/forks/` — 需要完整替换的上游模块 Fork
  - `ava/tools/` — 自定义工具（claude_code, image_gen, vision, sticker, memory_tool）
  - `ava/console/` — Web Console 子应用
  - `ava/storage/` — SQLite 存储层
  - `ava/agent/` — Agent 扩展模块（记忆、压缩、摘要、命令）
  - `ava/launcher.py` — Patch 发现与执行入口
- `.specanchor/` — SpecAnchor 规范文档
- `tests/` — 测试目录

## 开发约定

- 语言：文档和注释使用中文，代码标识符保持英文
- 测试框架：pytest + pytest-asyncio，asyncio_mode = "auto"
- Patch 命名：`ava/patches/{module}_patch.py`，函数 `apply_{module}_patch() -> str`
- 每个 patch 文件末尾通过 `register_patch()` 自注册
