"""Task 3: fork schema 漂移检测。"""

from __future__ import annotations

import ast
import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, get_args, get_origin


REPO_ROOT = Path(__file__).parents[2]
UPSTREAM_SCHEMA = REPO_ROOT / "nanobot" / "config" / "schema.py"
FORK_SCHEMA = REPO_ROOT / "ava" / "forks" / "config" / "schema.py"

CRITICAL_CLASSES = [
    "AgentDefaults",
    "GatewayConfig",
    "ToolsConfig",
    "ProvidersConfig",
    "MCPServerConfig",
]

INTENTIONAL_REMOVALS: dict[str, dict[str, str]] = {}

INTENTIONAL_DEFAULT_DRIFTS = {
    "AgentDefaults": {
        "model": "sidecar 默认模型刻意保持自己的演进节奏",
    },
}


def _parse_class_defs(path: Path) -> dict[str, list[ast.ClassDef]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    classes: dict[str, list[ast.ClassDef]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.setdefault(node.name, []).append(node)
    return classes


def _load_module(path: Path, module_name: str, *, upstream_module: ModuleType | None = None) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {path}")

    module = importlib.util.module_from_spec(spec)
    if upstream_module is not None:
        module._ava_upstream_schema = upstream_module
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def _load_schema_modules() -> tuple[ModuleType, ModuleType]:
    upstream = _load_module(UPSTREAM_SCHEMA, "_guardrail_upstream_schema")
    fork = _load_module(FORK_SCHEMA, "_guardrail_fork_schema", upstream_module=upstream)
    return upstream, fork


def _model_fields(module: ModuleType, class_name: str) -> dict[str, Any]:
    return getattr(module, class_name).model_fields


def _shared_field_names(upstream_fields: dict[str, Any], fork_fields: dict[str, Any]) -> list[str]:
    return sorted(set(upstream_fields) & set(fork_fields))


def _annotation_signature(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin is None:
        if isinstance(annotation, type):
            return annotation.__qualname__
        return repr(annotation)

    origin_name = getattr(origin, "__qualname__", getattr(origin, "__name__", repr(origin)))
    args = ",".join(_annotation_signature(arg) for arg in get_args(annotation))
    return f"{origin_name}[{args}]"


def _default_signature(field: Any) -> tuple[str, str]:
    default_factory = getattr(field, "default_factory", None)
    if default_factory is not None:
        return ("factory", getattr(default_factory, "__qualname__", repr(default_factory)))
    return ("value", repr(getattr(field, "default", None)))


def test_schema_files_exist() -> None:
    """上游 schema 和 fork schema 必须存在。"""
    assert UPSTREAM_SCHEMA.exists()
    assert FORK_SCHEMA.exists()


def test_no_duplicate_class_defs() -> None:
    """fork schema 内不允许重复类定义。"""
    class_defs = _parse_class_defs(FORK_SCHEMA)
    duplicates = sorted(name for name, defs in class_defs.items() if len(defs) > 1)
    assert duplicates == []


def test_no_unacknowledged_upstream_removals() -> None:
    """上游类不允许被 fork 静默删除。"""
    upstream_defs = _parse_class_defs(UPSTREAM_SCHEMA)
    fork_defs = _parse_class_defs(FORK_SCHEMA)

    missing_classes = sorted(set(upstream_defs) - set(fork_defs))
    assert missing_classes == []


def test_no_unacknowledged_upstream_additions() -> None:
    """上游字段若未同步到 fork，必须写入 INTENTIONAL_REMOVALS。"""
    upstream_module, fork_module = _load_schema_modules()

    unexpected: list[str] = []
    for class_name in _parse_class_defs(UPSTREAM_SCHEMA):
        upstream_fields = _model_fields(upstream_module, class_name)
        fork_fields = _model_fields(fork_module, class_name)
        for field_name in sorted(set(upstream_fields) - set(fork_fields)):
            reason = INTENTIONAL_REMOVALS.get(class_name, {}).get(field_name, "")
            if not reason.strip():
                unexpected.append(f"{class_name}.{field_name}")

    assert unexpected == []


def test_shared_field_annotations_match_for_critical_classes() -> None:
    """关键共享字段的 annotation 仍应与上游保持兼容。"""
    upstream_module, fork_module = _load_schema_modules()

    mismatches: list[str] = []
    for class_name in CRITICAL_CLASSES:
        upstream_fields = _model_fields(upstream_module, class_name)
        fork_fields = _model_fields(fork_module, class_name)
        for field_name in _shared_field_names(upstream_fields, fork_fields):
            upstream_annotation = _annotation_signature(upstream_fields[field_name].annotation)
            fork_annotation = _annotation_signature(fork_fields[field_name].annotation)
            if upstream_annotation != fork_annotation:
                mismatches.append(
                    f"{class_name}.{field_name}: {upstream_annotation} != {fork_annotation}"
                )

    assert mismatches == []


def test_shared_field_defaults_match_for_critical_classes() -> None:
    """关键共享字段的默认值变化必须显式登记。"""
    upstream_module, fork_module = _load_schema_modules()

    mismatches: list[str] = []
    for class_name in CRITICAL_CLASSES:
        upstream_fields = _model_fields(upstream_module, class_name)
        fork_fields = _model_fields(fork_module, class_name)
        for field_name in _shared_field_names(upstream_fields, fork_fields):
            upstream_default = _default_signature(upstream_fields[field_name])
            fork_default = _default_signature(fork_fields[field_name])
            if upstream_default == fork_default:
                continue
            if field_name in INTENTIONAL_DEFAULT_DRIFTS.get(class_name, {}):
                continue
            mismatches.append(
                f"{class_name}.{field_name}: {upstream_default} != {fork_default}"
            )

    assert mismatches == []
