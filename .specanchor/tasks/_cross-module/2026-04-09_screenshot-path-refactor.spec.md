---
specanchor:
  level: task
  task_name: "截图保存路径重构与迁移"
  author: "@Ziyan Lin"
  assignee: "@Ziyan Lin"
  reviewer: "@Ziyan Lin"
  created: "2026-04-09"
  status: "in_progress"
  last_change: "Execute 完成：page_agent 默认截图目录已切到 media/screenshots，MediaService 已接管多目录查找/迁移/symlink 兼容，并通过定向验证"
  related_modules:
    - ".specanchor/modules/ava-tools-page_agent.spec.md"
    - ".specanchor/modules/console-ui-src-pages-BrowserPage.spec.md"
  related_global:
    - ".specanchor/global/architecture.spec.md"
    - ".specanchor/global/coding-standards.spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "REVIEW"
  branch: "codex/upstream-v0.1.5-merge-analysis"
---

# SDD Spec: 截图保存路径重构与迁移

## 0. Open Questions

- [x] 截图文件与模型生成图片在上游代码中是同一个保存入口还是不同入口？→ **不同入口**，截图走 `PageAgentTool._do_screenshot()`，生成图片走 `ImageGenTool._save_image()`，但默认保存到同一目录
- [x] console-ui 中引用截图的路径是通过 API 获取还是拼接固定路径？→ **通过 API**，前端 `imageUrl()` 仅提取文件名，请求 `/api/media/images/{filename}`，后端 `MediaService.get_image_path()` 查找文件
- [x] 迁移后是否需要保持向后兼容（旧路径 fallback）？→ **需要**。`VisionTool._resolve_image_url()` 和 `ImageGenTool` 的 `reference_image` 参数会直接 `Path(path).is_file()` 检查绝对路径。迁移策略改为 **move + symlink**：移动文件后在旧位置留 symlink，确保旧绝对路径仍可访问

## 1. Requirements (Context)

- **Goal**: 将截图文件从 `/Users/fanghu/.nanobot/media/generated` 迁移到独立子目录，使截图和模型生成图片不再混杂；同步更新后端保存链路和 console-ui 前端引用路径
- **In-Scope**:
  - 分析当前截图保存链路（后端工具 → 文件系统 → console-ui 展示）
  - 确定新的截图保存目录结构
  - 修改截图保存代码，输出到新路径
  - 迁移现有截图文件到新目录
  - 更新 console-ui 中截图引用路径
- **Out-of-Scope**:
  - 模型生成图片的路径重构（保持原位）
  - 上游 nanobot/ 代码修改（除非截图保存链路涉及上游）

## 1.1 Context Sources

- Requirement Source: 用户需求——截图和生成图片混杂在同一目录
- Design Refs: `.specanchor/global/architecture.spec.md`
- Chat/Business Refs: N/A
- Extra Context: 当前截图功能由 `ava/tools/` 下的 vision/page_agent 相关工具实现

## 1.5 Codemap Used (Feature/Project Index)

- Codemap Mode: `feature`
- Key Index:
  - Entry Points: `PageAgentTool._do_screenshot()` (ava/tools/page_agent.py:517)
  - Core Logic: `_get_screenshot_dir()` (ava/tools/page_agent.py:1001)、`ImageGenTool._save_image()` (ava/tools/image_gen.py:108)
  - Dependencies: `MediaService.get_image_path()` (ava/console/services/media_service.py:135)、`imageUrl()` (console-ui/src/pages/ChatPage/utils.ts)

## 2. Research Findings

### 2.1 截图保存链路（PageAgent）

- **调用链**: `PageAgentTool.execute(action="screenshot")` → `_do_screenshot()` → `_get_screenshot_dir()` 获取目录 → RPC 发送给 `page-agent-runner.mjs` → Playwright `page.screenshot()` → `fs.writeFileSync(savePath, buffer)`
- **路径决策**: `_get_screenshot_dir()` 先检查 `PageAgentConfig.screenshot_dir`（配置字段，定义在 `ava/forks/config/schema.py:555`），为空则回退到 `Path.home() / ".nanobot" / "media" / "generated"`
- **文件命名**: `page-agent-{YYYYMMDD-HHMMSS}-{session_id[:8]}.png`
- **元数据记录**: `model="page-agent"`, `id="page-agent-{ts}"`, 写入 `MediaService.write_record()`

### 2.2 模型生成图片链路（ImageGen）

- **调用链**: `ImageGenTool.execute()` → Google Gemini API → `_save_image()` → 写入 `GENERATED_DIR`
- **路径决策**: 硬编码 `GENERATED_DIR = Path.home() / ".nanobot" / "media" / "generated"` (image_gen.py:13)
- **文件命名**: `{uuid_hex[:12]}_{index}.png`
- **不支持配置化**

### 2.3 前端展示链路

- **imageUrl()**: `path.split('/').pop()` 提取文件名 → `/api/media/images/{filename}` — **前端只依赖文件名，不依赖绝对路径**
- **后端文件服务**: `GET /api/media/images/{filename}` → `MediaService.get_image_path(filename)` → 在 `_media_dir` 中查找文件 → `FileResponse`
- **MediaService._media_dir**: 构造函数参数，默认 `~/.nanobot/media/generated`
- **BrowserPage 实时预览**: 不涉及文件路径（WebSocket 推送 base64 帧）

### 2.4 关键代码文件

| 文件 | 角色 | 关键行 |
|------|------|--------|
| `ava/tools/page_agent.py` | 截图保存入口 | :517-596 (_do_screenshot), :1001-1006 (_get_screenshot_dir) |
| `ava/tools/image_gen.py` | 生成图片保存 | :13 (GENERATED_DIR), :108-113 (_save_image) |
| `ava/console/services/media_service.py` | 文件查找与记录 | :13-14 (_media_dir), :135-141 (get_image_path) |
| `ava/console/routes/media_routes.py` | HTTP 文件服务 | :31-44 |
| `ava/forks/config/schema.py` | screenshot_dir 配置字段 | :555-559 |
| `console-ui/src/pages/ChatPage/utils.ts` | 前端 imageUrl() | 提取文件名 |
| `console-ui/e2e/page-agent-runner.mjs` | Node 端截图写入 | :659-662 |

### 2.5 风险与约束

- 截图和生成图片的文件名前缀不同（`page-agent-*` vs `uuid_*`），迁移时可通过前缀区分
- `MediaService.get_image_path()` 当前只查单个目录，拆分后需支持多子目录查找
- 已有的 `output_images` 数据库/JSONL 记录存的是文件名（不含路径），拆分目录后需要让 `get_image_path()` 能从两个子目录中找到文件
- `delete_record()` 也依赖 `_media_dir` 来定位文件删除，需同步更新
- **[Codex P2]** `VisionTool._resolve_image_url()` (vision.py:56-70) 和 `ImageGenTool.execute()` 的 `reference_image` 参数都直接 `Path(path).is_file()` 检查绝对路径。如果 LLM 在同一对话中先截图、再用截图路径调用 vision/image_gen，迁移后旧绝对路径会 404。**解决方案**：迁移时在旧位置创建 symlink 指向新位置，确保旧绝对路径仍可访问

## 2.6 Next Actions

- 确定新目录结构方案
- 编写 Plan

## 3. Innovate (Options & Decision)

### Option A：子目录拆分（推荐）

新目录结构：

```
~/.nanobot/media/
├── generated/          ← 模型生成图片（保持不变）
│   ├── {uuid}_{idx}.png
│   └── records.jsonl   ← JSONL 后备（如果还在用）
└── screenshots/        ← 截图独立目录（新增）
    └── page-agent-{ts}-{sid}.png
```

- Pros: 物理隔离清晰；对 image_gen 零改动；截图工具只需改默认路径
- Pros: `MediaService.get_image_path()` 改为多目录查找，前端完全不用改（只依赖文件名）
- Cons: `delete_record()` 也需要多目录查找

### Option B：在 generated/ 下建子目录

```
~/.nanobot/media/generated/
├── images/             ← 模型生成图片
└── screenshots/        ← 截图
```

- Pros: 保持在 generated/ 下，改动范围更小
- Cons: 需要同时改 image_gen 和 page_agent 的路径；records.jsonl 放哪里不好决定

### Decision

- Selected: **Option A**
- Why: 对 image_gen 零侵入；截图路径已有配置化支持（`screenshot_dir`），只需设置默认值；前端无需修改（`imageUrl()` 只提取文件名，`/api/media/images/{filename}` 由后端多目录查找解决）

## 4. Plan (Contract)

### 4.1 File Changes

| 文件 | 变更说明 |
|------|---------|
| `ava/tools/page_agent.py` | `_get_screenshot_dir()` 默认路径从 `media/generated` 改为 `media/screenshots` |
| `ava/console/services/media_service.py` | `get_image_path()` 支持多目录查找（`_media_dir` + `_screenshot_dir`）；`delete_record()` 同步更新；构造函数新增 `screenshot_dir` 参数 |
| `ava/console/routes/media_routes.py` | 无需修改（透传 `get_image_path()` 结果） |
| `console-ui/**` | **无需修改**（前端只依赖文件名，通过 `/api/media/images/{filename}` 获取，后端负责多目录查找） |
| 迁移脚本（一次性） | 将 `~/.nanobot/media/generated/page-agent-*.png` 移动到 `~/.nanobot/media/screenshots/`，并在旧位置创建 symlink 指向新位置（兼容 VisionTool/ImageGenTool 的绝对路径引用） |

### 4.2 Signatures

```python
# ava/tools/page_agent.py
def _get_screenshot_dir(self) -> Path:
    # 默认值改为 Path.home() / ".nanobot" / "media" / "screenshots"

# ava/console/services/media_service.py
class MediaService:
    def __init__(self, media_dir: Path | None = None, screenshot_dir: Path | None = None, db: Any | None = None):
        # 新增 _screenshot_dir 属性

    def get_image_path(self, filename: str) -> Path | None:
        # 先查 _media_dir，再查 _screenshot_dir

    def delete_record(self, record_id: str) -> bool:
        # 文件删除时检查两个目录
```

### 4.3 Implementation Checklist

- [x] 1. 修改 `page_agent.py` 的 `_get_screenshot_dir()` 默认路径为 `~/.nanobot/media/screenshots`
- [x] 2. 修改 `MediaService.__init__()` 新增 `screenshot_dir` 参数，默认 `~/.nanobot/media/screenshots`
- [x] 3. 修改 `MediaService.get_image_path()` 支持多目录查找
- [x] 4. 修改 `MediaService.delete_record()` 支持多目录查找文件删除
- [x] 5. 更新 `MediaService` 的实例化点，传入 `screenshot_dir`（如有必要）
- [x] 6. 执行迁移：将 `~/.nanobot/media/generated/page-agent-*.png` 移动到 `~/.nanobot/media/screenshots/`，并在旧位置创建 symlink 指向新文件（兼容绝对路径引用）
- [x] 7. 验证：确认 console-ui 中截图和生成图片都能正常展示；确认旧绝对路径通过 symlink 仍可访问

## 5. Execute Log

- [x] 2026-04-10：将 `ava/tools/page_agent.py` 的默认截图目录从 `media/generated` 切到 `media/screenshots`，保留 `config.tools.page_agent.screenshot_dir` 自定义优先级不变。
- [x] 2026-04-10：补完 `ava/console/services/media_service.py`，让 `get_image_path()` / `delete_record()` 同时覆盖 `generated` 与 `screenshots` 两个目录，并新增基于文件名前缀的 legacy screenshot 迁移逻辑。
- [x] 2026-04-10：迁移策略落到 `MediaService` 初始化阶段自动执行：检测 `generated/page-agent-*.png` 后移动到 `screenshots/`，并在旧位置留下 symlink，兼容 `vision` / `image_gen` 继续读取旧绝对路径。
- [x] 2026-04-10：补齐 `MediaService` 的装配点，确保 console mock runtime 与 `loop_patch` 初始化出的 `self.media_service` 都显式使用 sibling `screenshots` 目录。
- [x] 2026-04-10：新增 `tests/console/test_media_service.py`，覆盖 sibling screenshot_dir 推导、多目录查找、legacy migration 与 delete_record 删除 symlink/目标文件。
- [x] 2026-04-10：更新 `tests/tools/test_page_agent.py`，锁定 page_agent 默认截图目录并修正现有 `screenshot` 参数合同断言（`session_id` 或 `url` 至少一者存在）。
- [x] 2026-04-10：定向验证通过：`pytest tests/console/test_media_service.py tests/tools/test_page_agent.py tests/console/test_mock_tester_pages.py tests/patches/test_loop_patch.py -q` => `47 passed`；`git diff --check` => clean。

## 6. Review Verdict

- Spec coverage: PASS
- Behavior check: PASS
- Regression risk: Low
- Follow-ups:
  - 当前迁移是在 `MediaService` 初始化时惰性触发的；如果后续希望在安装/升级阶段提前完成磁盘整理，可以再单独抽出 CLI 迁移命令，但这不影响现有运行时兼容性。
  - 前端仍保持“只传文件名、后端解析目录”的合同；若未来媒体目录继续细分，优先继续扩展 `MediaService`，不要把路径拼接逻辑推回 `console-ui`。

## 7. Plan-Execution Diff

- 计划里把迁移写成“一次性脚本”；实际实现改成 `MediaService` 初始化时自动迁移。这么做的原因是能在不引入额外运维步骤的前提下保证旧截图绝对路径立即兼容，并天然覆盖 DB/JSONL 两种运行模式。
- 计划里把“更新实例化点”标成“如有必要”；实际执行中明确更新了 `ava/console/app.py` 的 mock runtime 装配和 `ava/patches/loop_patch.py` 的 `MediaService` 初始化，避免测试/运行时因 custom media_dir 继续回落到 `~/.nanobot/media/screenshots`。
