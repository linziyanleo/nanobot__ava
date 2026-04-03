# Global Spec: Sidecar 架构规范

## 核心原则

1. **零侵入上游**：`nanobot/` 目录默认保持纯净，所有 sidecar 定制逻辑在 `ava/` 中实现
2. **Monkey Patch 优先**：能通过运行时 patch 实现的功能，不做 Fork
3. **Fork 作为最后手段**：Fork 文件放入 `ava/forks/`，通过路径覆盖机制生效
4. **最小化拦截点**：patch 只作用于入口/出口（CLI 层、工具执行层、消息总线层）

## 上游集成例外

- 以下场景允许更新 `nanobot/`：
  - 合并 `upstream/main` 时带入的上游变更
  - 为解决 upstream merge conflict 做的最小 reconciliation
  - 明确要回提 upstream 的 bugfix / 通用能力修改
- 这些改动不视为 sidecar 定制；sidecar 定制仍必须落在 `ava/`
- 若提交时 commit guard 因 `nanobot/` staged files 阻挡，可显式使用：

```bash
ALLOW_NANOBOT_PATCH=1 git commit ...
```

- 使用该参数时，提交说明或相关 Task Spec 中必须明确写出“这是 upstream 集成 / upstream 修复例外”，不能把它当作常规放行开关

## 目录结构

```
ava/
├── launcher.py          # 统一入口，依次 apply 所有 patch
├── patches/             # Monkey Patch 模块，文件名 *_patch.py 自动发现
├── forks/               # Fork 覆盖的上游文件（镜像 nanobot/ 结构）
├── tools/               # 自定义工具
├── console/             # Web Console（FastAPI 子应用）
├── storage/             # SQLite 存储层
├── channels/            # 渠道扩展
├── session/             # Session 扩展
├── agent/               # Agent 扩展（记忆、历史压缩等）
├── skills/              # 自定义 Skill 文件
└── templates/           # 自定义模板
```

## Patch 编写规范

- 每个 patch 文件末尾调用 `register_patch(name, apply_fn)`
- `apply_fn` 返回 str 描述做了什么
- patch 内部先保存 `original_xxx`，wrap 后再替换，保持可回滚
- 不在 patch 中做 I/O 初始化（用懒加载）

## Fork 覆盖规范

- Fork 文件路径：`ava/forks/<mirror_of_nanobot_path>`
- 在 `launcher.py` 中通过 `sys.modules` 注入或 `importlib` 覆盖
- Fork 文件顶部注释标注与上游的 diff 摘要，方便合并冲突时参考
