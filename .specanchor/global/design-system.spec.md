---
specanchor:
  level: global
  type: design-system
  version: "1.0.0"
  author: "Ziyan Lin"
  reviewers: []
  last_synced: "2026-04-09"
  last_change: "按 console-ui 当前 token、主题和响应式样式重扫设计系统规则"
  applies_to: "**/*.{tsx,ts,css}"
---

# 设计系统规则

## 色值
- 主题 token 统一放在 `console-ui/src/index.css` 的 CSS 变量：`--bg-*`、`--text-*`、`--accent`、`--border`
- 深浅主题切换通过 `:root` / `:root.light` 覆盖变量，不直接在页面组件里复制整套色板

## 字号与布局
- Console UI 以 Tailwind utility class 为主，少量全局样式放在 `index.css`
- 移动端兼容优先使用 `100dvh`、drawer 动画和 `scrollbar-none` 这类基础能力，不在页面内重复造轮子

## 组件样式
- Markdown 展示依赖 `.markdown-body` 统一排版规则
- 需要状态色时复用 `--success` / `--warning` / `--danger`，避免每页自定义告警颜色
