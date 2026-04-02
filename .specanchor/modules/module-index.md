# Module Spec 索引

> 最后更新：2026-04-02

## Patch 模块（已实现）

| Patch 文件 | Spec 文件 | 状态 | 说明 |
|-----------|----------|------|------|
| `ava/patches/a_schema_patch.py` | [schema_patch_spec.md](schema_patch_spec.md) | ✅ | Config Schema 模块替换 |
| `ava/patches/b_config_patch.py` | [config_patch_spec.md](config_patch_spec.md) | ✅ | Config 字段注入（降级方案） |
| `ava/patches/bus_patch.py` | [bus_console_listener_spec.md](bus_console_listener_spec.md) | ✅ | MessageBus Console listener |
| `ava/patches/c_onboard_patch.py` | [onboard_patch_spec.md](onboard_patch_spec.md) | ✅ | onboard refresh 旧配置兼容层 |
| `ava/patches/channel_patch.py` | [channel_patch_spec.md](channel_patch_spec.md) | ✅ | 消息批处理 |
| `ava/patches/console_patch.py` | [console_patch_spec.md](console_patch_spec.md) | ✅ | Web Console 独立服务 |
| `ava/patches/context_patch.py` | [context_patch_spec.md](context_patch_spec.md) | ✅ | 历史摘要+压缩+分类记忆注入 |
| `ava/patches/loop_patch.py` | [loop_patch_spec.md](loop_patch_spec.md) | ✅ | AgentLoop 属性注入 + token 统计 |
| `ava/patches/skills_patch.py` | [skills_patch_spec.md](skills_patch_spec.md) | ✅ | SkillsLoader 三源发现 + SQLite disabled filter |
| `ava/patches/storage_patch.py` | [storage_patch_spec.md](storage_patch_spec.md) | ✅ | SQLite 存储层替换 |
| `ava/patches/tools_patch.py` | [tools_patch_spec.md](tools_patch_spec.md) | ✅ | 5 个自定义工具注入 |
| `ava/patches/transcription_patch.py` | [transcription_patch_spec.md](transcription_patch_spec.md) | ✅ | GroqTranscriptionProvider 代理注入 |

## 已接入模块

| 模块文件 | 接入方式 | 状态 | 说明 |
|---------|----------|------|------|
| `ava/agent/categorized_memory.py` | `loop_patch` 注入 + `context_patch` 注入记忆 | ✅ | 分类记忆系统 |
| `ava/agent/history_compressor.py` | `loop_patch` 注入 + `context_patch` 调用 | ✅ | 历史压缩器 |
| `ava/agent/history_summarizer.py` | `loop_patch` 注入 + `context_patch` 调用 | ✅ | 历史摘要器 |

## 已复制但未接入模块

| 模块文件 | Spec 文件 | 状态 | 说明 |
|---------|----------|------|------|
| `ava/agent/commands.py` | [commands_spec.md](commands_spec.md) | 🟡 | 统一命令系统 |

## 其他模块

| 模块路径 | 说明 |
|---------|------|
| `ava/console/` | Web Console 子应用（FastAPI + WebSocket） |
| `ava/tools/` | 5 个自定义工具实现 |
| `ava/storage/` | SQLite 数据库封装 |
| `ava/channels/` | 消息批处理器实现 |
| `ava/session/` | Session backfill 实现 |
| `ava/forks/config/` | Config Schema Fork 文件 |
| `ava/skills/` | Skills 静态文件 |
| `ava/templates/` | 模板静态文件 |
