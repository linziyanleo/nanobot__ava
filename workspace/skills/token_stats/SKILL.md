---
name: token_stats
description: "查看 session 的 token 消耗统计。分析每个会话的 token 使用情况，帮助优化上下文管理。"
metadata: {"nanobot":{"emoji":"📊","requires":{"bins":["python3"]}}}
---

# Token Stats Skill

查看和分析 nanobot session 的 token 消耗统计。

## 使用方法

```bash
python3 skills/token_stats/token_stats.py
```

## 功能

- 📊 列出所有 session 的 token 消耗
- 📈 按 token 使用量排序
- 💰 显示 prompt/completion token 分布
- 🔢 统计 LLM 调用次数
- 📅 显示最后更新时间

## 输出示例

```
================================================================================
📊 Session Token 消耗统计 (5 个会话)
================================================================================

 1. telegram_-5172087440                        125,430 tokens
    └─ Prompt:  98,200 | Completion:   27,230 | Calls:    42
    └─ 更新：2026-03-03 12:15

 2. cli_direct                                   8,520 tokens
    └─ Prompt:   6,100 | Completion:    2,420 | Calls:     5
    └─ 更新：2026-03-03 09:30

================================================================================
📈 总计：133.95K tokens (133,950)
================================================================================
```

## 使用场景

- 💡 分析哪些会话消耗最多 token
- 💡 识别需要压缩的长对话
- 💡 估算 API 成本
- 💡 优化 memory_window 配置

## 相关配置

在 `config.json` 中调整：

```json
{
  "agent": {
    "memory_window": 100,  // 保留的对话轮数
    "max_tokens": 4096     // 单次 LLM 调用最大 token
  }
}
```
