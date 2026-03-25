# Global Patch Spec — Sidecar Monkey Patch 规范

> 本规范适用于 `cafeext/patches/` 目录下所有 Monkey Patch 模块。
> 所有开发者在编写、审查或维护 patch 时必须遵守本规范。

---

## 1. 核心原则

### 1.1 零上游污染原则
- **绝对禁止**修改 `nanobot/` 目录下的任何文件
- 所有定制逻辑必须放在 `cafeext/` 目录中
- Patch 通过 Python 运行时动态替换实现，不改变磁盘上的上游源码

### 1.2 最小化拦截原则
- 只在系统的「入口」和「出口」位置打 patch：
  - **CLI 层**：命令启动、参数注入（如 `cli.commands._create_gateway_app`）
  - **工具执行层**：工具注册、工具执行（如 `AgentLoop._register_default_tools`）
  - **消息总线层**：消息发送、session 加载（如 `TelegramChannel._send_message`、`SessionManager._load`）
  - **存储层**：数据持久化接口（如 `SessionManager.save`、`SessionManager._load`）
- **不深入**中间业务逻辑（如 `AgentLoop._process_turn` 的内部分支）

### 1.3 可撤销原则
- 每个 patch 必须可以独立禁用
- 禁用方式：在 `cafeext/patches/` 中删除或重命名对应的 `*_patch.py` 文件
- 禁用后系统回退到上游默认行为，不产生错误
- Patch 函数必须保存原始方法的引用（如 `original_xxx = Class.method`），以便运行时回滚

### 1.4 幂等原则
- `apply_*_patch()` 可以被多次调用，不产生副作用
- 不能多次注册同一个工具或多次包装同一个方法
- 推荐在 patch 内部使用标记位（如 `_patched = True`）防止重复应用

### 1.5 不影响 merge 原则
- 上游 `git pull` 后，patch 必须仍然可以正常工作
- 若上游重构导致拦截点消失，patch 必须**优雅降级**（打印警告，跳过 patch），不能抛出未捕获异常
- 禁止依赖上游代码的内部实现细节（如私有变量 `_internal_state`），只依赖公开接口或稳定的受保护方法

---

## 2. Patch 文件规范

### 2.1 文件命名
```
cafeext/patches/{module_name}_patch.py
```
- `module_name` 对应被 patch 的上游模块或功能域
- 示例：`tools_patch.py`、`channel_patch.py`、`console_patch.py`、`storage_patch.py`

### 2.2 模块级文档字符串
每个 patch 文件**必须**以文档字符串开头，说明：
- patch 的目的
- 拦截的上游模块/类
- 修改后的行为概述

```python
"""Monkey patch to inject CafeExt custom tools into AgentLoop.

拦截点: AgentLoop._register_default_tools
修改行为: 在上游默认工具注册完成后，追加注册 5 个自定义工具
"""
```

### 2.3 Patch 函数命名
```python
def apply_{module_name}_patch() -> str:
    """Apply the {description} patch.

    Returns:
        str: 人类可读的 patch 描述
    """
```

### 2.4 自注册模式
每个 patch 文件必须在模块末尾通过 `register_patch()` 自注册：

```python
from cafeext.launcher import register_patch
register_patch("{patch_name}", apply_{module_name}_patch)
```

### 2.5 代码注释要求
每个 patch 函数内部**必须**注释说明：
- **拦截点**：被替换的类名.方法名
- **原始行为**：上游该方法的原始功能
- **修改后行为**：patch 后的新功能

---

## 3. Patch 注册与执行

### 3.1 注册中心
所有 patch 在 `cafeext/launcher.py` 的 `apply_all_patches()` 中统一发现和执行。

### 3.2 执行顺序
Patch 按文件名字母序发现，但逻辑上遵循依赖顺序：

```
storage → tools → channels → console
```

- `storage_patch` 最先执行：后续 patch 可能依赖 SQLite 存储
- `console_patch` 最后执行：依赖 Gateway app 已创建

### 3.3 失败处理
- 单个 patch 失败不影响其他 patch 的执行
- 失败的 patch 会打印 `✗` 标记和错误信息
- 系统继续以部分 patch 状态运行

---

## 4. Patch 安全检查规范

### 4.1 拦截点存在性检查
每个 patch 在应用前**必须**检查拦截点是否存在：

```python
def apply_xxx_patch() -> str:
    from nanobot.some.module import SomeClass

    if not hasattr(SomeClass, 'target_method'):
        logger.warning(
            "Patch skipped: SomeClass.target_method not found — "
            "upstream may have been refactored"
        )
        return "Patch skipped (target method not found)"

    # ... apply patch
```

### 4.2 禁止静默失败
- 检查失败时**必须**通过 `loguru.logger.warning()` 输出警告
- 返回描述性字符串说明 patch 被跳过的原因
- **绝对禁止**：`except: pass` 或空的 except 块

### 4.3 类型安全
- Patch 函数中访问对象属性时使用 `getattr(obj, 'attr', default)` 防御性编程
- 不假设上游对象具有特定的内部属性

---

## 5. 测试规范

### 5.1 测试文件位置
```
tests/test_{module_name}_patch.py
```

### 5.2 测试覆盖要求
每个 patch 模块的测试**必须**覆盖以下场景：

| 场景 | 说明 |
|------|------|
| Patch 前行为 | 验证上游原始方法的行为符合预期 |
| Patch 后行为 | 验证 patch 应用后新行为正确 |
| 可撤销性 | 验证 patch 可以被移除，系统回退到原始行为 |
| 拦截点缺失 | 模拟上游重构，验证 patch 优雅降级 |
| 幂等性 | 连续调用两次 `apply_*_patch()`，验证无副作用 |

### 5.3 测试框架
- 使用 `pytest` 作为测试框架
- 使用 `unittest.mock` 或 `pytest-mock` mock 上游依赖
- **不依赖**真实运行环境（不需要真实的 Telegram Bot Token、数据库文件等）

### 5.4 测试示例结构
```python
import pytest
from unittest.mock import MagicMock, patch

class TestToolsPatch:
    def test_original_behavior(self):
        """验证未 patch 时 AgentLoop 只注册默认工具"""
        ...

    def test_patched_behavior(self):
        """验证 patch 后追加了 5 个自定义工具"""
        ...

    def test_reversibility(self):
        """验证 patch 可撤销"""
        ...

    def test_missing_intercept_point(self):
        """验证拦截点缺失时优雅降级"""
        ...

    def test_idempotent(self):
        """验证多次应用不产生副作用"""
        ...
```

---

## 6. 新增 Patch 的 Checklist

在提交新的 patch 文件前，确认以下事项：

- [ ] 文件放在 `cafeext/patches/` 目录，命名为 `{module}_patch.py`
- [ ] 有完整的模块级文档字符串
- [ ] `apply_*_patch()` 函数有返回值描述
- [ ] 在模块末尾通过 `register_patch()` 自注册
- [ ] 保存了所有被替换方法的原始引用
- [ ] 有拦截点存在性检查
- [ ] 失败时打印 warning 日志而非静默失败
- [ ] 对应的 `tests/test_{module}_patch.py` 已编写
- [ ] 测试覆盖了上述 5 个场景
- [ ] 不修改 `nanobot/` 目录下的任何文件
- [ ] `launcher.py` 的执行顺序注释已更新（如有必要）

---

## 7. 版本兼容性

### 7.1 上游版本追踪
- 在 `cafeext/` 根目录维护 `UPSTREAM_VERSION` 文件，记录最后验证通过的上游 commit hash
- 每次上游更新后，运行全量 patch 测试

### 7.2 降级策略
当上游重构导致 patch 无法应用时：
1. Patch 自动跳过并输出警告
2. 开发者根据警告信息更新 patch
3. 更新 Module Spec 中的拦截点列表
4. 更新测试用例
