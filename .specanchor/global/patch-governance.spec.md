---
specanchor:
  level: global
  type: patch-governance
  version: "1.0.0"
  author: "Ziyan Lin"
  reviewers: []
  last_synced: "2026-04-09"
  last_change: "提炼旧版 global-patch-spec 为新的可加载 Global Spec"
  applies_to: "ava/patches/**/*.py,ava/forks/**/*.py,nanobot/**/*.py"
---

# Patch 治理规则

## 核心原则
- 默认禁止修改 `nanobot/`；唯一例外是 upstream merge、upstream bugfix / 通用能力、或明确为上游 PR 做准备
- patch 只打入口 / 出口层，不深入绑定上游中间业务分支
- 每个 patch 必须可独立禁用、可重复调用且不产生重复注册副作用

## 文件规范
- 文件名固定 `ava/patches/{module}_patch.py`，末尾必须 `register_patch(...)` 自注册
- patch 函数返回人类可读描述，并保存原始方法引用以便回滚
- fork 文件只放 `ava/forks/`，用于 patch 不足以覆盖的最小替换

## 安全与验证
- 拦截点不存在时必须 warning + skip，禁止 `except: pass`
- 修改 `ava/patches/*` 或合并 `upstream/main` 前先核对 `.specanchor/patch_map.md`
- 对应验证优先落在 `tests/patches/test_*.py`，覆盖 patch 前后行为、缺失拦截点和幂等性
