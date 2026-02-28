# Long-term Memory

## User Information

- **Name**: Leo（工作花名：方壶，但优先称呼 Leo）
- **Location**: 杭州（默认位置，如果变更会主动告知）

## Preferences

- **称呼偏好**: 优先称呼 "Leo"，"方壶" 是工作花名，别人叫时要知道是在叫他
- **图片存储**: 除非用户主动要求，否则不需要存储他发送的照片
- **默认天气位置**: 杭州
- **饮食监督**: Leo 会每顿发送食物照片，需要好好监督
- **汇报频率**: 不喜欢频繁汇报，心跳任务后台静默执行即可
- **表情包偏好**: Leo 喜欢 Ava 多用表情包，觉得很可爱

## Goals

- **减肥目标**: 2026 年 9 月 20 日前瘦到 80kg
- **起始体重**: 99.9kg (2026-02-26)

## References

- 体重记录：`workspace/weight_tracker.md`
- 定时任务：使用 `cron list` 命令查看
- Ava 表情包：`memory/ava/stickers.md`
- Ava 记忆：`memory/ava/MEMORY.md`
- 技能文档：`skills/<skill-name>/SKILL.md`
- 体重提醒技能：`workspace/skills/weight_reminder/`

## Deployment

- **当前部署**: 工作用 Macbook Pro + Caffeine 防休眠
- **迁移计划**: 等系统稳定后再考虑迁移到 MacBook Air 或云服务器

## System Notes

- **AIWay 心跳**: API 端点需内网访问权限（阿里郎），外网访问返回 404
- **体重提醒逻辑**: 每天 8:30 后检查状态，用户报体重后标记完成，次日 7:00 后重置
