"""扫描仓库，确认源码中不嵌入 bot token、API key 或私钥。"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

_PATTERNS = [
    (re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"), "Telegram Bot Token"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OpenAI API Key"),
    (re.compile(r"-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----"), "Private Key PEM"),
]

_SCAN_DIRS = ["ava", "console-ui/src"]
_SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", ".venv", "venv"}
_SCAN_EXTS = {".py", ".ts", ".tsx", ".js", ".mjs", ".json", ".md", ".yaml", ".yml", ".toml"}


def _iter_source_files():
    for scan_dir in _SCAN_DIRS:
        root = _REPO_ROOT / scan_dir
        if not root.exists():
            continue
        for f in root.rglob("*"):
            if any(part in _SKIP_DIRS for part in f.parts):
                continue
            if f.is_file() and f.suffix in _SCAN_EXTS:
                yield f


@pytest.mark.parametrize("pattern,label", _PATTERNS)
def test_no_embedded_secrets(pattern: re.Pattern, label: str):
    violations: list[str] = []
    for f in _iter_source_files():
        try:
            content = f.read_text(errors="replace")
        except OSError:
            continue
        for match in pattern.finditer(content):
            rel = f.relative_to(_REPO_ROOT)
            violations.append(f"  {rel}: {label} at offset {match.start()}")

    assert not violations, f"Found embedded secrets:\n" + "\n".join(violations)
