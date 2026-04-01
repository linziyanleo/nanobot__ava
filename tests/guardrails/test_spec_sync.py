"""Task 6: Spec / Doc / plan 同步检测。"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).parents[2]
PATCH_DIR = REPO_ROOT / "ava" / "patches"
MODULE_INDEX = REPO_ROOT / ".specanchor" / "modules" / "module-index.md"
GLOBAL_PATCH_SPEC = REPO_ROOT / ".specanchor" / "global-patch-spec.md"
SCHEMA_PATCH_SPEC = REPO_ROOT / ".specanchor" / "modules" / "schema_patch_spec.md"
PLAN_DOC = REPO_ROOT / "docs" / "superpowers" / "plans" / "2026-04-01-engineering-guardrails.md"
UPSTREAM_VERSION = REPO_ROOT / "ava" / "UPSTREAM_VERSION"
CONTRIBUTING_DOC = REPO_ROOT / "CONTRIBUTING.md"
EVIDENCE_DOC = (
    REPO_ROOT / "docs" / "superpowers" / "evidence" / "engineering-guardrails-demo.md"
)


def _module_index_entries() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    content = MODULE_INDEX.read_text(encoding="utf-8")
    pattern = re.compile(
        r"\|\s*`(ava/patches/[^`]+_patch\.py)`\s*\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|"
    )
    for match in pattern.finditer(content):
        patch_path = match.group(1)
        spec_path = match.group(3)
        entries.append((patch_path, spec_path))
    return entries


def test_module_index_covers_all_patch_files() -> None:
    """module-index 必须覆盖所有 patch 文件。"""
    actual_patch_files = {
        str(path.relative_to(REPO_ROOT)) for path in sorted(PATCH_DIR.glob("*_patch.py"))
    }
    indexed_patch_files = {patch_path for patch_path, _ in _module_index_entries()}
    assert indexed_patch_files == actual_patch_files


def test_patch_specs_reference_existing_files() -> None:
    """module-index 中引用的 spec 文件都必须真实存在。"""
    missing = []
    for _, spec_path in _module_index_entries():
        if not (MODULE_INDEX.parent / spec_path).exists():
            missing.append(spec_path)
    assert missing == []


def test_global_patch_spec_lists_all_patch_files() -> None:
    """global patch spec 必须列出当前 patch 文件集合。"""
    content = GLOBAL_PATCH_SPEC.read_text(encoding="utf-8")
    missing = [
        path.name
        for path in sorted(PATCH_DIR.glob("*_patch.py"))
        if path.name not in content
    ]
    assert missing == []


def test_schema_patch_spec_matches_current_field_set() -> None:
    """schema patch spec 应反映当前 fork 字段，不再包含过期字段。"""
    content = SCHEMA_PATCH_SPEC.read_text(encoding="utf-8")
    expected_fields = [
        "vision_model",
        "mini_model",
        "image_gen_model",
        "memory_tier",
        "memory_window",
        "context_compression",
        "in_loop_truncation",
        "history_summarizer",
    ]
    for field_name in expected_fields:
        assert field_name in content
    assert "voice_model" not in content


def test_plan_and_repo_hook_paths_match() -> None:
    """计划文档中的 hook 路径必须与仓库实现一致。"""
    content = PLAN_DOC.read_text(encoding="utf-8")
    assert ".githooks/pre-commit" in content
    assert ".git/hooks/pre-commit" not in content


def test_upstream_version_file_has_expected_format() -> None:
    """UPSTREAM_VERSION 需要包含 sha、verified_at 和 note。"""
    lines = UPSTREAM_VERSION.read_text(encoding="utf-8").splitlines()
    assert re.fullmatch(r"[0-9a-f]{40}", lines[0])
    assert any(line.startswith("# verified_at:") for line in lines[1:])
    assert any(line.startswith("# note:") for line in lines[1:])


def test_contributing_mentions_guardrails() -> None:
    """CONTRIBUTING 应说明 hook、例外路径和 UPSTREAM_VERSION。"""
    content = CONTRIBUTING_DOC.read_text(encoding="utf-8")
    assert "bash scripts/install-hooks.sh" in content
    assert "ALLOW_NANOBOT_PATCH=1" in content
    assert "ava/UPSTREAM_VERSION" in content


def test_evidence_doc_exists_and_lists_three_demos() -> None:
    """演讲证据文档必须存在并列出 3 个 demo。"""
    content = EVIDENCE_DOC.read_text(encoding="utf-8")
    assert "Demo 1" in content
    assert "Demo 2" in content
    assert "Demo 3" in content
