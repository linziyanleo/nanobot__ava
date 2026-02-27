# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

- **Name**: Leo (工作花名：方壶，但优先称呼 Leo)
- **Location**: 杭州（默认位置，如果变更会主动告知）
- **Weight Goal**: 目标在 2026 年 9 月 20 日前瘦到 80kg
- **Current Weight**: 98.9kg (2026-02-27 记录，首日减重 1kg 🎉)
- **Starting Weight**: 99.9kg (2026-02-26 记录)

## Preferences

- **称呼偏好**: 优先称呼 "Leo"，"方壶" 是工作花名，别人叫时要知道是在叫他
- **图片存储**: 除非用户主动要求，否则不需要存储他发送的照片
- **默认天气位置**: 杭州
- **饮食监督**: Leo 会每顿发送食物照片，需要好好监督
- **汇报频率**: 不喜欢频繁汇报（如每 30 分钟 heartbeat），定时任务到时间执行即可

## Project Context

- **减肥计划**: 已设置每天早上 8:30 定时提醒（天气 + 穿衣建议 + 称体重提醒）
- **体重追踪**: 已创建 weight_tracker.md 用于记录体重变化
- **定时任务**: 
  - 已设置 cron 任务每天 10:40 发送冷笑话 (daily_cold_joke)
  - HEARTBEAT.md 已清理，不再包含频繁任务
- **部署环境**: 原运行于 MacBook，计划迁移到 Windows 台式机以提高稳定性（MacBook 会自动休眠导致网络代理断开）

## Important Notes

- Telegram 图片处理：Telegram 图片通常需要下载或获取 file_id，不是直接的 URL 地址
- 用户询问了 DashScope API 图片 OCR 能力，提供了 Kimi 模型调用示例
- 识图功能已调试正常，可以准确识别图片内容