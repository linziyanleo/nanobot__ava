# Module Spec: Codex Tool

> 模块路径：`ava/tools/codex.py`
> 状态：✅ 已实现
> 关联：`ava/agent/bg_tasks.py`（BackgroundTaskStore）

## 1. 定位

独立的 Codex coding 工具，通过 OpenAI Codex API（或兼容 API）执行代码任务。与 `claude_code` 平行存在，不共享基类，但共享 `BackgroundTaskStore` 进行异步任务管理。

**设计原则：独立工具 + 共享基础设施**
- `claude_code` 和 `codex` 是两个独立工具，各自保留完整的能力和特性
- LLM 看到两个工具的签名，可根据任务特征自主选择
- `BackgroundTaskStore` 是统一的异步任务管理层，两个工具共享

## 2. 与 claude_code 的差异

| 维度 | claude_code | codex |
|------|-------------|-------|
| 执行方式 | CLI subprocess (`claude -p`) | CLI subprocess (`codex exec`) |
| 输出格式 | 单行 JSON | JSONL 事件流 |
| Session 管理 | `--resume session_id` 可恢复 | 无 session 恢复 |
| 工具控制 | `--allowedTools` 白名单 | `--full-auto` / `-s read-only` sandbox |
| 模型 | `--model` 参数 | `-m` 参数或 `~/.codex/config.toml` |
| Sync 模式 | 有（`mode="sync"`） | 无，全异步 |
| 认证 | ANTHROPIC_API_KEY | CODEX_API_KEY / codex login |

## 3. 接口设计

### Tool 签名

```python
class CodexTool(Tool):
    name = "codex"

    async def execute(
        self,
        prompt: str,
        project_path: str | None = None,
        mode: str = "standard",
        **kwargs: Any,
    ) -> str
```

### 参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `prompt` | str | 是 | 任务描述 |
| `project_path` | str | 否 | 项目目录（默认 workspace） |
| `mode` | str | 否 | `fast` / `standard` / `readonly`（无 sync） |

### mode 映射

| mode | 行为 |
|------|------|
| `fast` | 异步，较短超时 |
| `standard` | 异步，默认 |
| `readonly` | 异步，只读分析（如果 API 支持） |

注意：Codex 没有 `sync` 模式——所有调用默认异步（通过 BackgroundTaskStore）。

## 4. 实现要点

### 4.1 API 调用

```python
async def _execute_background(self, *, prompt: str, project: str, mode: str, **_kw) -> dict:
    # 1. 构建 API 请求
    # 2. 调用 OpenAI Codex API（或兼容 API）
    # 3. 解析响应
    # 4. 记录 token stats
    # 5. 返回结构化结果
```

### 4.2 BackgroundTaskStore 集成

与 claude_code 完全一致：

```python
task_id = self._task_store.submit_coding_task(
    executor=self._execute_background,
    origin_session_key=self._session_key,
    prompt=prompt,
    project_path=project,
    timeout=timeout,
    mode=mode,
    project=project,
)
```

### 4.3 Token Stats 记录

复用 `self._token_stats.record()` 接口，但 `provider` 标记为 `"codex"` 或 `"openai-codex"`：

```python
self._token_stats.record(
    model=model_name,
    provider="codex",
    usage={...},
    model_role="codex",
    cost_usd=cost,
)
```

### 4.4 配置来源

从 `config.providers.openai_codex` 读取 API key 和 base URL：

```python
cc_config = SimpleNamespace(
    api_key=config.providers.openai_codex.api_key,
    base_url=config.providers.openai_codex.base_url,
)
```

## 5. 注册方式

在 `ava/patches/tools_patch.py` 中条件注册：

```python
codex_config = getattr(config.providers, "openai_codex", None)
if codex_config and codex_config.api_key:
    from ava.tools.codex import CodexTool
    codex_tool = CodexTool(
        workspace=workspace,
        token_stats=token_stats,
        task_store=getattr(self, 'bg_tasks', None),
        codex_config=codex_config,
    )
    self.tools["codex"] = codex_tool
```

同样需要在 `loop_patch.py` 的 post-init 引用回填中更新 `_task_store`。

## 6. TOOLS.md 文档

待工具实现后，在 `ava/templates/TOOLS.md` 中添加：

```markdown
## Codex

### codex

调用 Codex API 执行代码任务。全部异步。

codex(prompt: str, project_path: str = None, mode: str = "standard") -> str

**什么时候选 codex 而不是 claude_code：**
- [根据实际 API 能力补充]

**Notes:**
- 全部异步，通过 BackgroundTaskStore 管理
- 需要配置 `providers.openai_codex.api_key`
```

## 7. 已解决问题

- [x] Codex 调用方式：`codex exec "prompt" --json -C <project>` 非交互模式，JSONL 事件流输出
- [x] Sandbox 模式：`--full-auto`（fast/standard）或 `-s read-only`（readonly），不需要文件系统上传
- [x] 模型选择：默认使用 codex CLI 的 `~/.codex/config.toml` 配置（用户当前是 `gpt-5.4`），可通过 `providers.openai_codex` 覆盖
- [x] 选择策略：LLM 自主选择，不做 tool 层自动路由

## 8. 实现与 Spec 的偏差

| Spec 原设计 | 实际实现 | 原因 |
|------------|---------|------|
| REST API 调用 | CLI subprocess（与 claude_code 同构） | Codex CLI 已安装且功能完善，subprocess 方式更简单、更一致 |
| `_execute_background` | `_run_background` | 避免与 claude_code 的方法名冲突，语义更清晰 |
| `config.providers.openai_codex.base_url` | 注入 `OPENAI_BASE_URL` 环境变量 | codex CLI 不接受 `--base-url` 参数，通过环境变量传递 |
| ProviderConfig.model 字段 | 上游 ProviderConfig 无 model 字段 | 通过 `getattr(codex_cfg, "model", "")` 安全读取，无值时让 codex CLI 用自身默认 |

## 9. 测试覆盖

`tests/tools/test_codex.py`（38 个测试）：

| 类别 | 测试数 | 覆盖内容 |
|------|--------|---------|
| Properties | 3 | name / description / parameters schema |
| Context | 3 | 默认上下文 / set_context / session_key 直传 |
| Command Building | 4 | standard / readonly / fast / 无 model |
| JSONL Parsing | 8 | 基础成功 / 多轮 / turn.failed / error / 空输出 / 无 agent_message / 畸形行 / 最后消息优先 |
| Output Formatting | 3 | 成功 / 错误 / 长文本截断 |
| Execute Integration | 5 | 无 binary / 不存在路径 / 提交 store / fast 超时 / standard 超时 |
| Cancel | 2 | 委托 store / 无 store |
| Record Stats | 3 | 正常记录 / 错误 finish_reason / 无 collector |
| Project Resolution | 2 | 显式路径 / 默认路径 |
| Config Injection | 2 | 默认配置 / 自定义配置 |
| Patch Integration | 3 | tools_patch 导入 / 条件注册 / loop_patch 回填 |

## 10. 不做什么

- 不创建 `CodingDevTool` 抽象基类
- 不统一 claude_code 和 codex 的接口
- 不在 tool 层做自动路由（LLM 自主选择）
- 不支持 sync 模式（codex 全异步）
- 不支持 session 恢复（codex CLI 的 resume 能力不对标 claude_code 的 session_id）

## 11. Future TODO（未实现）

以下内容是 `console_ui_dev_loop` 的后续阶段规划，不代表当前 codex contract 已满足：

- 作为 `console_ui_dev_loop` 的 Phase B 主路径进入条件：
  - 补一个可调用的后台任务状态/等待工具面，而不是依赖 `/task`
  - 明确 async continuation 如何续接 loop skill 所需上下文
- 评估是否需要为 loop 层提供“伪阻塞”等待语义：
  - tool 级 `wait`
  - 或 orchestrator 级轮询/继续协议
- 为 Codex 主路径补 benchmark：
  - 与 `claude_code sync` 对比成功率
  - 平均轮次 / 总耗时
  - 在前端任务上的回归通过率
- 若上述条件未满足，Codex 继续保留为可选异步 coding 工具，而不是 v1 默认路径
