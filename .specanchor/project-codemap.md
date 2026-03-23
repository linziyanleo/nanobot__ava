# Project Codemap: nanobot-ai

## 入口
- `nanobot/__main__.py` → CLI 入口
- `nanobot/cli/commands.py` → Typer 命令定义

## 核心模块
- `nanobot/agent/` — Agent 循环、上下文、记忆、技能
- `nanobot/channels/` — 消息通道（base, manager, telegram, discord, slack...）
- `nanobot/providers/` — LLM 提供商（litellm, openai, azure...）
- `nanobot/config/` — 配置 schema + 加载
- `nanobot/bus/` — 事件总线

## 辅助模块
- `nanobot/console/` — Web 管理面板
- `nanobot/cron/` — 定时任务
- `nanobot/heartbeat/` — 心跳服务
- `nanobot/storage/` — 数据存储
- `nanobot/skills/` — Agent 技能
