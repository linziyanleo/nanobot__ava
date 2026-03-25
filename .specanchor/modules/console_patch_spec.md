# Module Spec: console_patch — Web Console 注入

> 文件：`cafeext/patches/console_patch.py`
> 状态：✅ 已实现（Phase 1）

---

## 1. 模块职责

将 CafeExt Web Console 子应用挂载到 nanobot Gateway 的 FastAPI 应用上，使用户可以通过 `/console` 路径访问 Web 管理界面。

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `nanobot.cli.commands._create_gateway_app` | 函数替换 | 在 Gateway app 创建后挂载 Console 子应用 |

### 拦截详情

- **原始行为**：`_create_gateway_app(*args, **kwargs)` 创建并返回 FastAPI 应用实例
- **修改后行为**：调用原始工厂函数创建 app → 创建 Console 子应用 → 挂载到 `/console` 路径 → 返回增强后的 app
- **挂载路径**：`/console`
- **挂载名称**：`"console"`

---

## 3. 依赖关系

### 上游依赖
- `nanobot.cli.commands` — 模块级拦截目标
- `nanobot.cli.commands._create_gateway_app` — 具体拦截的工厂函数

### Sidecar 内部依赖
- `cafeext.console.app.create_console_app` — Console 子应用工厂
- `cafeext.launcher.register_patch` — 自注册机制（别名 `_register`）

---

## 4. 关键实现细节

### 4.1 优雅降级
- 若 `_create_gateway_app` 不存在于 `cli.commands` 模块中，patch 跳过并输出 warning
- 返回描述性字符串说明 patch 被跳过
- Console 仍可通过 `cafeext.console.app` 手动挂载

### 4.2 Console 挂载失败处理
- `create_console_app()` 执行失败时捕获异常并 log error
- Gateway app 仍然正常返回（不阻塞主应用启动）

### 4.3 运行时特点
- 此 patch 不同于其他 patch：它是在 CLI 命令执行阶段生效（创建 Gateway app 时），而非在模块导入阶段
- Patch 的实际效果延迟到 `gateway` 命令执行时

---

## 5. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 正常挂载 | Console 子应用成功挂载到 `/console` |
| Gateway 工厂不存在 | `_create_gateway_app` 缺失时优雅跳过 |
| Console 创建失败 | `create_console_app()` 异常时不影响 Gateway 启动 |
| 路由正确 | 挂载后 `/console` 路径可访问 |
| 原始 app 完整 | 挂载 Console 不影响原有 API 路由 |
| 幂等性 | 多次调用不会重复挂载 |
