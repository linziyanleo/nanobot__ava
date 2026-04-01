"""Task 5: patch 运行时契约检测。"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[2]
PATCH_DIR = REPO_ROOT / "ava" / "patches"
MODULE_INDEX = REPO_ROOT / ".specanchor" / "modules" / "module-index.md"


def _expected_patch_names() -> set[str]:
    names: set[str] = set()
    for path in sorted(PATCH_DIR.glob("*_patch.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "register_patch":
                continue
            if not node.args:
                continue
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                names.add(first_arg.value)
    return names


def _documented_patch_count() -> int:
    content = MODULE_INDEX.read_text(encoding="utf-8")
    return content.count("`ava/patches/")


def _run_python(code: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_apply_all_patches_twice_does_not_crash() -> None:
    """连续执行 apply_all_patches() 两次不应出现失败项。"""
    output = _run_python(
        """
        import json
        from ava.launcher import apply_all_patches

        results_first = apply_all_patches()
        results_second = apply_all_patches()
        print(json.dumps({"first": results_first, "second": results_second}))
        """
    )
    data = json.loads(output.splitlines()[-1])
    results_first = data["first"]
    results_second = data["second"]

    assert not any("FAILED" in item for item in results_first)
    assert not any("FAILED" in item for item in results_second)
    assert len(results_first) == len(results_second)


def test_patch_registry_has_expected_patch_names() -> None:
    """运行时 patch registry 应与源码 register_patch() 声明一致。"""
    output = _run_python(
        """
        import json
        from ava import launcher

        launcher.apply_all_patches()
        print(json.dumps(sorted({name for name, _ in launcher._PATCHES})))
        """
    )
    actual_names = set(json.loads(output.splitlines()[-1]))
    assert actual_names == _expected_patch_names()


def test_context_patch_is_idempotent() -> None:
    """context_patch 二次 apply 应明确返回 skipped。"""
    output = _run_python(
        """
        import json
        from ava.patches.context_patch import apply_context_patch

        print(json.dumps([apply_context_patch(), apply_context_patch()]))
        """
    )
    result = json.loads(output.splitlines()[-1])[1]
    assert "skipped" in result.lower()


def test_schema_patch_is_idempotent() -> None:
    """schema_patch 二次 apply 应明确返回 skipped。"""
    output = _run_python(
        """
        import json
        from ava.patches.a_schema_patch import apply_schema_patch

        print(json.dumps([apply_schema_patch(), apply_schema_patch()]))
        """
    )
    result = json.loads(output.splitlines()[-1])[1]
    assert "skipped" in result.lower()


@pytest.mark.parametrize(
    ("name", "code"),
    [
        (
            "console_patch",
            """
            import json
            import nanobot.cli.commands as cli_mod
            from ava.patches.console_patch import apply_console_patch

            cli_mod.app.registered_commands = []
            print(json.dumps(apply_console_patch()))
            """,
        ),
        (
            "bus_patch",
            """
            import json
            from nanobot.bus.queue import MessageBus
            from ava.patches.bus_patch import apply_bus_patch

            delattr(MessageBus, "publish_outbound")
            print(json.dumps(apply_bus_patch()))
            """,
        ),
        (
            "transcription_patch",
            """
            import json
            from nanobot.providers.transcription import GroqTranscriptionProvider
            from ava.patches.transcription_patch import apply_transcription_patch

            delattr(GroqTranscriptionProvider, "transcribe")
            print(json.dumps(apply_transcription_patch()))
            """,
        ),
    ],
)
def test_missing_intercept_points_degrade_gracefully_for_selected_patches(
    name: str, code: str
) -> None:
    """选定 patch 的拦截点消失时应优雅跳过。"""
    result = json.loads(_run_python(code).splitlines()[-1])
    assert "skip" in result.lower(), name


def test_apply_all_patches_matches_documented_count() -> None:
    """module-index 中记录的 patch 数量应与实际发现数量一致。"""
    output = _run_python(
        """
        import json
        from ava import launcher

        launcher.apply_all_patches()
        print(json.dumps(len({name for name, _ in launcher._PATCHES})))
        """
    )
    actual_count = int(json.loads(output.splitlines()[-1]))
    assert actual_count == _documented_patch_count()
