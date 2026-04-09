---
specanchor:
  level: global
  type: coding-standards
  version: "1.0.0"
  author: "Ziyan Lin"
  reviewers: []
  last_synced: "2026-04-09"
  last_change: "按 Python sidecar + React console 双栈代码形态重扫编码规范"
  applies_to: "**/*.{py,ts,tsx,js,css}"
---

# 编码规范

## 技术栈
- 后端：Python 3.11、Typer、aiohttp、FastAPI、Pydantic v2、loguru
- 前端：React 19、TypeScript 5.9、Vite 7、React Router 7、Zustand、Tailwind CSS 4
- 测试：`pytest` / `pytest-asyncio`；前端以类型检查和构建通过为主

## 命名约定
- 代码标识符保持英文；文档、注释、面向维护者的说明默认使用中文
- patch 文件命名固定为 `ava/patches/{module}_patch.py`，入口函数为 `apply_{module}_patch() -> str`
- React 组件使用 `PascalCase`，hooks / store / util 使用 `camelCase`

## 代码约定
- Python 文件默认启用类型注解，常见模式为 `from __future__ import annotations`
- patch / 路由层禁止静默失败；缺失拦截点或运行依赖时要 `logger.warning(...)` 并优雅降级
- sidecar 初始化避免 eager I/O，重资源对象放在运行时懒加载或 service 层
- 前端遵循 TS strict；不要绕过 ESLint 规则堆积未使用变量和隐式 any

## Git 提交约定
- 提交格式遵循 `<type>(<scope>): <subject>`
- 上游同步、upstream bugfix、sidecar 定制要在 scope 或正文中明确边界
