---
specanchor:
  level: global
  type: architecture
  version: "1.0.0"
  author: "@Ziyan Lin"
  reviewers: []
  last_synced: "2026-03-23"
  last_change: "初始创建"
  applies_to: "**/*"
---

# 架构约定

## 目录结构
- nanobot/channels/ — 消息通道（Telegram, Discord, Slack 等）
- nanobot/agent/ — AI Agent 核心逻辑
- nanobot/providers/ — LLM 提供商适配层
- nanobot/config/ — Pydantic 配置 schema + 加载器
- nanobot/bus/ — 事件总线（跨模块通信）
- nanobot/cli/ — CLI 入口 (Typer)
- nanobot/console/ — Web 管理面板 (FastAPI)

## 模块边界
- Channel 通过 bus 发布/订阅事件与 Agent 通信
- Channel 注册由 manager.py 统一管理
- 配置集中在 config/schema.py，每个 channel 有独立 Config 子类
- Provider 通过 registry.py 注册，与 Channel 无直接依赖

## 数据流
- 用户消息 → Channel.start() 收消息 → bus 发布 → Agent 处理 → Channel.send() 回复
