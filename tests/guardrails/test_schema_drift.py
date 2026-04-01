"""Task 3: fork schema 漂移检测。"""

from __future__ import annotations

import ast
from pathlib import Path


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

INTENTIONAL_REMOVALS = {
    "MCPServerConfig": {
        "enabled_tools": "sidecar 仍沿用旧版 MCP 白名单策略，暂未在 fork 中暴露",
        "type": "sidecar 仍使用旧版 transport 定义，等待后续同步上游新枚举",
    },
    "ProvidersConfig": {
        "byteplus": "当前 sidecar fork 尚未接入 BytePlus provider 配置",
        "byteplus_coding_plan": "当前 sidecar fork 尚未接入 BytePlus Coding Plan provider",
        "mistral": "当前 sidecar fork 尚未接入 Mistral provider",
        "ollama": "当前 sidecar fork 尚未接入 Ollama provider",
        "ovms": "当前 sidecar fork 尚未接入 OVMS provider",
        "stepfun": "当前 sidecar fork 尚未接入 StepFun provider",
        "volcengine_coding_plan": "当前 sidecar fork 尚未接入 VolcEngine Coding Plan provider",
    },
    "WebSearchConfig": {
        "base_url": "fork 仍保留 Brave-only 搜索配置，尚未同步 SearXNG base_url",
        "provider": "fork 仍保留 Brave-only 搜索配置，尚未同步多 provider 选择字段",
    },
}

INTENTIONAL_DEFAULT_DRIFTS = {
    "AgentDefaults": {
        "model": "sidecar 默认模型刻意保持自己的演进节奏",
    },
    "ProvidersConfig": {
        "github_copilot": "sidecar fork 允许该 provider 正常序列化到配置模型中",
        "openai_codex": "sidecar fork 允许该 provider 正常序列化到配置模型中",
    },
}


def _parse_schema(path: Path) -> tuple[ast.Module, dict[str, list[ast.ClassDef]], dict[str, dict[str, tuple[str, str | None]]]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    classes: dict[str, list[ast.ClassDef]] = {}
    fields: dict[str, dict[str, tuple[str, str | None]]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        classes.setdefault(node.name, []).append(node)
        class_fields: dict[str, tuple[str, str | None]] = {}
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                annotation = ast.unparse(item.annotation) if item.annotation else ""
                default = ast.unparse(item.value) if item.value is not None else None
                class_fields[item.target.id] = (annotation, default)
        fields[node.name] = class_fields
    return tree, classes, fields


def _shared_field_names(upstream_fields: dict[str, tuple[str, str | None]], fork_fields: dict[str, tuple[str, str | None]]) -> list[str]:
    return sorted(set(upstream_fields) & set(fork_fields))


def test_schema_files_exist() -> None:
    """上游 schema 和 fork schema 必须存在。"""
    assert UPSTREAM_SCHEMA.exists()
    assert FORK_SCHEMA.exists()


def test_no_duplicate_class_defs() -> None:
    """fork schema 内不允许重复类定义。"""
    _, class_defs, _ = _parse_schema(FORK_SCHEMA)
    duplicates = sorted(name for name, defs in class_defs.items() if len(defs) > 1)
    assert duplicates == []


def test_no_unacknowledged_upstream_removals() -> None:
    """上游类不允许被 fork 静默删除。"""
    _, upstream_classes, _ = _parse_schema(UPSTREAM_SCHEMA)
    _, fork_classes, _ = _parse_schema(FORK_SCHEMA)
    missing_classes = sorted(set(upstream_classes) - set(fork_classes))
    assert missing_classes == []


def test_no_unacknowledged_upstream_additions() -> None:
    """上游字段若未同步到 fork，必须写入 INTENTIONAL_REMOVALS 并说明原因。"""
    _, _, upstream_fields = _parse_schema(UPSTREAM_SCHEMA)
    _, _, fork_fields = _parse_schema(FORK_SCHEMA)

    unexpected: list[str] = []
    for class_name, upstream_class_fields in upstream_fields.items():
        fork_class_fields = fork_fields.get(class_name, {})
        for field_name in sorted(set(upstream_class_fields) - set(fork_class_fields)):
            reason = INTENTIONAL_REMOVALS.get(class_name, {}).get(field_name, "")
            if not reason.strip():
                unexpected.append(f"{class_name}.{field_name}")

    assert unexpected == []


def test_shared_field_annotations_match_for_critical_classes() -> None:
    """关键共享字段的 annotation 不应无声漂移。"""
    _, _, upstream_fields = _parse_schema(UPSTREAM_SCHEMA)
    _, _, fork_fields = _parse_schema(FORK_SCHEMA)

    mismatches: list[str] = []
    for class_name in CRITICAL_CLASSES:
        for field_name in _shared_field_names(upstream_fields[class_name], fork_fields[class_name]):
            upstream_annotation, _ = upstream_fields[class_name][field_name]
            fork_annotation, _ = fork_fields[class_name][field_name]
            if upstream_annotation != fork_annotation:
                mismatches.append(
                    f"{class_name}.{field_name}: {upstream_annotation} != {fork_annotation}"
                )

    assert mismatches == []


def test_shared_field_defaults_match_for_critical_classes() -> None:
    """关键共享字段的默认值变化必须显式登记。"""
    _, _, upstream_fields = _parse_schema(UPSTREAM_SCHEMA)
    _, _, fork_fields = _parse_schema(FORK_SCHEMA)

    mismatches: list[str] = []
    for class_name in CRITICAL_CLASSES:
        for field_name in _shared_field_names(upstream_fields[class_name], fork_fields[class_name]):
            _, upstream_default = upstream_fields[class_name][field_name]
            _, fork_default = fork_fields[class_name][field_name]
            if upstream_default == fork_default:
                continue
            if field_name in INTENTIONAL_DEFAULT_DRIFTS.get(class_name, {}):
                continue
            mismatches.append(
                f"{class_name}.{field_name}: {upstream_default} != {fork_default}"
            )

    assert mismatches == []
