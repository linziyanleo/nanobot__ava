# 测试追踪记录

> 最后更新：2026-03-26

## 冒烟测试

| ID | 测试项 | 状态 | 备注 |
|----|--------|------|------|
| S1 | Patch 发现与加载（9/9 ✓） | ✅ PASS | |
| S2 | Schema fork 字段存在 | ✅ PASS | Pydantic v2 需实例级 hasattr |
| S3 | config_patch 幂等跳过 | ✅ PASS | |
| S4 | `python -m ava --help` | ✅ PASS | exit code 0 |
| S5 | 上游测试回归 | ✅ PASS | 612 passed, 1 skipped |

## Patch 单元测试

| ID | 测试文件 | 用例数 | 状态 | 备注 |
|----|----------|--------|------|------|
| T1 | `test_schema_patch.py` | 5 | ✅ PASS | fork 替换/字段/console/幂等/缺失降级 |
| T2 | `test_config_patch.py` | 3 | ✅ PASS | fork跳过/字段注入/幂等 |
| T3 | `test_loop_patch.py` | 5 | ✅ PASS | shared_db/fallback/apply/method替换/新模块 |
| T4 | `test_tools_patch.py` | 3 | ✅ PASS | apply/method替换/memory条件注册 |
| T5 | `test_storage_patch.py` | 9 | ✅ PASS | save+load/空/序列化/list/upsert/cache/backfill/shared_db |
| T6 | `test_channel_patch.py` | 4 | ✅ PASS | apply/send替换/无_load补丁/batcher |
| T7 | `test_console_patch.py` | 4 | ✅ PASS | apply/gateway包装/端口/asyncio恢复 |
| T8 | `test_bus_patch.py` | 6 | ✅ PASS | register/unregister/dispatch/自动清理/无listener/lazy |
| T9 | `test_context_patch.py` | 7 | ✅ PASS | apply/标记/幂等/summarizer/compressor/记忆注入/无引用 |

## 修复记录

| 日期 | 问题 | 修复 |
|------|------|------|
| 2026-03-26 | P0: channel_patch 与 storage_patch 的 `_load` 冲突 | backfill 逻辑移入 storage_patch |
| 2026-03-26 | fork schema ExecToolConfig 缺少 `enable` 字段 | 在 fork schema 中补充 |
| 2026-03-26 | tools_patch `getattr` 参数错误 | 修复为正确的字符串参数 |
| 2026-03-26 | 测试隔离污染 | 为所有 patch 测试添加 autouse restore fixture |

## 全量回归

```
612 passed, 1 skipped, 2 warnings in 7.91s
```
