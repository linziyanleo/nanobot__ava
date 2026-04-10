---
specanchor:
  level: module
  module_name: "转写代理 Patch"
  module_path: "ava/patches/transcription_patch.py"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-04-01"
  updated: "2026-04-10"
  last_synced: "2026-04-10"
  last_change: "扩展 gemini/zenmux 多模态转译链路，并保留 Groq proxy 注入"
  status: "active"
  depends_on:
    - "ava/launcher.py"
---

# 转写代理 Patch (transcription_patch)

## 1. 模块职责
- 代理配置读取顺序：
- ~/.nanobot/config.json
- ~/.nanobot/extra_config.json
- 为 Groq Whisper 请求注入 `tools.web.proxy`
- 为 `channels.transcriptionProvider=gemini/zenmux` 提供 ZenMux Vertex 多模态转译

## 2. 业务规则
- 未配置 proxy 时直接 skip，不影响原系统启动
- transcribe 方法缺失时直接 skip，并记录 warning
- 文件不存在、API key 缺失、HTTP 请求失败时返回空字符串，不向上抛未捕获异常
- patch 二次应用时必须返回 skipped
- `zenmux` 优先读取 `providers.zenmux`；缺失时回退到 `providers.gemini + apiBase=https://zenmux.ai/api/vertex-ai/v1`

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `apply_transcription_patch()` | `apply_transcription_patch() -> str` | Patch Groq transcription proxy and gemini/zenmux multimodal transcription routing. |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| 运行时状态 | — | 当前模块以局部变量和调用方注入对象为主 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.providers.transcription.GroqTranscriptionProvider
- nanobot.channels.manager.ChannelManager
- nanobot.channels.base.BaseChannel
- 本地 ~/.nanobot/config.json / extra_config.json
- httpx.AsyncClient(proxy=...)
- ZenMux Vertex `generateContent`

## 5. 已知约束 & 技术债
- [ ] 未配置 proxy 时直接 skip，不影响原系统启动
- [ ] transcribe 方法缺失时直接 skip，并记录 warning
- [ ] 文件不存在、API key 缺失、HTTP 请求失败时返回空字符串，不向上抛未捕获异常

## 6. TODO
- [ ] 代码行为变化后同步更新接口表、关键文件表和 module-index @ZiyanLin
- [ ] 如上游新增同类能力，重新评估 keep / narrow / delete / upstream 的 patch 策略 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/patches/transcription_patch.py`
- **核心链路**: `transcription_patch.py` → 上游拦截点 → sidecar 补丁逻辑 → 原始运行时输出
- **数据流**: 触发 patch 注册 → 校验目标存在 → 包装/替换目标方法 → 返回 launcher/调用方可见结果
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/patches/transcription_patch.py` | 模块主入口 |
- **外部依赖**: `ava/launcher.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-patches-transcription_patch.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
