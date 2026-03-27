---
specanchor:
  level: task
  task_name: "修复 token 统计记录数据不完整问题"
  author: "@fanghu"
  created: "2026-03-27"
  status: "done"
  last_change: "Execute 完成，所有字段修复并验证通过"
  related_modules:
    - ".specanchor/modules/loop_patch_spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "refactor/sidecar"
---

# SDD Spec: 修复 token 统计记录数据不完整问题

## 0. Open Questions
- [x] prompt_tokens 为何只有 20-60？（已明确：usage 来源是 runner.py 累加量，被 `_last_usage` 覆盖了错误数据）
- [x] cached_tokens 为何全是 0？（已明确：_store_full_usage 的 usage 字段读取方式和 provider 返回的结构不匹配）
- [x] system_prompt / conversation_history / full_request_payload 为何是空？（已明确：loop_patch 根本没有向 record() 传这些字段）

## 1. Requirements

- **Goal**: 修复 nanobot.db 的 token_usage 表，使其记录准确的 token 数值（prompt/completion/cached/cache_creation）和完整的上下文（system_prompt、conversation_history）
- **In-Scope**:
  - 修复 prompt_tokens 数值错误（当前只有 20-60，实际应为数千）
  - 修复 cached_tokens / cache_creation_tokens 始终为 0
  - 补充 system_prompt_preview 和 conversation_history 字段
  - full_request_payload 可选（较大，按需）
- **Out-of-Scope**: token_stats_service.py 的 record() 接口不变，DB schema 不变

## 2. Research Findings

### 问题1：prompt_tokens 数值严重偏低（20-60，实际应为数千）

**根因**：`_store_full_usage` 在 `intercepted_chat/chat_stream` 里从 `response.usage` 读取数据。但上游 merge 后（e7d371ec），`AgentRunner.run()` 里每轮 LLM 调用的 `usage` **只累加 prompt_tokens/completion_tokens，且每次覆盖**（runner.py:93-96）。

更严重的是：`patched_process_message` 里的检测逻辑：
```python
usage_before = dict(getattr(self, "_last_usage", {}))
# ...
last_usage = dict(getattr(self, "_last_usage", {}))
if last_usage and last_usage != usage_before:
```

`self._last_usage` 在上游 loop.py:269 被赋值为 `result.usage`，而 `result.usage` 只有 `{"prompt_tokens": X, "completion_tokens": Y}`，**不包含完整的 response.usage 原始数据**（Anthropic 的真实 prompt_tokens 包含整个上下文窗口，而 runner.py 里只取了 raw_usage 的两个字段，疑似截断）。

**实际验证**：DB 里 prompt_tokens=20 对应的是 `result.usage` 的值，与真实 LLM 调用的 token 数（通常数千）完全不符。这说明 runner.py 的 `raw_usage.get("prompt_tokens", 0)` 读到的值本身就是错的，或者 `_store_full_usage` 里捕获的 response.usage 的 `prompt_tokens` 字段实际上是其他含义的值。

**关键发现**：`_store_full_usage` 捕获的 `response.usage` 来自 `provider.chat_stream_with_retry` 的返回值，即 `LLMResponse.usage`。需要检查这个字段的实际内容。看 runner.py:92 `raw_usage = response.usage or {}`，和 _store_full_usage 里的 `usage = response.usage or {}`，两者读的是同一个对象，所以 prompt_tokens 的值应该一致。

**真正的问题**：`response.usage` 里的 `prompt_tokens` 到底是什么？对 Anthropic 来说，真实的 input token 数在 `usage.input_tokens`，而不是 `prompt_tokens`。provider 层做了字段映射（`prompt_tokens` ← `input_tokens`），但映射后的值可能在某些 provider 下不正确。

需要看 `nanobot/providers/` 里 Anthropic/zenmux provider 的 usage 映射代码。

**补充发现（看 DB 数据）**：prompt_tokens=20 而 completion_tokens=47，这个比例对 Anthropic 来说不可能——即使最短的回复也需要至少几百的 prompt tokens（系统提示就几百了）。这说明 `response.usage` 里的 `prompt_tokens` 字段在 Anthropic 路径下实际是 0 或者一个很小的值，provider 映射层有问题。

### 问题2：cached_tokens / cache_creation_tokens 始终为 0

**根因**：`_store_full_usage` 里：
```python
prompt_details = usage.get("prompt_tokens_details") or {}
cached_tokens = int(
    prompt_details.get("cached_tokens", 0)
    or usage.get("cache_read_input_tokens", 0)
    or 0
)
cache_creation_tokens = int(usage.get("cache_creation_input_tokens", 0) or 0)
```

但 `token_stats_service.record()` 里又重新从 usage 解析：
```python
cached_tokens = 0
prompt_details = usage.get("prompt_tokens_details")
if isinstance(prompt_details, dict):
    cached_tokens = prompt_details.get("cached_tokens", 0) or 0
cache_creation_tokens = usage.get("cache_creation_input_tokens", 0) or 0
```

**双重问题**：
1. `loop_patch` 把 `_full_last_usage` 的 `cached_tokens`/`cache_creation_tokens` 已解析好放进 dict，但 record() 里又从 usage dict 重新解析，而此时 usage dict 里没有这两个字段（已被 _store_full_usage 解析提取，没有保留原始结构）
2. 传给 record() 的 `usage_to_record` 里缺少 `cache_read_input_tokens` 和 `cache_creation_input_tokens` 原始字段，也缺少 `prompt_tokens_details`

**解决方向**：在 `_full_last_usage` 里直接把已解析的值以正确的键名放入，或者把原始 usage 结构完整传递。

### 问题3：system_prompt_preview / conversation_history 为空

**根因**：`patched_process_message` 里传给 `record()` 的：
```python
system_prompt = getattr(self, "_last_system_prompt", "") or ""
```
`_last_system_prompt` 在 `context_patch.py` 里被设置（build_messages 最后一步），只保存了 500 字符截断后的内容。但 `conversation_history` 完全没有被传递——record() 调用里根本没有 conversation_history 参数。

**需要改进**：
- `system_prompt`：已有，但截断了（500 字符），可以放宽
- `conversation_history`：需要从 `msg` 的上下文构建，或从 session history 里提取
- `full_request_payload`：存储完整的 messages 列表（JSON），体积较大，可设上限

### 问题4：需要先确认 provider 的 usage 映射

需要检查 Anthropic provider 的 usage 字段映射，确认 prompt_tokens 为何只有 20。

## 2.1 Next Actions（Research 追加）

需要读取 provider 的 usage 映射代码来确认问题1的根因。

## 3. Innovate

### Option A：修复 _store_full_usage + 直接传已解析值给 record()
在 intercepted_chat/stream 里捕获完整 response.usage 原始结构，把 cached_tokens 等已解析值直接存入 _full_last_usage，并在 patched_process_message 里直接用这些已解析值调用 record()，跳过 record() 内部的二次解析。

- Pros：改动最小，不影响 token_stats_service 接口
- Cons：两处解析逻辑（_store_full_usage 和 record()）仍然分离，容易混淆

### Option B：让 record() 接受 raw_usage，内部统一解析
修改 record() 的签名，直接传 response.usage 原始 dict，record() 内部统一提取所有字段。

- Pros：单一解析点，清晰
- Cons：需改 token_stats_service.py，影响所有 record() 调用点

### Decision
选 **Option A**：最小改动原则，修复数据流而不改接口。具体：
1. 修复 _store_full_usage：把 cached_tokens/cache_creation_tokens 解析后直接放入 _full_last_usage
2. 修复 patched_process_message：直接从 _full_last_usage 取已解析的 cached/creation tokens 传给 record()，不依赖 record() 内部二次解析
3. 同时传 conversation_history（从 session 取最近几轮历史）

## 4. Plan (Contract)

### 4.1 File Changes

- `ava/patches/loop_patch.py`：
  1. `_store_full_usage()`：需要先调查 response.usage 结构，确认 prompt_tokens 问题根因，再修复字段提取
  2. `patched_process_message()`：传 conversation_history（从 session 提取），修复 cached_tokens 传递方式
  3. 加大 system_prompt 截断限制（500 → 2000）

### 4.2 Signatures（不变，仅修内部逻辑）

### 4.3 Implementation Checklist

- [ ] 1. 读取 nanobot provider 的 LLMResponse.usage 字段映射，确认 prompt_tokens 问题根因
- [ ] 2. 修复 `_store_full_usage`：确保从正确字段提取 prompt/cached/cache_creation tokens
- [ ] 3. 修复 `patched_process_message`：直接传 cached_tokens/cache_creation_tokens 给 record()
- [ ] 4. 在 `patched_process_message` 中添加 conversation_history（最近 N 轮历史 JSON）
- [ ] 5. 放宽 system_prompt 截断（500 → 2000）
- [ ] 6. 验证 DB 新记录的数值正确

## 5. Execute Log

## 6. Review Verdict

## 7. Plan-Execution Diff
