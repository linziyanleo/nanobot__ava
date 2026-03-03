# Weight Reminder Skill

体重提醒状态管理工具

## 功能

- ✅ 检查今日体重提醒状态
- ✅ 自动重置提醒状态（每天 8:30 后）
- ✅ 不主动发送提醒（避免打扰）
- ✅ 状态持久化存储

## 文件结构

```
skills/weight_reminder/
├── SKILL.md           # 技能文档
├── check_reminder.py  # 检查状态脚本
├── reset_reminder.py  # 重置状态脚本
├── state.json         # 状态存储
└── README.md          # 使用说明
```

## 使用方法

### 检查状态

```bash
cd skills/weight_reminder
python check_reminder.py
```

**输出示例**:
```
当前时间：10:43
📊 体重提醒状态：ACTIVE
📝 待提醒
⏳ 待提醒状态，等待用户报体重
```

### 重置状态

```bash
cd skills/weight_reminder
python reset_reminder.py
```

**输出示例**:
```
📅 今天日期：2026-02-28
📝 上次重置：2026-02-27
✅ 已将体重提醒重置为 Active 状态
📊 状态文件已更新
```

## 与 HEARTBEAT.md 集成

在 `HEARTBEAT.md` 中添加：

```markdown
### 体重提醒（每天）

1. 8:30 后执行 `skills/weight_reminder/check_reminder.py` 检查状态
2. 如果状态是 "active"，等待用户主动报体重
3. 用户报体重后，将此任务移到 Completed
4. 第二天 8:30 后执行 `skills/weight_reminder/reset_reminder.py` 重置

- [ ] 检查用户是否已报今日体重（8:30 后）
```

## 状态说明

| 状态 | 含义 | 操作 |
|------|------|------|
| ACTIVE | 待提醒 | 等待用户报体重 |
| COMPLETED | 已完成 | 等待明日重置 |
| UNKNOWN | 未知 | 检查配置 |

## 注意事项

- ⚠️ 不主动发送提醒消息（Leo 不喜欢频繁汇报）
- ⚠️ 只在用户主动询问时报告状态
- ⚠️ 状态变更记录到 HISTORY.md
