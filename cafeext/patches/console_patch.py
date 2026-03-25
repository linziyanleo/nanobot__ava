"""Patch to mount Web Console onto the Gateway FastAPI app.

Unlike other patches that are zero-arg callables, the Console patch
needs runtime context (the FastAPI app, workspace, agent_loop, etc.).

Strategy: we monkey-patch the CLI gateway command so that after it
creates the FastAPI app but before it calls uvicorn.run(), it mounts
the Console sub-application.
"""

from __future__ import annotations

from loguru import logger

from cafeext.launcher import register_patch as _register


def apply_console_patch() -> str:
    """Patch the gateway startup to mount the Web Console.

    We wrap ``nanobot.cli.commands._create_gateway_app`` (or equivalent) so
    that the Console FastAPI app is mounted onto the main app at /console
    before Uvicorn begins serving.
    """
    import nanobot.cli.commands as cli_mod

    if not hasattr(cli_mod, "_create_gateway_app"):
        logger.warning(
            "Gateway app factory not found — console patch skipped. "
            "Console can still be mounted manually a cafeext.console.app."
        )
        return "Console patch skipped (no _create_gateway_app found)"

    original_factory = cli_mod._create_gateway_app

    def patched_gateway_factory(*args, **kwargs):
        """Create the gateway app, then mount Console onto it."""
        app = original_factory(*args, **kwargs)

        try:
            from cafeext.console.app import create_console_app

            console_app = create_console_app()
            app.mount("/console", console_app, name="console")
            logger.info("Web Console mounted at /console")
        except Exception as exc:
            logger.error("Failed to mount Web Console: {}", exc)

        return app

    cli_mod._create_gateway_app = patched_gateway_factory
    return "Gateway patched to mount Web Console at /console"


_register("web_console", apply_console_patch)
