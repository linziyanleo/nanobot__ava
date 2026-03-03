---
name: memory_cleanup
description: "整理 Ava 的记忆系统，去芜存菁。保留重要信息（偏好、身份、项目背景），清理临时信息（时间线条目、过程细节）。"
metadata: {"nanobot":{"emoji":"🧹","requires":{"bins":["python3"]}}}
---

# Memory Cleanup Skill

自动整理记忆系统，保持 MEMORY.md 简洁高效。

## 使用方法

```bash
python3 skills/memory_cleanup/memory_cleanup.py
```

## 整理规则

### ✅ 保留在 MEMORY.md
- 用户偏好（沟通风格、技术偏好等）
- 身份信息（姓名、角色、关系）
- 项目背景（技术栈、架构决策）
- 长期有效的上下文

### 📝 移到 HISTORY.md
- 时间线条目（`[YYYY-MM-DD HH:MM] ...`）
- 临时状态（"进行中"、"testing"）
- 过程细节（debug 记录、临时笔记）

## 执行频率

每天凌晨 3 点自动执行（通过 cron 任务）

## 输出示例

```
🧹 开始整理记忆... (2026-03-03 03:00)
✓ MEMORY.md 整理完成：保留 45 行，移动 12 行时间线条目到 HISTORY.md
✨ 记忆整理完成！
```
