from __future__ import annotations

import os
from pathlib import Path

from ava.console.ui_build import needs_console_ui_build, prepare_console_ui_dist


def _write_file(path: Path, *, content: str = "x", mtime_ns: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    os.utime(path, ns=(mtime_ns, mtime_ns))


def test_prepare_console_ui_dist_skips_build_when_dist_is_fresh(tmp_path: Path):
    _write_file(tmp_path / "src" / "main.tsx", mtime_ns=100)
    _write_file(tmp_path / "package.json", mtime_ns=100)
    _write_file(tmp_path / "dist" / "index.html", mtime_ns=200)
    _write_file(tmp_path / "dist" / "assets" / "app.js", mtime_ns=200)

    build_calls: list[Path] = []
    dist_dir = prepare_console_ui_dist(tmp_path, build_runner=build_calls.append)

    assert needs_console_ui_build(tmp_path) is False
    assert dist_dir == tmp_path / "dist"
    assert build_calls == []


def test_prepare_console_ui_dist_builds_when_dist_is_missing(tmp_path: Path):
    _write_file(tmp_path / "src" / "main.tsx", mtime_ns=100)
    _write_file(tmp_path / "package.json", mtime_ns=100)

    build_calls: list[Path] = []

    def build_runner(root: Path) -> None:
        build_calls.append(root)
        _write_file(root / "dist" / "index.html", mtime_ns=300)
        _write_file(root / "dist" / "assets" / "app.js", mtime_ns=300)

    dist_dir = prepare_console_ui_dist(tmp_path, build_runner=build_runner)

    assert dist_dir == tmp_path / "dist"
    assert build_calls == [tmp_path]


def test_prepare_console_ui_dist_builds_when_source_is_newer(tmp_path: Path):
    _write_file(tmp_path / "src" / "main.tsx", mtime_ns=300)
    _write_file(tmp_path / "package.json", mtime_ns=300)
    _write_file(tmp_path / "dist" / "index.html", mtime_ns=200)
    _write_file(tmp_path / "dist" / "assets" / "app.js", mtime_ns=200)

    build_calls: list[Path] = []

    def build_runner(root: Path) -> None:
        build_calls.append(root)
        _write_file(root / "dist" / "index.html", mtime_ns=400)
        _write_file(root / "dist" / "assets" / "app.js", mtime_ns=400)

    assert needs_console_ui_build(tmp_path) is True

    dist_dir = prepare_console_ui_dist(tmp_path, build_runner=build_runner)

    assert dist_dir == tmp_path / "dist"
    assert build_calls == [tmp_path]


def test_prepare_console_ui_dist_returns_none_when_build_fails_without_dist(tmp_path: Path):
    _write_file(tmp_path / "src" / "main.tsx", mtime_ns=100)
    _write_file(tmp_path / "package.json", mtime_ns=100)

    def build_runner(_: Path) -> None:
        raise RuntimeError("boom")

    assert prepare_console_ui_dist(tmp_path, build_runner=build_runner) is None


def test_prepare_console_ui_dist_keeps_existing_dist_when_rebuild_fails(tmp_path: Path):
    _write_file(tmp_path / "src" / "main.tsx", mtime_ns=300)
    _write_file(tmp_path / "package.json", mtime_ns=300)
    _write_file(tmp_path / "dist" / "index.html", mtime_ns=200)
    _write_file(tmp_path / "dist" / "assets" / "app.js", mtime_ns=200)

    def build_runner(_: Path) -> None:
        raise RuntimeError("boom")

    assert prepare_console_ui_dist(tmp_path, build_runner=build_runner) == tmp_path / "dist"
