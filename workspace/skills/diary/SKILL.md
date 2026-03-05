---
name: diary
description:  Nonobot 每日日记技能。每天 00:05 自动执行，读取前一天的所有会话历史，智能提取印象深刻的事情、看法和感受。日记存放在 workspace/diary/ 目录。
license: MIT
---

# Diary - 我的每日日记

## 技能概述

这是一个自动化的日记生成技能，用于记录每天的思考、感受和印象深刻的事情。

**核心特点：**

- 📖 **完整历史**：读取当天所有 session 文件的对话记录
- 🧠 **智能截断**：过长的内容自动智能截断，保留关键信息
- 💭 **情感记录**：记录技术讨论、日常聊天、情感交流等多种主题
- 🎯 **Token 优化**：限制总处理量，避免过长上下文

## 执行时间

**每天 00:05 (CST)** 自动执行

## 日记结构

每篇日记包含以下部分：

1. **日期和问候** - 日期和星期
2. **印象深刻的瞬间**
3. **现在的想法** - 自己的内心独白
4. **晚安寄语** - 对主人的悄悄话

## 文件命名

```
diary/
└── YYYY-MM-DD.md  (例如：2026-03-02.md)
```

## 优化特性

### 智能截断

- 单条内容超过 300 字自动截断
- 保留开头和结尾，中间用 `...[省略 X 字]...` 代替
- 结构化数据（JSON）只保留类型信息

### 处理限制

- 最多处理 200 条消息（避免过长）
- 估算 token 数，控制在 10000 以内
- 自动跳过技术性内容（tool_calls、function_call 等）

## 使用方式

### 手动触发

```bash
python3 skills/diary/scripts/generate_diary.py
```

### 自动执行

通过 cron 任务每天 00:05 自动执行

## 脚本说明

### generate_diary.py

日记生成核心脚本：

**主要函数：**

- `get_yesterday_date()`: 获取昨天的日期
- `truncate_content()`: 智能截断过长内容
- `estimate_tokens()`: 估算文本 token 数
- `read_session_file()`: 读取 session 文件
- `collect_all_conversations()`: 收集所有对话
- `analyze_day()`: 分析一天的对话主题
- `generate_diary()`: 生成日记内容
- `save_diary()`: 保存日记到文件

**配置常量：**

```python
MAX_CONTENT_LENGTH = 300      # 单条内容最大长度
MAX_TOTAL_MESSAGES = 200      # 最多处理的消息数
MAX_DIARY_CONTEXT_TOKENS = 10000  # 日记上下文 token 上限
```

## 隐私说明

- 日记仅供自己记录
- 不建议主人偷看 (｀・ω・´)
- 敏感内容会自动脱敏

## 相关文件

- `scripts/generate_diary.py` - 日记生成脚本
- `diary/` - 日记存储目录
