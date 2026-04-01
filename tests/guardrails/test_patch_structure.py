"""Task 4: patch 结构约束检测。"""

from __future__ import annotations

import ast
import re
from pathlib import Path


REPO_ROOT = Path(__file__).parents[2]
PATCH_DIR = REPO_ROOT / "ava" / "patches"
PATCH_FILES = sorted(PATCH_DIR.glob("*_patch.py"))
PATCH_TEST_DIR = REPO_ROOT / "tests" / "patches"


def _read_patch(path: Path) -> tuple[str, ast.Module]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    return source, tree


def _normalized_patch_name(path: Path) -> str:
    stem = path.stem
    if re.match(r"^[a-z]_.+_patch$", stem):
        return stem.split("_", 1)[1]
    return stem


def _candidate_test_paths(path: Path) -> list[Path]:
    stem = path.stem
    normalized = _normalized_patch_name(path)
    return [
        PATCH_TEST_DIR / f"test_{stem}.py",
        PATCH_TEST_DIR / f"test_{normalized}.py",
    ]


def test_patch_files_have_module_docstrings() -> None:
    """每个 patch 文件都必须有模块级 docstring。"""
    missing = []
    for path in PATCH_FILES:
        _, tree = _read_patch(path)
        if not ast.get_docstring(tree):
            missing.append(path.name)
    assert missing == []


def test_patch_files_define_apply_function_returning_str() -> None:
    """每个 patch 文件都必须定义 apply_*_patch() -> str。"""
    missing = []
    for path in PATCH_FILES:
        _, tree = _read_patch(path)
        apply_functions = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and re.match(r"apply_.+_patch$", node.name)
        ]
        if not apply_functions:
            missing.append(path.name)
            continue
        if all(ast.unparse(node.returns) != "str" for node in apply_functions if node.returns):
            missing.append(path.name)
            continue
        if all(node.returns is None for node in apply_functions):
            missing.append(path.name)
    assert missing == []


def test_patch_files_register_themselves() -> None:
    """每个 patch 文件都必须调用 register_patch() 自注册。"""
    missing = []
    for path in PATCH_FILES:
        _, tree = _read_patch(path)
        has_register_call = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "register_patch"
            for node in ast.walk(tree)
        )
        if not has_register_call:
            missing.append(path.name)
    assert missing == []


def test_patch_files_have_guard_or_skip_path() -> None:
    """每个 patch 至少要有一个 guard/skip 分支，避免上游重构时硬崩。"""
    failures = []
    for path in PATCH_FILES:
        source, _ = _read_patch(path)
        has_guard_token = any(
            token in source
            for token in ("hasattr(", "getattr(", ".exists()", ".exists(", " is None")
        )
        has_skip_path = "skipped" in source or "skip" in source or "logger.warning" in source
        if not (has_guard_token and has_skip_path):
            failures.append(path.name)
    assert failures == []


def test_patch_files_have_corresponding_patch_tests() -> None:
    """每个 patch 都要有 tests/patches/ 下的专项测试。"""
    missing = []
    for path in PATCH_FILES:
        candidates = _candidate_test_paths(path)
        if not any(candidate.exists() for candidate in candidates):
            missing.append(path.name)
    assert missing == []
