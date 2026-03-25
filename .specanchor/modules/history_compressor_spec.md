# Module Spec: history_compressor — 历史压缩器（Phase 2.2）

> 状态：🔶 待迁移
> 优先级：Phase 2.2
> 预估工时：1h

---

## 1. 模块职责

基于字符预算的历史消息压缩算法。在上下文窗口有限的情况下，智能选择保留哪些历史消息，确保最近的对话和高相关性内容优先保留。

### 核心能力
- **字符预算控制**：根据配置的字符预算裁剪历史消息
- **最近轮次保留**：最近 N 轮对话始终保留
- **相关性筛选**：基于轻量级关键词匹配进行相关性评分
- **auto-backfill 识别**：识别并标记自动回填的消息
- **术语提取**：支持英文 + 中日韩（CJK）术语提取

---

## 2. 源文件位置

| 类型 | 路径 |
|------|------|
| 源码（feat/0.0.1） | `nanobot/agent/history_compressor.py`（+205 行，纯新增） |
| 计划实现位置 | `cafeext/agent/history_compressor.py` |
| Patch 文件 | `cafeext/patches/history_patch.py`（新建，可与 history_summarizer 合并） |

---

## 3. 拦截点设计

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `AgentLoop._build_messages` | 方法包装 | 在构建消息列表时插入压缩逻辑 |

### 拦截逻辑

1. 原始 `_build_messages` 返回完整消息列表
2. 包装函数将消息列表传入 `HistoryCompressor.compress()`
3. 返回压缩后的消息列表

---

## 4. 接口设计

```python
class HistoryCompressor:
    """基于字符预算的历史消息压缩器"""

    def __init__(
        self,
        char_budget: int = 100_000,
        recent_turns: int = 5,
        relevance_threshold: float = 0.3,
    ):
        ...

    def compress(
        self,
        messages: list[dict],
        current_query: str | None = None,
    ) -> list[dict]:
        """压缩消息列表，返回裁剪后的消息"""
        ...

    def extract_terms(self, text: str) -> set[str]:
        """从文本中提取关键术语（支持英文 + CJK）"""
        ...

    def score_relevance(
        self,
        message: dict,
        query_terms: set[str],
    ) -> float:
        """计算消息与当前查询的相关性评分"""
        ...
```

---

## 5. 依赖关系

### 上游依赖
- `nanobot.agent.loop.AgentLoop._build_messages` — 拦截目标

### Sidecar 内部依赖
- 无（纯工具类，无其他 Sidecar 依赖）

### 外部依赖
- 标准库 `re` — 正则表达式用于术语提取

---

## 6. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 预算内不压缩 | 消息总量在预算内时原样返回 |
| 超预算压缩 | 正确裁剪到字符预算范围内 |
| 最近轮次保留 | 最近 N 轮始终保留 |
| 相关性排序 | 高相关性消息优先保留 |
| CJK 术语提取 | 中日韩文本正确提取术语 |
| auto-backfill 标记 | 自动回填消息被正确识别 |
| 空消息列表 | 空列表不报错 |
