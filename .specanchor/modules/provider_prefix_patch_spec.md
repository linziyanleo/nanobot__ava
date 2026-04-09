# Module Spec: provider_prefix_patch

> 文件：`ava/patches/provider_prefix_patch.py`
> 注册名：`provider_prefix_compat`

## 目标

- 为 sidecar 私有 OpenAI-compatible provider 保留旧模型前缀兼容：
  - `yunwu/...`
  - `zenmux/...`
- 不影响已有 upstream provider spec 的正常路由。

## 拦截点

- `nanobot.providers.openai_compat_provider.OpenAICompatProvider._build_kwargs`

## 行为

- 当 provider 没有 registry spec 时，若模型名带有 `yunwu/` 或 `zenmux/` 前缀，则在真正发请求前剥离前缀。
- 当 provider 已有 upstream spec 时，不改模型名，避免误伤 upstream provider 路径。
- 二次调用 `apply_provider_prefix_patch()` 必须返回 `skipped`。

## 验证

- `tests/patches/test_provider_prefix_patch.py`

