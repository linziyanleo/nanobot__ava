"""Tests for repo-tracked nanobot/ edit guardrails."""

from pathlib import Path


REPO_ROOT = Path(__file__).parents[2]


def test_pre_commit_hook_exists_and_checks_nanobot() -> None:
    """Repo-tracked pre-commit hook should guard nanobot/ edits."""
    hook = REPO_ROOT / ".githooks" / "pre-commit"
    assert hook.exists(), ".githooks/pre-commit not found"

    content = hook.read_text(encoding="utf-8")
    assert "ALLOW_NANOBOT_PATCH" in content
    assert "git diff --cached --name-only -- nanobot/" in content
    assert "COMMIT BLOCKED" in content


def test_install_hooks_script_sets_hooks_path() -> None:
    """Hook install script should configure repo-tracked hooksPath."""
    script = REPO_ROOT / "scripts" / "install-hooks.sh"
    assert script.exists(), "scripts/install-hooks.sh not found"

    content = script.read_text(encoding="utf-8")
    assert "git config core.hooksPath .githooks" in content
    assert ".githooks" in content
