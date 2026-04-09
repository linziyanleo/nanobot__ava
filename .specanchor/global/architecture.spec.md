---
specanchor:
  level: global
  type: architecture
  version: "1.0.0"
  author: "Ziyan Lin"
  reviewers: []
  last_synced: "2026-04-09"
  last_change: "按 upstream + sidecar + console 三层结构重建可加载架构规范"
  applies_to: "**/*"
---

# 架构约定

## 目录结构约定
- `nanobot/`：上游框架数据面，默认保持纯净，用于承接 upstream merge 与通用能力
- `ava/`：sidecar 扩展层，包含 `patches/`、`forks/`、`tools/`、`console/`、`storage/`、`agent/`
- `console-ui/`：Console React 前端；`bridge/`：独立 Node 桥接进程；`tests/`：按能力面分层验证

## 模块边界规则
- 所有 sidecar 定制优先落在 `ava/`；能 patch 不 fork，能 fork 不改上游
- `python -m ava` 先执行 `ava.launcher.apply_all_patches()`，再委派到 `nanobot.cli.commands:app`
- `console-ui/` 只通过 `/api/*` 与后端交互，不直接耦合 Python 内部实现细节
- 历史 spec、研究和上下文沉淀继续留在 `mydocs/`，由 SpecAnchor 做治理映射

## 数据流约定
- CLI / gateway 主入口：`ava.__main__` -> `ava.launcher` -> `nanobot` CLI
- Console 路由：`ava.console.routes.*` -> `ava.console.app` service -> runtime / storage / bg task
- API 模式：`nanobot/api/server.py` 提供 OpenAI-compatible HTTP 包装，面向固定 session

## 参考关系
- 详细 patch 约束见 `.specanchor/global/patch-governance.spec.md`
- 旧版长文档 `.specanchor/global-patch-spec.md` 继续保留作历史说明，不作为新的加载入口
