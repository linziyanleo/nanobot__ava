# Module Spec: transcription_patch — Groq 转写代理注入

> 文件：`ava/patches/transcription_patch.py`
> 状态：✅ 已实现
> 执行顺序：字母序第 11 位（最后执行）

---

## 1. 模块职责

为 `GroqTranscriptionProvider.transcribe` 注入代理能力，解决直连 `api.groq.com`
在受限网络环境下超时或 403 的问题。

代理配置读取顺序：

1. `~/.nanobot/config.json`
2. `~/.nanobot/extra_config.json`

字段路径统一为 `tools.web.proxy`。

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `GroqTranscriptionProvider.transcribe` | 方法替换 | 使用带 proxy 的 `httpx.AsyncClient` 发起转写请求 |

---

## 3. 关键行为

- 未配置 proxy 时直接 skip，不影响原系统启动
- `transcribe` 方法缺失时直接 skip，并记录 warning
- 文件不存在、API key 缺失、HTTP 请求失败时返回空字符串，不向上抛未捕获异常
- patch 二次应用时必须返回 skipped

---

## 4. 依赖关系

### 上游依赖
- `nanobot.providers.transcription.GroqTranscriptionProvider`

### Sidecar 内部依赖
- 本地 `~/.nanobot/config.json` / `extra_config.json`
- `httpx.AsyncClient(proxy=...)`

---

## 5. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 无代理配置 | 返回 skip 描述，不修改方法 |
| 正常注入 | patch 后带 `_ava_transcription_patched` 标记 |
| 幂等性 | 二次 apply 返回 skipped |
| 拦截点缺失 | 缺少 `transcribe` 时优雅跳过 |
| 代理来源 | `config.json` / `extra_config.json` 都可提供 proxy |
