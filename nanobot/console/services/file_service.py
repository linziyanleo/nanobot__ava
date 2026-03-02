"""File system operations with whitelist-based access control."""

from __future__ import annotations

import os
from pathlib import Path

from nanobot.console.models import FileNode, FileContent


IGNORED_NAMES = {".DS_Store", "__pycache__", ".git", "node_modules", ".venv"}


class FileService:
    def __init__(self, workspace: Path, nanobot_dir: Path):
        self._roots = {
            "workspace": workspace.resolve(),
            "nanobot": nanobot_dir.resolve(),
        }

    def _resolve_and_validate(self, path: str) -> Path:
        """Resolve path and validate it's within allowed roots."""
        resolved = Path(path).resolve()
        for root in self._roots.values():
            try:
                resolved.relative_to(root)
                return resolved
            except ValueError:
                continue
        raise PermissionError(f"Access denied: {path}")

    def get_file_tree(self, root: str = "workspace") -> FileNode:
        base = self._roots.get(root)
        if not base or not base.exists():
            raise ValueError(f"Root '{root}' not found")
        return self._build_tree(base, base)

    def _build_tree(self, path: Path, base: Path, depth: int = 0) -> FileNode:
        rel = str(path.relative_to(base.parent))
        node = FileNode(name=path.name, path=rel, type="directory" if path.is_dir() else "file")
        if path.is_dir() and depth < 5:
            children = []
            try:
                for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                    if child.name in IGNORED_NAMES:
                        continue
                    children.append(self._build_tree(child, base, depth + 1))
            except PermissionError:
                pass
            node.children = children
        return node

    def read_file(self, path: str) -> FileContent:
        resolved = self._resolve_and_validate(path)
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not resolved.is_file():
            raise ValueError(f"Not a file: {path}")
        return FileContent(
            path=path,
            content=resolved.read_text("utf-8"),
            mtime=resolved.stat().st_mtime,
        )

    def write_file(self, path: str, content: str, expected_mtime: float) -> FileContent:
        resolved = self._resolve_and_validate(path)
        if resolved.exists():
            current_mtime = resolved.stat().st_mtime
            if abs(current_mtime - expected_mtime) > 0.01:
                raise ValueError("File was modified externally. Please reload.")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, "utf-8")
        return FileContent(
            path=path,
            content=content,
            mtime=resolved.stat().st_mtime,
        )
