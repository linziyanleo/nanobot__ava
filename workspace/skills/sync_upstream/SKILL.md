# Skill: sync_upstream

## Purpose

同步上游 nanobot 仓库的更新到本地。每天 10:30 由 cron 定时任务自动触发。

## 重要约定

**执行前必须检查工作树状态！**

如果有未提交的修改，**必须向主人确认**如何处理：
- `commit` - 提交修改后再同步
- `stash` - 暂存修改后再同步
- `discard` - 丢弃修改后再同步
- `skip` - 跳过本次同步

**绝对禁止**：自动决定或清空工作树

## 使用方法

```bash
# 手动执行同步
bash sync-upstream.sh
```

## Cron 任务配置

| 任务名称 | Cron 表达式 | 执行时间 |
|---------|------------|---------|
| `sync-upstream` | `30 10 * * *` | 每天 10:30 |

## 流程文档

详细流程见：`workspace/docs/sync_upstream_procedure.md`
