---
specanchor:
  level: module
  module_name: "AgentLoop 注入 Patch"
  module_path: "ava/patches/loop_patch.py"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-03-26"
  updated: "2026-04-09"
  last_synced: "2026-04-09"
  last_change: "按 SpecAnchor 最新 Module Spec 模板重生，合并 legacy spec 与当前代码扫描结果"
  status: "active"
  depends_on:
    - "ava/launcher.py"
    - "ava/agent/bg_tasks.py"
    - "ava/runtime/lifecycle.py"
---

# AgentLoop 注入 Patch (loop_patch)

## 1. 模块职责
- **属性注入**：在 AgentLoop.__init__ 完成后绑定 db/token_stats/media_service/categorized_memory/history_summarizer/history_compressor
- **Token 统计**：包装 _run_agent_loop（拦截 provider 调用获取原始 usage）和 _process_message（每轮记录完整字段）
- **Conversation 分段**：为同一 session_key 下的逻辑新会话维护 session.metadata["conversation_id"]；/new 前置轮换新 id，后续 turn 在该 conversation 内重新从 0 编号
- **Phase 0 预记录**：在 patched_run_agent_loop 开头（LLM 调用前）写入 pending 状态的 token_usage 记录，首次 LLM 调用完成后 UPDATE 填入真实数值

## 2. 业务规则
- 保留原始方法引用并打 patched 标记，重复 apply 不得产生副作用
- 目标拦截点不存在时必须 warning + skip，不能静默失败
- 补丁逻辑优先收敛在入口/出口层，避免把 sidecar 规则深入写进上游中段实现

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `set_shared_db()` | `set_shared_db(db) -> None` | Called by storage_patch to share the Database instance. |
| `get_agent_loop()` | `get_agent_loop()` | Return the most recently created AgentLoop instance (or None). |
| `apply_loop_patch()` | `apply_loop_patch() -> str` | 公共函数 |
| `TimelineEvent` | `class` | 核心类 |
| `TaskSnapshot` | `class` | 核心类 |
| `BackgroundTaskStore` | `class` | 统一后台任务注册/状态机/timeline/持久化/digest。 |
| `BackgroundTaskStore.record_event()` | `record_event(task_id: str, event: str, detail: str = '') -> None` | 通用事件记录接口（供 cron/subagent observer 使用）。 |
| `BackgroundTaskStore.cancel()` | `cancel(task_id: str) -> str` | 公共方法 |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| _shared_db | module | 模块级共享状态或常量 |
| _agent_loop_ref | module | 模块级共享状态或常量 |
| TaskStatus | module | 模块级共享状态或常量 |
| _MAX_CONTINUATION_BUDGET | module | 模块级共享状态或常量 |
| _FINISHED_RETENTION_MAX_ITEMS | module | 模块级共享状态或常量 |
| _FINISHED_RETENTION_MAX_AGE_S | module | 模块级共享状态或常量 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.agent.loop.AgentLoop
- nanobot.utils.helpers.estimate_prompt_tokens（当轮 token 估算）
- ava.storage.Database
- ava.console.services.token_stats_service.TokenStatsCollector

## 5. 已知约束 & 技术债
- [ ] `AgentLoop._save_turn` 的包装仍承担 skip 与 compressed history 对齐修正，后续上游改签名时要优先复核这里。
- [ ] return Database(get_data_dir() / "nanobot.db") # fallback
- [ ] 执行顺序：loop_patch（l）先于 storage_patch（s），首次用 fallback db，storage_patch 运行后通过 set_shared_db() 替换为共享 db。

## 6. TODO
- [ ] 代码行为变化后同步更新接口表、关键文件表和 module-index @ZiyanLin
- [ ] 如上游新增同类能力，重新评估 keep / narrow / delete / upstream 的 patch 策略 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/patches/loop_patch.py`
- **核心链路**: `loop_patch.py` → 上游拦截点 → sidecar 补丁逻辑 → 原始运行时输出
- **数据流**: 触发 patch 注册 → 校验目标存在 → 包装/替换目标方法 → 返回 launcher/调用方可见结果
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/patches/loop_patch.py` | 模块主入口 |
| `ava/agent/bg_tasks.py` | 关联链路文件 |
| `ava/runtime/lifecycle.py` | 关联链路文件 |
- **外部依赖**: `ava/launcher.py`、`ava/agent/bg_tasks.py`、`ava/runtime/lifecycle.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-patches-loop_patch.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
