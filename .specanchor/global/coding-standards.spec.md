---
specanchor:
  level: global
  type: coding-standards
  version: "1.0.0"
  author: "@Ziyan Lin"
  reviewers: []
  last_synced: "2026-03-23"
  last_change: "初始创建"
  applies_to: "**/*.py"
---

# 编码规范

## 技术栈
- 语言: Python 3.11+
- 框架: Typer (CLI), FastAPI (Console), Pydantic v2 (Config)
- HTTP 客户端: httpx (async)
- 日志: loguru
- 异步: asyncio / async-await

## 命名约定
- 模块目录: 小写下划线 (snake_case)
- 文件命名: snake_case.py
- 类名: PascalCase (如 TelegramChannel, BaseChannel)
- 函数/方法: snake_case
- 常量: UPPER_SNAKE_CASE

## 代码约定
- Channel 类继承 BaseChannel，实现 start/stop/send
- 配置使用 Pydantic BaseModel，字段可选带默认值
- 错误处理: try/except + loguru logger.error
- 异步方法使用 async def，HTTP 请求使用 httpx.AsyncClient

## Git 提交约定
- 格式: `<type>(<scope>): <subject>`
- type: feat / fix / docs / refactor / test / chore
