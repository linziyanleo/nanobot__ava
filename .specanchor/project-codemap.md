# Project Codemap

## 主体结构

- `nanobot/`：上游 agent / channel / provider / CLI / API 实现
- `ava/`：sidecar patch、fork、tools、console、storage、runtime 扩展
- `console-ui/`：Console React 前端
- `bridge/`：WhatsApp bridge Node 进程
- `tests/`：patch、console、runtime、tools、安全等验证入口
- `mydocs/`：历史 spec、research、context、persona 资产

## 关键链路

- sidecar 启动：`ava/__main__.py` -> `ava/launcher.py` -> `nanobot.cli.commands`
- Console：`ava.console.routes.*` -> services -> storage / runtime / bg tasks
- OpenAI-compatible API：`nanobot/api/server.py`
