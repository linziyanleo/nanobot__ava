"""
模板同步覆盖 Patch

将 ava/templates/ 作为事实源，覆盖上游 nanobot/templates/ 的"补缺不覆盖"策略。
同步链路：ava/templates/ 同名文件覆盖 → workspace。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from loguru import logger

from ava.launcher import register_patch

_AVA_TPL_DIR = Path(__file__).resolve().parent.parent / "templates"


def apply_templates_patch() -> str:
    import nanobot.utils.helpers as helpers_mod
    import nanobot.cli.commands as commands_mod

    _original_sync = helpers_mod.sync_workspace_templates

    def patched_sync(workspace: Path, silent: bool = False) -> list[str]:
        added = _original_sync(workspace, silent=silent)

        if not _AVA_TPL_DIR.is_dir():
            return added

        overlay_count = 0
        for src in _AVA_TPL_DIR.iterdir():
            if not src.name.endswith(".md") or src.name.startswith("."):
                continue
            dest = workspace / src.name
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dest))
                overlay_count += 1
            except Exception as exc:
                logger.warning("templates_patch: failed to overlay {}: {}", src.name, exc)

        if overlay_count and not silent:
            logger.debug("templates_patch: overlaid {} files from ava/templates/", overlay_count)
        return added

    helpers_mod.sync_workspace_templates = patched_sync
    commands_mod.sync_workspace_templates = patched_sync

    return "sync_workspace_templates 已接管，ava/templates/ 作为覆盖层"


register_patch("templates_patch", apply_templates_patch)
