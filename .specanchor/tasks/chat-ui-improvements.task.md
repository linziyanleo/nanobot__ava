---
specanchor:
  level: task
  task_id: "chat-ui-improvements"
  title: "Chat UI 三项改进：复制按钮位置 + 搜索功能 + Markdown 性能优化"
  module: console-ui/ChatPage
  status: ready
  created: "2026-03-24"
  priority: high
---

# Task: Chat UI 三项改进

## 背景

console-ui ChatPage 存在三个待改进点：
1. Session header 的复制按钮位置不直观（复制的是 session id，应紧跟在 session id 旁边）
2. 缺少聊天记录搜索功能（目前只能滚动翻找）
3. 引入 ReactMarkdown + SyntaxHighlighter 后页面变卡（大量消息时渲染性能差）

---

## 改动一：复制按钮挪到 Session ID 右边

### 文件
`console-ui/src/pages/ChatPage/MessageArea.tsx`

### 现状
Session header 布局：
```
左侧：session.key（大字） + token stats（小字）
右侧：Read-only badge | Copy按钮 | Refresh按钮
```
复制按钮在右侧 action 区，视觉上与 session id 割裂。

### 目标布局
```
左侧：session.key（大字）+ [Copy图标，inline，紧跟文字右边] 
      token stats（小字）
右侧：Read-only badge | Refresh按钮 | Search按钮
```

### 实现要点
- 将 Copy 按钮从右侧 action 区移到左侧 `h3` 的行内（`flex items-center gap-1.5`）
- Copy 按钮尺寸缩小到 `w-3 h-3`，保持 hover 高亮
- 复制成功后 1.5s 内显示 Check 图标（现有逻辑不变）
- 右侧 action 区移除 Copy，保留 Read-only badge + Refresh + Search（新增）

---

## 改动二：搜索按钮 + 搜索弹窗

### 文件
- `console-ui/src/pages/ChatPage/MessageArea.tsx`（入口按钮 + 弹窗触发）
- `console-ui/src/pages/ChatPage/SearchModal.tsx`（新建组件）

### 功能描述

#### 入口
- Session header 右侧 action 区新增 Search 按钮（`Search` icon from lucide-react）
- 点击后弹出搜索弹窗（modal overlay）

#### 搜索弹窗（SearchModal）
```
┌─────────────────────────────────────┐
│  🔍 搜索聊天记录              [×]   │
│  ┌─────────────────────────────┐   │
│  │ 输入关键词...               │   │
│  └─────────────────────────────┘   │
│  ─────────────────────────────────  │
│  [结果列表，最多20条]               │
│  ┌─────────────────────────────┐   │
│  │ [role] snippet...  [跳转→]  │   │
│  │ [role] snippet...  [跳转→]  │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

#### 搜索逻辑（纯前端，不需要后端接口）
- 搜索范围：当前 session 的所有 turns（已在 `turns` prop 中）
- 匹配字段：`userMessage.content` + `assistantSteps` 中每条 message 的 content 文本
- 匹配方式：大小写不敏感 substring 匹配
- 结果展示：
  - 显示 role（User / Assistant）
  - 截取匹配关键词前后各 40 字符作为 snippet，高亮关键词
  - 最多显示 20 条结果
  - 每条右侧有「跳转」箭头按钮

#### 跳转逻辑
- 每个 TurnGroup 需要有可定位的 DOM id，格式：`turn-{index}`
- 点击跳转后：关闭弹窗 + `document.getElementById('turn-{index}').scrollIntoView({ behavior: 'smooth', block: 'start' })`
- `TurnGroup.tsx` 中的根元素需加上 `id={`turn-${index}`}`（`MessageArea.tsx` 渲染时传 index）

#### 键盘支持
- 弹窗打开后自动 focus 搜索框
- `Escape` 关闭弹窗
- 搜索框实时搜索（无需按回车，debounce 150ms）

---

## 改动三：Markdown 渲染性能优化

### 文件
`console-ui/src/pages/ChatPage/MessageBubble.tsx`

### 问题根因
- `ReactMarkdown` + `react-syntax-highlighter` 在每次渲染时重新解析整个 markdown 字符串
- 大量消息时，父组件 re-render 触发所有 MessageBubble 重渲染
- `SyntaxHighlighter` 尤其重，每个代码块都是独立的高亮引擎实例

### 优化方案（三层）

#### 层一：MessageBubble 整体 memo
```tsx
export const MessageBubble = React.memo(function MessageBubble(...) {
  ...
}, (prev, next) => {
  // 只在 message.content / tokenStats 变化时重渲染
  return prev.message.content === next.message.content &&
         prev.tokenStats === next.tokenStats
})
```

#### 层二：MarkdownRenderer 独立组件 + useMemo
将 ReactMarkdown 部分抽离为独立组件 `MarkdownRenderer`：
```tsx
const MarkdownRenderer = React.memo(function MarkdownRenderer({ content }: { content: string }) {
  // components 对象用 useMemo 缓存，避免每次渲染重新创建
  const components = useMemo(() => ({
    code({ className, children, ...props }) { ... },
    a({ ... }) { ... },
    table({ ... }) { ... },
    th({ ... }) { ... },
    td({ ... }) { ... },
  }), []) // 空依赖，components 定义不变

  return <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>{content}</ReactMarkdown>
})
```

#### 层三：SyntaxHighlighter 懒加载
- 将 `SyntaxHighlighter` import 改为动态 import + React.lazy：
```tsx
const SyntaxHighlighter = React.lazy(() =>
  import('react-syntax-highlighter').then(m => ({ default: m.Prism }))
)
```
- 外层包 `<Suspense fallback={<pre>...code...</pre>}>`
- 首屏不加载高亮器，代码块首次出现时才异步加载

#### 层四（可选，如仍卡）：虚拟滚动
- 如果消息数量超过 100 条仍有卡顿，可引入 `@tanstack/react-virtual` 对 turns 列表做虚拟滚动
- 本次 **不实现**，作为 fallback 方案备用

### 预期效果
- 大量历史消息时，滚动/输入不再卡顿
- 代码高亮异步加载，不阻塞首屏消息渲染

---

## 文件改动清单

| 文件 | 操作 | 改动内容 |
|------|------|---------|
| `MessageArea.tsx` | 修改 | 复制按钮移位；新增 Search 按钮；弹窗状态管理；TurnGroup 传 index |
| `SearchModal.tsx` | 新建 | 搜索弹窗完整组件 |
| `TurnGroup.tsx` | 修改 | 根元素加 `id={`turn-${index}`}` prop |
| `MessageBubble.tsx` | 修改 | React.memo 包裹；抽离 MarkdownRenderer；SyntaxHighlighter 懒加载 |

---

## Open Questions（已确认无需问主人）

- 搜索不需要后端接口，纯前端 turns 数据即可 ✅
- 虚拟滚动本次不做，三层 memo 优化先上 ✅
- 跳转用 scrollIntoView，不需要路由变更 ✅

---

## 验收标准

1. **复制按钮**：点击 session id 右边的 copy 图标可复制 session key，右侧 action 区无 copy 按钮
2. **搜索**：输入关键词后实时显示匹配结果，点击跳转到对应 turn，Escape 关闭弹窗
3. **性能**：打开有 50+ 条消息的 session，滚动流畅，无明显卡顿
4. **回归**：现有 Copy（消息内容）、Refresh、TokenInfo 功能不受影响
