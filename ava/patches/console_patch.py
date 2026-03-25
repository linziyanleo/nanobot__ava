"""Patch to launch Web Console alongside the nanobot gateway.

Strategy:
  Wrap the Typer `gateway` command callback so that before calling
  asyncio.run(), we inject a Console uvicorn server into the same
  event loop as a background task.

Console is served at: http://0.0.0.0:<CAFE_CONSOLE_PORT>  (default 18791)
Set CAFE_CONSOLE_PORT env var to change.
"""

from __future__ import annotations

import os

from loguru import logger

from ava.launcher import register_patch

CONSOLE_PORT = int(os.environ.get("CAFE_CONSOLE_PORT", "18791"))
CONSOLE_HOST = os.environ.get("CAFE_CONSOLE_HOST", "0.0.0.0")


def apply_console_patch() -> str:
    import nanobot.cli.commands as cli_mod

    # Find the gateway CommandInfo in the Typer app
    gateway_cmd = None
    for cmd_info in cli_mod.app.registered_commands:
        cb = getattr(cmd_info, "callback", None)
        if cb and cb.__name__ == "gateway":
            gateway_cmd = cmd_info
            break

    if gateway_cmd is None:
        logger.warning("gateway command not found in Typer app — console patch skipped")
        return "Console patch skipped (gateway command not found)"

    original_callback = gateway_cmd.callback

    def patched_gateway(*args, **kwargs) -> None:
        """Wrap gateway to inject Console into the event loop."""
        import asyncio

        original_asyncio_run = asyncio.run

        _intercepted = {"done": False}

        def patched_asyncio_run(coro, **run_kwargs):
            if _intercepted["done"]:
                return original_asyncio_run(coro, **run_kwargs)
            _intercepted["done"] = True

            async def _with_console():
                console_task = None
                try:
                    from ava.console.app import create_console_app
                    import uvicorn

                    console_app = create_console_app()
                    uvicorn_config = uvicorn.Config(
                        console_app,
                        host=CONSOLE_HOST,
                        port=CONSOLE_PORT,
                        log_level="warning",
                    )
                    server = uvicorn.Server(uvicorn_config)
                    console_task = asyncio.create_task(server.serve())
                    logger.info(
                        "Web Console starting at http://{}:{}/", CONSOLE_HOST, CONSOLE_PORT
                    )
                    print(
                        f"☕ Web Console → http://localhost:{CONSOLE_PORT}/"
                    )
                except Exception as exc:
                    logger.warning("Failed to start Web Console: {}", exc)

                try:
                    await coro
                finally:
                    if console_task and not console_task.done():
                        console_task.cancel()
                        try:
                            await console_task
                        except asyncio.CancelledError:
                            pass

            try:
                asyncio.run = original_asyncio_run  # restore before running
                return original_asyncio_run(_with_console(), **run_kwargs)
            finally:
                pass  # asyncio.run already restored

        asyncio.run = patched_asyncio_run
        try:
            original_callback(*args, **kwargs)
        finally:
            asyncio.run = original_asyncio_run  # ensure restore

    # Replace the callback in the CommandInfo
    gateway_cmd.callback = patched_gateway
    # Also update the module-level function reference
    cli_mod.gateway = patched_gateway

    return (
        f"gateway callback wrapped — Console will start at "
        f"http://localhost:{CONSOLE_PORT}/"
    )


register_patch("web_console", apply_console_patch)
