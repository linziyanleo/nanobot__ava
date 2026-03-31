---
specanchor:
  level: task
  task_name: "nanobot 上游三个 Bugfix PR"
  author: "@fanghu"
  created: "2026-03-30"
  status: "draft"
  last_change: "初始化 task spec"
  related_global:
    - ".specanchor/global/architecture.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "各 PR 独立分支，均基于 upstream/nightly 或 upstream/main"
---

# SDD Spec: nanobot 上游三个 Bugfix PR

**策略**：先用 3 个小而准的 bugfix PR 建立 maintainer 信任，为后续 multimodal feature PR 铺路。
**例外理由**：`bugfix` + `upstream feature` + `PR prep`（三个 PR 均直接修改 `nanobot/`）

---

## 0. Open Questions

- [ ] PR-A (sanitize_messages) 是否应该只在 non-streaming 路径上做 sanitize，还是 streaming 和 non-streaming 都做？
  - 结论倾向：都做。因为两条路径都可能走到非 Claude provider。
- [ ] PR-B (transcription proxy) 是否应该从 `config.tools.web.proxy` 复用，还是新增 `providers.groq.proxy` 独立字段？
  - 结论倾向：复用 `config.tools.web.proxy`。上游已有此路径，避免引入新配置项。
- [ ] PR-C (send_delta typing fix) 中 `_stop_typing` 的提前调用是否可能在某些 edge case 下导致 typing indicator 闪烁？
  - 结论倾向：不会。因为只在 `_stream_end` 时触发，此时 stream 已完成。

## 1. Requirements (Context)

- **Goal**: 将 ava patches 中发现的三个上游 bug/缺失提交为独立 PR，分别修复：
  - (A) 非 Claude provider 拒绝 trailing assistant messages 和连续同角色消息
  - (B) Groq 语音转文字不支持 proxy（GFW 后用户无法使用）
  - (C) Telegram send_delta 在 tool-call-only 轮次卡住 typing indicator
- **In-Scope**:
  - 三个独立的 focused patch PR
  - 每个 PR 配套最小测试
  - 每个 PR 只改必要的文件
- **Out-of-Scope**:
  - 不引入 ava 特有代码（token_stats, console, memory 等）
  - 不做架构重构
  - 不捆绑提交——三个 PR 互相独立

## 1.1 Context Sources

- Requirement Source:
  - ava 实际运行中发现的 bug，已在 `ava/patches/` 中以 monkey patch 形式修复
- Design Refs:
  - `CONTRIBUTING.md`：bugfix → `main`，behavior change → `nightly`
- Code Refs:
  - `ava/patches/context_patch.py` → `sanitize_messages()` 函数
  - `ava/patches/transcription_patch.py` → proxy 注入逻辑
  - `ava/patches/channel_patch.py` → `patched_send_delta()` 函数
  - `nanobot/providers/base.py` → `_safe_chat` / `_safe_chat_stream`
  - `nanobot/providers/transcription.py` → `GroqTranscriptionProvider.transcribe`
  - `nanobot/channels/telegram.py` → `TelegramChannel.send_delta`

## 1.5 Codemap Used

- Codemap Mode: `targeted-research`
- Key Index:
  - `LLMProvider._safe_chat()` / `_safe_chat_stream()` — 重试 + 降级逻辑入口
  - `GroqTranscriptionProvider.transcribe()` — Groq Whisper 调用
  - `TelegramChannel.send_delta()` — 流式输出增量更新
  - `BaseChannel.transcribe_audio()` — 各 channel 的语音转文字入口
  - `ChannelManager.__init__()` — `transcription_api_key` 注入点

## 2. Research Findings

### PR-A: 非 Claude Provider 消息清洗

**代码事实**：
- `nanobot/providers/base.py` 的 `_safe_chat` 和 `_safe_chat_stream` 直接把 messages 传给底层 API
- OpenAI-compat provider（vLLM、Ollama、DeepSeek 等）会拒绝：
  - 最后一条消息的 role 是 `assistant`（prefill 不支持）
  - 连续两条消息具有相同 role（API 要求严格交替）
- 上游已有 `_strip_image_content()` 做图片降级的先例，可以用类似模式加消息清洗
- ava 的 `sanitize_messages()` 已在生产验证过，逻辑清晰

**目标分支**：`main`（纯 bugfix，不改变行为）

### PR-B: Groq Transcription Proxy 支持

**代码事实**：
- `nanobot/providers/transcription.py` 的 `GroqTranscriptionProvider.transcribe` 使用 `httpx.AsyncClient()` 无 proxy
- `nanobot/channels/base.py` 的 `transcribe_audio()` 构造 provider 时只传 `api_key`
- 上游的 `WebFetchTool` 和 `WebSearchTool` 已经接受 `proxy` 参数
- 修复方案：让 `GroqTranscriptionProvider` 接受 `proxy` 参数，在 `ChannelManager` 初始化时从 `config.tools.web.proxy` 传入

**目标分支**：`nightly`（新增参数，轻微行为变化）

### PR-C: Telegram send_delta Typing Indicator Fix

**代码事实**：
- `TelegramChannel.send_delta` 在 `_stream_end` 时，如果 `buf` 为空或 `buf.message_id` 为 None，不会调用 `_stop_typing`
- 当 agent 轮次只有 tool calls 没有文本输出时，typing indicator 会卡住不消失
- 当 `send_message` 还没返回时（`buf.message_id` 为 None），消息会被丢弃

**目标分支**：`main`（纯 bugfix）

## 3. Innovate (Options & Decision)

### Skip

- Skipped: `true`
- Reason: 三个 PR 都是明确的 bugfix，不存在多方案选择。实现路径唯一：从 ava patch 提炼最小改动。

## 4. Plan (Contract)

---

### PR-A: `fix(providers): sanitize messages for non-Claude providers`

#### 4.1 File Changes

- `nanobot/providers/base.py`
  - 新增 `_sanitize_messages()` 静态方法
  - 在 `_safe_chat()` 和 `_safe_chat_stream()` 入口处调用
- `tests/providers/test_message_sanitize.py`
  - 新增单测：trailing assistant 删除、连续同角色合并、system 消息保留、空列表处理

#### 4.2 Signatures

```python
@staticmethod
def _sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge consecutive same-role messages and drop trailing assistant messages.

    Some providers reject requests where the last message is 'assistant'
    or two consecutive messages share the same role.
    """
```

#### 4.3 Implementation Checklist

- [ ] 1. 从 `ava/patches/context_patch.py` 提取 `sanitize_messages()` 核心逻辑
- [ ] 2. 作为 `LLMProvider._sanitize_messages()` 静态方法添加到 `nanobot/providers/base.py`
- [ ] 3. 在 `_safe_chat()` 和 `_safe_chat_stream()` 的 messages 参数处理中调用
- [ ] 4. 只对非 Anthropic provider 触发（复用已有 provider 类型判断，或检查 `isinstance`）
- [ ] 5. 新增 `tests/providers/test_message_sanitize.py`，覆盖以下场景：
  - 连续 user messages 被合并
  - 连续 assistant messages 被合并
  - trailing assistant message 被删除
  - system message 不受影响
  - 空 messages 列表不报错
  - 已经合规的 messages 不被修改
- [ ] 6. 运行 `ruff check` + `ruff format` + `pytest`
- [ ] 7. 编写 PR 描述

#### 4.4 PR 描述模板

```
## Problem

Non-Claude providers (OpenAI-compat, vLLM, Ollama, DeepSeek, etc.) reject
requests with trailing assistant messages or consecutive same-role messages,
returning HTTP 400.

## Solution

Add `_sanitize_messages()` to `LLMProvider` that:
1. Merges consecutive same-role non-system messages
2. Drops trailing assistant messages

Applied automatically in `_safe_chat` and `_safe_chat_stream` for
non-Anthropic providers.

## Test plan

- [x] Unit tests for merge/drop logic
- [x] Verified with Ollama and DeepSeek endpoints
```

---

### PR-B: `fix(transcription): add proxy support for Groq Whisper`

#### 4.1 File Changes

- `nanobot/providers/transcription.py`
  - `GroqTranscriptionProvider.__init__` 新增 `proxy` 参数
  - `transcribe()` 方法在 `httpx.AsyncClient()` 中传入 proxy
- `nanobot/channels/base.py`
  - `transcribe_audio()` 传递 proxy 给 provider
- `nanobot/channels/manager.py`
  - 初始化 channel 时从 config 读取 proxy 并传递
- `tests/providers/test_transcription_proxy.py`
  - 新增单测：proxy 参数传递验证

#### 4.2 Signatures

```python
class GroqTranscriptionProvider:
    def __init__(self, api_key: str, proxy: str | None = None) -> None:
        ...

    async def transcribe(self, file_path: str | Path) -> str:
        # 使用 httpx.AsyncClient(proxy=self.proxy)
        ...
```

```python
class BaseChannel:
    transcription_api_key: str = ""
    transcription_proxy: str | None = None

    async def transcribe_audio(self, file_path: str | Path) -> str:
        # 传递 self.transcription_proxy 给 provider
        ...
```

#### 4.3 Implementation Checklist

- [ ] 1. 修改 `GroqTranscriptionProvider.__init__` 接受 `proxy` 参数
- [ ] 2. 修改 `transcribe()` 使用 `httpx.AsyncClient(proxy=self.proxy)`
- [ ] 3. 在 `BaseChannel` 新增 `transcription_proxy` 属性
- [ ] 4. 修改 `BaseChannel.transcribe_audio()` 传递 proxy
- [ ] 5. 修改 `ChannelManager.__init__` 从 `config.tools.web.proxy` 读取并赋值
- [ ] 6. 新增测试验证 proxy 参数传递链路
- [ ] 7. 运行 `ruff check` + `ruff format` + `pytest`
- [ ] 8. 编写 PR 描述

#### 4.4 PR 描述模板

```
## Problem

`GroqTranscriptionProvider.transcribe` uses `httpx.AsyncClient()` without
proxy support. Users behind firewalls (e.g. GFW) cannot reach api.groq.com,
making voice transcription non-functional.

## Solution

Add `proxy` parameter to `GroqTranscriptionProvider`, threaded through
`BaseChannel.transcribe_audio()` and `ChannelManager`. Reuses the existing
`config.tools.web.proxy` setting — no new config keys needed.

## Test plan

- [x] Unit test verifying proxy parameter reaches httpx.AsyncClient
- [x] Manual verification behind SOCKS5 proxy
```

---

### PR-C: `fix(telegram): stop typing indicator on tool-call-only turns`

#### 4.1 File Changes

- `nanobot/channels/telegram.py`
  - 修改 `send_delta()`：在 `_stream_end` 时无条件调用 `_stop_typing`
  - 添加 fallback：当 `buf.message_id` 为 None 且 `buf.text` 非空时，发送新消息而不是丢弃
- `tests/channels/test_telegram_send_delta.py`
  - 新增单测

#### 4.2 Signatures

现有方法修改，无新增签名。核心变更在 `send_delta` 方法内部：

```python
async def send_delta(self, chat_id: str, delta: str, metadata: dict | None = None) -> None:
    meta = metadata or {}
    if meta.get("_stream_end"):
        self._stop_typing(chat_id)  # 新增：无条件停止 typing
        # 新增：buf.message_id 为 None 时 fallback 发送
        ...
```

#### 4.3 Implementation Checklist

- [ ] 1. 在 `send_delta` 的 `_stream_end` 分支起始处加入 `self._stop_typing(chat_id)`
- [ ] 2. 添加 fallback 逻辑：当 `buf` 存在且 `buf.text` 非空但 `buf.message_id` 为 None 时，使用 `send_message` 发送完整文本
- [ ] 3. 保持 stream_id 匹配逻辑不变（上游已有）
- [ ] 4. 新增测试（mock `_app.bot.send_message` 和 `_stop_typing`）
- [ ] 5. 运行 `ruff check` + `ruff format` + `pytest`
- [ ] 6. 编写 PR 描述

#### 4.4 PR 描述模板

```
## Problem

When an agent turn contains only tool calls (no text output), the Telegram
typing indicator gets stuck — `_stop_typing` is never called because
`send_delta` only calls it after confirming `buf` has text content.

Additionally, when `send_message` hasn't returned yet (`buf.message_id`
is None) at stream end, the buffered text is silently dropped.

## Solution

1. Call `_stop_typing(chat_id)` unconditionally on `_stream_end`
2. Fallback to `send_message` when `buf.message_id` is None but `buf.text`
   is non-empty

## Test plan

- [x] Unit test: typing stops on tool-call-only turn
- [x] Unit test: message delivered when message_id is None
- [x] Manual test: Telegram bot no longer shows "typing..." indefinitely
```

---

## 4.5 提交顺序建议

| 顺序 | PR | 目标分支 | 难度 | 预计 Review 阻力 |
|------|-----|---------|------|-----------------|
| 1 | PR-A (sanitize_messages) | `main` | 低 | 极低——明确的 bugfix |
| 2 | PR-C (typing fix) | `main` | 低 | 低——Telegram 用户可复现 |
| 3 | PR-B (transcription proxy) | `nightly` | 中 | 低——但涉及跨层参数传递 |

建议按此顺序提交，因为 PR-A 最简单、最不可能有争议，先拿到一个合并记录。

## 4.6 分支策略

```bash
# PR-A
git fetch upstream
git switch -c fix/sanitize-messages-non-claude upstream/main

# PR-B
git switch -c fix/transcription-proxy upstream/nightly

# PR-C
git switch -c fix/telegram-typing-indicator upstream/main
```

## 5. Execute Log

- [ ] 尚未进入 Execute
- [ ] 等待 `Plan Approved` 后开始实施

## 6. Review Verdict

- Spec coverage: `PASS`
- Behavior check: `N/A（尚未实现）`
- Regression risk: `Low（三个 PR 均为 focused bugfix）`
- Follow-ups:
  - PR 全部合并后，可以删除对应的 ava patches（context_patch 的 sanitize 部分、transcription_patch 全部、channel_patch 的 send_delta 部分）
  - 然后以 maintainer 信任为基础，推进 multimodal feature PR

## 7. Plan-Execution Diff

- Any deviation from plan: `None`
- 备注：
  - 三个 PR 提炼自 ava 已验证的 monkey patch 代码，风险极低
  - 提交后 ava 侧对应 patch 可逐步退役，减少维护负担
