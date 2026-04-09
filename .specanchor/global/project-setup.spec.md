---
specanchor:
  level: global
  type: project-setup
  version: "1.0.0"
  author: "Ziyan Lin"
  reviewers: []
  last_synced: "2026-04-09"
  last_change: "迁移 root anchor.yaml，并按 sidecar 真实入口重扫项目启动规范"
  applies_to: "**/*"
---

# 项目启动指南

## 基本信息
- 项目形态：`nanobot-ai` 上游仓 + `ava/` sidecar 扩展层 + `console-ui/` 前端子应用
- 稳定入口：sidecar 语义一律走 `uv run python -m ava <command>`；只验证原生上游时才用 `nanobot ...`
- 本地地址：`console-ui` 开发态默认 `http://localhost:5173`
- 默认评审人：仓库内未声明固定 reviewer，按当前任务 owner 指定

## 环境要求
- Python：`>=3.11`，依赖由 `uv sync` 或 `pip install -e .` 安装
- Node.js：`bridge/` 需要 `>=20`；`console-ui/` 需 npm 生态
- 测试基线：`pytest` + `pytest-asyncio`，前端改动按需补 `npm run build`

## 启动命令
- sidecar 初始化：`uv run python -m ava onboard`
- gateway / agent：`uv run python -m ava gateway`、`uv run python -m ava agent -m "Hello"`
- console-ui：`cd console-ui && npm install && npm run dev`
- bridge：`cd bridge && npm install && npm run dev`

## 开发约定
- 以功能分支开发；涉及上游同步或 `nanobot/` 例外修改时必须显式注明原因
- 历史开发 spec 继续保留在 `mydocs/specs/`，由 `anchor.yaml` 纳入治理而不迁移文件
