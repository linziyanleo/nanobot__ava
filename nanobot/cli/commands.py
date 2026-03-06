"""CLI commands for nanobot."""

import asyncio
import os
import signal
import socket
import atexit
from pathlib import Path
import select
import sys

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout

from nanobot import __version__, __logo__
from nanobot.config.schema import Config
from nanobot.utils.helpers import sync_workspace_templates

app = typer.Typer(
    name="Nanobot",
    help=f"{__logo__} Nanobot - Personal AI Assistant",
    no_args_is_help=True,
)

console = Console()
EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}

# ============================================================================
# Gateway Single Instance Protection
# ============================================================================

GATEWAY_PID_FILE = Path.home() / ".nanobot" / "gateway.pid"
CONSOLE_PID_FILE = Path.home() / ".nanobot" / "console.pid"
GATEWAY_DEFAULT_PORT = 18790


def _check_console_running() -> int | None:
    """Check if the console process is already running."""
    if not CONSOLE_PID_FILE.exists():
        return None
    try:
        pid = int(CONSOLE_PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (ProcessLookupError, ValueError, PermissionError):
        try:
            CONSOLE_PID_FILE.unlink()
        except Exception:
            pass
        return None


def _run_console_server(
    nanobot_dir_str: str,
    workspace_str: str,
    host: str,
    c_port: int,
    gw_port: int,
    secret_key: str,
    expire_minutes: int,
    token_stats_dir: str,
    pid_file_str: str,
    dev_mode: bool = False,
) -> None:
    """Run the console UI server in a separate process (must be module-level for pickling)."""
    import signal as _sig
    import subprocess

    pid_path = Path(pid_file_str)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()))

    vite_proc: subprocess.Popen | None = None

    def _cleanup_console_pid(*_args):
        if vite_proc and vite_proc.poll() is None:
            vite_proc.terminate()
        try:
            pid_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise SystemExit(0)

    _sig.signal(_sig.SIGTERM, _cleanup_console_pid)
    atexit.register(lambda: pid_path.unlink(missing_ok=True))

    import uvicorn
    from nanobot.console.app import create_console_app_standalone

    if dev_mode:
        # Dev mode: Vite dev server gets the main port (c_port) for HMR,
        # uvicorn API server runs on c_port+1, Vite proxies /api to it.
        api_port = c_port + 1
        console_ui_dir = Path(__file__).parent.parent / "console-ui"
        if not (console_ui_dir / "node_modules").exists():
            subprocess.check_call(["npm", "install"], cwd=str(console_ui_dir))
        vite_env = {**os.environ, "NANOBOT_CONSOLE_PORT": str(api_port)}
        vite_proc = subprocess.Popen(
            ["npx", "vite", "--host", host, "--port", str(c_port)],
            cwd=str(console_ui_dir),
            env=vite_env,
        )
        atexit.register(lambda: vite_proc.terminate() if vite_proc.poll() is None else None)
    else:
        api_port = c_port

    console_app = create_console_app_standalone(
        nanobot_dir=Path(nanobot_dir_str),
        workspace=Path(workspace_str),
        gateway_port=gw_port,
        console_port=api_port,
        secret_key=secret_key,
        expire_minutes=expire_minutes,
        token_stats_dir=token_stats_dir,
    )
    uvicorn_config = uvicorn.Config(
        console_app, host=host, port=api_port, log_level="warning",
    )
    server = uvicorn.Server(uvicorn_config)
    server.run()


def check_gateway_running() -> int | None:
    """Check if gateway is already running.

    Returns:
        PID if running, None if not running
    """
    if not GATEWAY_PID_FILE.exists():
        return None

    try:
        pid = int(GATEWAY_PID_FILE.read_text().strip())
        # Check if process exists (signal 0 doesn't send a signal, just checks)
        os.kill(pid, 0)
        return pid
    except (ProcessLookupError, ValueError, PermissionError):
        # Process doesn't exist or PID file is corrupted
        # Clean up stale PID file
        try:
            GATEWAY_PID_FILE.unlink()
        except Exception:
            pass
        return None


def write_pid_file() -> None:
    """Write current process PID to PID file."""
    GATEWAY_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    GATEWAY_PID_FILE.write_text(str(os.getpid()))


def cleanup_pid_file() -> None:
    """Remove PID file."""
    if GATEWAY_PID_FILE.exists():
        try:
            GATEWAY_PID_FILE.unlink()
        except Exception:
            pass


def check_port_in_use(port: int) -> bool:
    """Check if a port is already in use.

    Returns:
        True if port is in use, False otherwise
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', port))
        return False
    except OSError:
        return True
    finally:
        sock.close()


def setup_gateway_cleanup() -> None:
    """Setup cleanup handlers for gateway."""
    def cleanup():
        cleanup_pid_file()

    # Register cleanup on normal exit
    atexit.register(cleanup)

    # Register cleanup on signals
    def signal_handler(signum, frame):
        cleanup()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

# ---------------------------------------------------------------------------
# CLI input: prompt_toolkit for editing, paste, history, and display
# ---------------------------------------------------------------------------

_PROMPT_SESSION: PromptSession | None = None
_SAVED_TERM_ATTRS = None  # original termios settings, restored on exit


def _flush_pending_tty_input() -> None:
    """Drop unread keypresses typed while the model was generating output."""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return

    try:
        import termios
        termios.tcflush(fd, termios.TCIFLUSH)
        return
    except Exception:
        pass

    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break
    except Exception:
        return


def _restore_terminal() -> None:
    """Restore terminal to its original state (echo, line buffering, etc.)."""
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass


def _init_prompt_session() -> None:
    """Create the prompt_toolkit session with persistent file history."""
    global _PROMPT_SESSION, _SAVED_TERM_ATTRS

    # Save terminal state so we can restore it on exit
    try:
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    history_file = Path.home() / ".nanobot" / "history" / "cli_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    _PROMPT_SESSION = PromptSession(
        history=FileHistory(str(history_file)),
        enable_open_in_editor=False,
        multiline=False,   # Enter submits (single line mode)
    )


def _print_agent_response(response: str, render_markdown: bool) -> None:
    """Render assistant response with consistent terminal styling."""
    content = response or ""
    body = Markdown(content) if render_markdown else Text(content)
    console.print()
    console.print(f"[cyan]{__logo__} Nanobot[/cyan]")
    console.print(body)
    console.print()


def _is_exit_command(command: str) -> bool:
    """Return True when input should end interactive chat."""
    return command.lower() in EXIT_COMMANDS


async def _read_interactive_input_async() -> str:
    """Read user input using prompt_toolkit (handles paste, history, display).

    prompt_toolkit natively handles:
    - Multiline paste (bracketed paste mode)
    - History navigation (up/down arrows)
    - Clean display (no ghost characters or artifacts)
    """
    if _PROMPT_SESSION is None:
        raise RuntimeError("Call _init_prompt_session() first")
    try:
        with patch_stdout():
            return await _PROMPT_SESSION.prompt_async(
                HTML("<b fg='ansiblue'>You:</b> "),
            )
    except EOFError as exc:
        raise KeyboardInterrupt from exc



def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} Nanobot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """nanobot - Personal AI Assistant."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize nanobot configuration and workspace."""
    from nanobot.config.loader import get_config_path, load_config, save_config
    from nanobot.config.schema import Config
    from nanobot.utils.helpers import get_workspace_path

    config_path = get_config_path()

    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        console.print("  [bold]y[/bold] = overwrite with defaults (existing values will be lost)")
        console.print("  [bold]N[/bold] = refresh config, keeping existing values and adding new fields")
        if typer.confirm("Overwrite?"):
            config = Config()
            save_config(config)
            console.print(f"[green]✓[/green] Config reset to defaults at {config_path}")
        else:
            config = load_config()
            save_config(config)
            console.print(f"[green]✓[/green] Config refreshed at {config_path} (existing values preserved)")
    else:
        save_config(Config())
        console.print(f"[green]✓[/green] Created config at {config_path}")

    # Create workspace
    workspace = get_workspace_path()

    if not workspace.exists():
        workspace.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] Created workspace at {workspace}")

    sync_workspace_templates(workspace)

    console.print(f"\n{__logo__} Nanobot is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.nanobot/config.json[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print("  2. Chat: [cyan]nanobot agent -m \"Hello!\"[/cyan]")
    console.print("\n[dim]Want Telegram/WhatsApp? See: https://github.com/HKUDS/nanobot#-chat-apps[/dim]")





def _make_provider(config: Config):
    """Create the appropriate LLM provider from config."""
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.openai_codex_provider import OpenAICodexProvider
    from nanobot.providers.custom_provider import CustomProvider

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)

    # OpenAI Codex (OAuth)
    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
        return OpenAICodexProvider(default_model=model, provider_name="openai_codex")

    # Custom: direct OpenAI-compatible endpoint, bypasses LiteLLM
    if provider_name == "custom":
        return CustomProvider(
            api_key=p.api_key if p else "no-key",
            api_base=config.get_api_base(model) or "http://localhost:8000/v1",
            default_model=model,
            provider_name="custom",
        )

    from nanobot.providers.registry import find_by_name
    spec = find_by_name(provider_name)
    if not model.startswith("bedrock/") and not (p and p.api_key) and not (spec and spec.is_oauth):
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Set one in ~/.nanobot/config.json under providers section")
        raise typer.Exit(1)

    # Collect cross-provider configs for mini/vision/voice models
    extra_model_configs: dict[str, tuple[str, str | None]] = {}
    for alt_model in (
        config.agents.defaults.mini_model,
        config.agents.defaults.vision_model,
        config.agents.defaults.voice_model,
    ):
        if not alt_model:
            continue
        alt_provider_name = config.get_provider_name(alt_model)
        if alt_provider_name and alt_provider_name != provider_name:
            alt_p = config.get_provider(alt_model)
            if alt_p and alt_p.api_key:
                extra_model_configs[alt_provider_name] = (
                    alt_p.api_key,
                    config.get_api_base(alt_model),
                )

    return LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(model),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=provider_name,
        extra_model_configs=extra_model_configs or None,
    )


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def gateway(
    port: int = typer.Option(GATEWAY_DEFAULT_PORT, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    dev: bool = typer.Option(False, "--dev", help="Enable Vite dev server with HMR for console-ui"),
):
    """Start the nanobot gateway."""
    from nanobot.config.loader import load_config, get_data_dir
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop
    from nanobot.channels.manager import ChannelManager
    from nanobot.session.manager import SessionManager
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.heartbeat.service import HeartbeatService

    # Single instance check
    existing_pid = check_gateway_running()
    if existing_pid:
        console.print(f"[red]Error: Gateway already running (PID: {existing_pid})[/red]")
        console.print("Use [cyan]nanobot gateway-stop[/cyan] to stop it first")
        console.print("Or use [cyan]nanobot gateway-restart[/cyan] to restart")
        raise typer.Exit(1)

    # Double-check port availability
    if check_port_in_use(port):
        console.print(f"[red]Error: Port {port} is already in use[/red]")
        console.print("Another gateway or service may be using this port")
        raise typer.Exit(1)


    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    console.print(f"{__logo__} Starting nanobot gateway on port {port}...")

    config = load_config()
    sync_workspace_templates(config.workspace_path)
    bus = MessageBus()
    provider = _make_provider(config)
    session_manager = SessionManager(config.workspace_path)

    if config.gateway.console.enabled:
        _console_port = config.gateway.console.port
        if _console_port != port and check_port_in_use(_console_port):
            console.print(f"[red]Error: Console port {_console_port} is already in use[/red]")
            raise typer.Exit(1)

    from nanobot.console.services.token_stats_service import TokenStatsCollector
    token_stats_collector = TokenStatsCollector(data_dir=get_data_dir() / "console")

    # Create cron service first (callback set after agent creation)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    # Create agent with cron service
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        vision_model=config.agents.defaults.vision_model,
        mini_model=config.agents.defaults.mini_model,
        voice_model=config.agents.defaults.voice_model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        reasoning_effort=config.agents.defaults.reasoning_effort,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
        mcp_servers=config.tools.mcp_servers,
        channels_config=config.channels,
        context_compression=config.agents.defaults.context_compression,
        memory_tier=config.agents.defaults.memory_tier,
        in_loop_truncation=config.agents.defaults.in_loop_truncation,
        token_stats=token_stats_collector,
        record_full_request_payload=config.token_stats.record_full_request_payload,
    )

    # Set cron callback (needs agent)
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job through the agent."""
        from nanobot.agent.tools.cron import CronTool
        from nanobot.agent.tools.message import MessageTool
        reminder_note = (
            "[Scheduled Task] Timer finished.\n\n"
            f"Task '{job.name}' has been triggered.\n"
            f"Scheduled instruction: {job.payload.message}"
        )

        # Select model based on job's model_tier setting
        model_override = agent.get_model_for_tier(job.payload.model_tier)

        # Prevent the agent from scheduling new cron jobs during execution
        cron_tool = agent.tools.get("cron")
        cron_token = None
        if isinstance(cron_tool, CronTool):
            cron_token = cron_tool.set_cron_context(True)
        try:
            response = await agent.process_direct(
                reminder_note,
                session_key=f"cron:{job.id}",
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to or "direct",
                model_override=model_override,
            )
        finally:
            if isinstance(cron_tool, CronTool) and cron_token is not None:
                cron_tool.reset_cron_context(cron_token)

        message_tool = agent.tools.get("message")
        if isinstance(message_tool, MessageTool) and message_tool._sent_in_turn:
            return response

        if job.payload.deliver and job.payload.to and response:
            from nanobot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to,
                content=response or ""
            ))
        return response
    cron.on_job = on_cron_job

    # Create channel manager
    channels = ChannelManager(config, bus)

    def _pick_heartbeat_target() -> tuple[str, str]:
        """Pick a routable channel/chat target for heartbeat-triggered messages."""
        enabled = set(channels.enabled_channels)
        # Prefer the most recently updated non-internal session on an enabled channel.
        for item in session_manager.list_sessions():
            key = item.get("key") or ""
            if ":" not in key:
                continue
            channel, chat_id = key.split(":", 1)
            if channel in {"cli", "system"}:
                continue
            if channel in enabled and chat_id:
                return channel, chat_id
        # Fallback keeps prior behavior but remains explicit.
        return "cli", "direct"

    # Create heartbeat service
    async def on_heartbeat_execute(tasks: str) -> str:
        """Phase 2: execute heartbeat tasks through the full agent loop."""
        channel, chat_id = _pick_heartbeat_target()

        async def _silent(*_args, **_kwargs):
            pass

        return await agent.process_direct(
            tasks,
            session_key="heartbeat",
            channel=channel,
            chat_id=chat_id,
            on_progress=_silent,
        )

    async def on_heartbeat_notify(response: str) -> None:
        """Deliver a heartbeat response to the user's channel."""
        from nanobot.bus.events import OutboundMessage
        channel, chat_id = _pick_heartbeat_target()
        if channel == "cli":
            return  # No external channel available to deliver to
        await bus.publish_outbound(OutboundMessage(channel=channel, chat_id=chat_id, content=response))

    hb_cfg = config.gateway.heartbeat
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        provider=provider,
        model=agent.model,
        mini_model=agent.mini_model,
        on_execute=on_heartbeat_execute,
        on_notify=on_heartbeat_notify,
        interval_s=hb_cfg.interval_s,
        enabled=hb_cfg.enabled,
    )

    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")

    schedule_path = config.workspace_path / "schedule.json"
    if schedule_path.exists():
        sched_count = cron.load_schedule(schedule_path)
        if sched_count:
            console.print(f"[green]✓[/green] Schedule: {sched_count} tasks loaded from schedule.json")

    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")

    console.print(f"[green]✓[/green] Heartbeat: every {hb_cfg.interval_s}s")

    # Write PID file and setup cleanup
    write_pid_file()
    setup_gateway_cleanup()
    console.print(f"[green]✓[/green] Gateway PID: {os.getpid()}")

    console_cfg = config.gateway.console
    console_port = console_cfg.port if console_cfg.enabled else port
    if console_cfg.enabled:
        console.print(f"[green]✓[/green] Console: http://localhost:{console_port}")

    if console_cfg.enabled:
        existing_console_pid = _check_console_running()
        if existing_console_pid:
            console.print(f"[green]✓[/green] Console already running (PID: {existing_console_pid}), reusing")
        else:
            _start_console_process(dev=dev)

    # Build the gateway-embedded console app (with ChatService + AgentLoop)
    import uvicorn
    from nanobot.console.app import create_console_app
    gateway_app = create_console_app(
        nanobot_dir=get_data_dir(),
        workspace=config.workspace_path,
        agent_loop=agent,
        config=config,
        token_stats_collector=token_stats_collector,
    )
    gateway_uvicorn = uvicorn.Server(uvicorn.Config(
        gateway_app, host=config.gateway.host, port=port, log_level="warning",
    ))
    console.print(f"[green]✓[/green] Gateway API: http://localhost:{port}")

    async def run():
        try:
            await cron.start()
            await heartbeat.start()

            tasks = [
                agent.run(),
                channels.start_all(),
                gateway_uvicorn.serve(),
            ]

            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            console.print("\nShutting down...")
        finally:
            gateway_uvicorn.should_exit = True
            await agent.close_mcp()
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()

    asyncio.run(run())


# ============================================================================
# Gateway Management Commands
# ============================================================================


@app.command("gateway-status")
def gateway_status_cmd():
    """Show gateway running status."""
    pid = check_gateway_running()

    if not pid:
        console.print(f"{__logo__} 网关状态\n")
        console.print("状态: [yellow]未运行[/yellow]")
        console.print("\n[dim]使用 [cyan]nanobot gateway[/cyan] 启动[/dim]")
        return

    # Get process info
    try:
        import subprocess
        result = subprocess.run(
            ["ps", "-o", "pid,lstart,etime,rss,command", "-p", str(pid)],
            capture_output=True,
            text=True
        )
        lines = result.stdout.strip().split("\n")

        if len(lines) < 2:
            console.print(f"[red]Error: Process {pid} not found[/red]")
            cleanup_pid_file()
            return

        # Parse process info
        parts = lines[1].split(None, 6)
        if len(parts) >= 5:
            start_time = " ".join(parts[1:5])
            elapsed = parts[5]
            rss_kb = parts[6] if len(parts) > 6 else "N/A"

            try:
                rss_mb = int(rss_kb) / 1024
                rss_str = f"{rss_mb:.1f} MB"
            except (ValueError, IndexError):
                rss_str = rss_kb

            console.print(f"{__logo__} 网关状态\n")
            console.print(f"状态: [green]✓ 运行中[/green]")
            console.print(f"PID: [cyan]{pid}[/cyan]")
            console.print(f"端口: [cyan]{GATEWAY_DEFAULT_PORT}[/cyan]")
            console.print(f"启动时间: [dim]{start_time}[/dim]")
            console.print(f"运行时间: [dim]{elapsed}[/dim]")
            console.print(f"Memory: [dim]{rss_str}[/dim]")
            console.print(f"PID File: [dim]{GATEWAY_PID_FILE}[/dim]")
        else:
            console.print(f"[yellow]Warning: Could not parse process info[/yellow]")
            console.print(f"PID: {pid}")

    except Exception as e:
        console.print(f"[yellow]Warning: Could not get process details: {e}[/yellow]")
        console.print(f"PID: {pid}")


@app.command("gateway-stop")
def gateway_stop_cmd(
    force: bool = typer.Option(False, "--force", "-f", help="Force kill (SIGKILL)"),
    timeout: int = typer.Option(10, "--timeout", "-t", help="Timeout in seconds before force kill"),
):
    """Stop the gateway gracefully."""
    pid = check_gateway_running()

    if not pid:
        console.print(f"{__logo__} 网关状态\n")
        console.print("状态: [yellow]未运行[/yellow]")
        console.print("\n[dim]使用 [cyan]nanobot gateway[/cyan] 启动[/dim]")
        return

    console.print(f"{__logo__} 停止网关\n")
    console.print(f"PID: [cyan]{pid}[/cyan]")

    try:
        if force:
            console.print("Force mode: sending SIGKILL...")
            os.kill(pid, signal.SIGKILL)
            sleep_time = 2
        else:
            console.print("Sending SIGTERM for graceful shutdown...")
            os.kill(pid, signal.SIGTERM)
            sleep_time = timeout

        import time
        elapsed = 0
        while elapsed < sleep_time:
            time.sleep(1)
            elapsed += 1
            try:
                os.kill(pid, 0)
                if not force:
                    console.print(f"Waiting for process to exit... ({elapsed}/{sleep_time})")
            except ProcessLookupError:
                console.print(f"[green]✓ Gateway stopped successfully[/green]")
                cleanup_pid_file()
                return

        if not force:
            console.print(f"[yellow]Timeout after {timeout}s, sending SIGKILL...[/yellow]")
            os.kill(pid, signal.SIGKILL)
            time.sleep(2)

        try:
            os.kill(pid, 0)
            console.print(f"[red]Error: Failed to stop gateway process[/red]")
            console.print("Manual intervention may be required")
            raise typer.Exit(1)
        except ProcessLookupError:
            console.print(f"[green]✓ Gateway stopped successfully[/green]")
            cleanup_pid_file()

    except ProcessLookupError:
        console.print(f"[yellow]Warning: Process {pid} not found[/yellow]")
        cleanup_pid_file()
    except PermissionError:
        console.print(f"[red]Error: Permission denied to stop process {pid}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    _stop_console_process()


def _stop_console_process(quiet: bool = False) -> bool:
    """Stop the console process if running. Returns True if a process was stopped."""
    pid = _check_console_running()
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        import time
        for _ in range(10):
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
        if not quiet:
            console.print(f"[green]✓[/green] Console process stopped (PID: {pid})")
    except (ProcessLookupError, ValueError, PermissionError):
        pass
    try:
        CONSOLE_PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    return True


def _start_console_process(dev: bool = False) -> int | None:
    """Start the console process. Returns the new PID, or None on failure."""
    import multiprocessing
    from nanobot.config.loader import load_config, get_data_dir

    config = load_config()
    console_cfg = config.gateway.console

    if not console_cfg.enabled:
        console.print("[yellow]Console is disabled in config[/yellow]")
        return None

    console_port = console_cfg.port

    if check_port_in_use(console_port):
        existing = _check_console_running()
        if existing:
            console.print(f"[yellow]Console already running (PID: {existing})[/yellow]")
            return existing
        console.print(f"[red]Error: Port {console_port} is already in use[/red]")
        return None

    if dev and check_port_in_use(console_port + 1):
        console.print(f"[red]Error: API port {console_port + 1} is already in use (needed for dev mode)[/red]")
        return None

    proc = multiprocessing.Process(
        target=_run_console_server,
        kwargs={
            "nanobot_dir_str": str(get_data_dir()),
            "workspace_str": str(config.workspace_path),
            "host": config.gateway.host,
            "c_port": console_port,
            "gw_port": config.gateway.port,
            "secret_key": console_cfg.secret_key,
            "expire_minutes": console_cfg.token_expire_minutes,
            "token_stats_dir": str(get_data_dir() / "console"),
            "pid_file_str": str(CONSOLE_PID_FILE),
            "dev_mode": dev,
        },
        daemon=False,
    )
    proc.start()
    console.print(f"[green]✓[/green] Console started (PID: {proc.pid})")
    if dev:
        console.print(f"[green]✓[/green] Dev mode: Vite HMR at http://localhost:{console_port}")
        console.print(f"[green]✓[/green] API server at http://localhost:{console_port + 1}")
    else:
        console.print(f"[green]✓[/green] http://localhost:{console_port}")
    return proc.pid


# ============================================================================
# Console Management Commands
# ============================================================================


@app.command("console-stop")
def console_stop_cmd():
    """Stop the console UI server."""
    pid = _check_console_running()
    if not pid:
        console.print(f"{__logo__} Console Status\n")
        console.print("Status: [yellow]Not running[/yellow]")
        return

    console.print(f"{__logo__} Stopping Console\n")
    _stop_console_process()


@app.command("console-restart")
def console_restart_cmd(
    dev: bool = typer.Option(False, "--dev", help="Enable Vite dev server with HMR for console-ui"),
):
    """Restart (or start) the console UI server."""
    console.print(f"{__logo__} Restarting Console\n")

    if _check_console_running():
        _stop_console_process()
        import time
        time.sleep(0.5)

    _start_console_process(dev=dev)


# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:direct", "--session", "-s", help="Session ID"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show nanobot runtime logs during chat"),
):
    """Interact with the agent directly."""
    from nanobot.config.loader import load_config, get_data_dir
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop
    from nanobot.cron.service import CronService
    from loguru import logger

    config = load_config()
    sync_workspace_templates(config.workspace_path)

    bus = MessageBus()
    provider = _make_provider(config)

    # Create cron service for tool usage (no callback needed for CLI unless running)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    if logs:
        logger.enable("nanobot")
    else:
        logger.disable("nanobot")

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        vision_model=config.agents.defaults.vision_model,
        mini_model=config.agents.defaults.mini_model,
        voice_model=config.agents.defaults.voice_model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        reasoning_effort=config.agents.defaults.reasoning_effort,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        mcp_servers=config.tools.mcp_servers,
        channels_config=config.channels,
        context_compression=config.agents.defaults.context_compression,
        memory_tier=config.agents.defaults.memory_tier,
        in_loop_truncation=config.agents.defaults.in_loop_truncation,
    )

    # Show spinner when logs are off (no output to miss); skip when logs are on
    def _thinking_ctx():
        if logs:
            from contextlib import nullcontext
            return nullcontext()
        # Animated spinner is safe to use with prompt_toolkit input handling
        return console.status("[dim]nanobot is thinking...[/dim]", spinner="dots")

    async def _cli_progress(content: str, *, tool_hint: bool = False) -> None:
        ch = agent_loop.channels_config
        if ch and tool_hint and not ch.send_tool_hints:
            return
        if ch and not tool_hint and not ch.send_progress:
            return
        console.print(f"  [dim]↳ {content}[/dim]")

    if message:
        # Single message mode — direct call, no bus needed
        async def run_once():
            with _thinking_ctx():
                response = await agent_loop.process_direct(message, session_id, on_progress=_cli_progress)
            _print_agent_response(response, render_markdown=markdown)
            await agent_loop.close_mcp()

        asyncio.run(run_once())
    else:
        # Interactive mode — route through bus like other channels
        from nanobot.bus.events import InboundMessage
        _init_prompt_session()
        console.print(f"{__logo__} Interactive mode (type [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit)\n")

        if ":" in session_id:
            cli_channel, cli_chat_id = session_id.split(":", 1)
        else:
            cli_channel, cli_chat_id = "cli", session_id

        def _exit_on_sigint(signum, frame):
            _restore_terminal()
            console.print("\nGoodbye!")
            os._exit(0)

        signal.signal(signal.SIGINT, _exit_on_sigint)

        async def run_interactive():
            bus_task = asyncio.create_task(agent_loop.run())
            turn_done = asyncio.Event()
            turn_done.set()
            turn_response: list[str] = []

            async def _consume_outbound():
                while True:
                    try:
                        msg = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
                        if msg.metadata.get("_progress"):
                            is_tool_hint = msg.metadata.get("_tool_hint", False)
                            ch = agent_loop.channels_config
                            if ch and is_tool_hint and not ch.send_tool_hints:
                                pass
                            elif ch and not is_tool_hint and not ch.send_progress:
                                pass
                            else:
                                console.print(f"  [dim]↳ {msg.content}[/dim]")
                        elif not turn_done.is_set():
                            if msg.content:
                                turn_response.append(msg.content)
                            turn_done.set()
                        elif msg.content:
                            console.print()
                            _print_agent_response(msg.content, render_markdown=markdown)
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        break

            outbound_task = asyncio.create_task(_consume_outbound())

            try:
                while True:
                    try:
                        _flush_pending_tty_input()
                        user_input = await _read_interactive_input_async()
                        command = user_input.strip()
                        if not command:
                            continue

                        if _is_exit_command(command):
                            _restore_terminal()
                            console.print("\nGoodbye!")
                            break

                        turn_done.clear()
                        turn_response.clear()

                        await bus.publish_inbound(InboundMessage(
                            channel=cli_channel,
                            sender_id="user",
                            chat_id=cli_chat_id,
                            content=user_input,
                        ))

                        with _thinking_ctx():
                            await turn_done.wait()

                        if turn_response:
                            _print_agent_response(turn_response[0], render_markdown=markdown)
                    except KeyboardInterrupt:
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break
                    except EOFError:
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break
            finally:
                agent_loop.stop()
                outbound_task.cancel()
                await asyncio.gather(bus_task, outbound_task, return_exceptions=True)
                await agent_loop.close_mcp()

        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from nanobot.config.loader import load_config

    config = load_config()

    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Configuration", style="yellow")

    # WhatsApp
    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )

    dc = config.channels.discord
    table.add_row(
        "Discord",
        "✓" if dc.enabled else "✗",
        dc.gateway_url
    )

    # Feishu
    fs = config.channels.feishu
    fs_config = f"app_id: {fs.app_id[:10]}..." if fs.app_id else "[dim]not configured[/dim]"
    table.add_row(
        "Feishu",
        "✓" if fs.enabled else "✗",
        fs_config
    )

    # Mochat
    mc = config.channels.mochat
    mc_base = mc.base_url or "[dim]not configured[/dim]"
    table.add_row(
        "Mochat",
        "✓" if mc.enabled else "✗",
        mc_base
    )

    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row(
        "Telegram",
        "✓" if tg.enabled else "✗",
        tg_config
    )

    # Slack
    slack = config.channels.slack
    slack_config = "socket" if slack.app_token and slack.bot_token else "[dim]not configured[/dim]"
    table.add_row(
        "Slack",
        "✓" if slack.enabled else "✗",
        slack_config
    )

    # DingTalk
    dt = config.channels.dingtalk
    dt_config = f"client_id: {dt.client_id[:10]}..." if dt.client_id else "[dim]not configured[/dim]"
    table.add_row(
        "DingTalk",
        "✓" if dt.enabled else "✗",
        dt_config
    )

    # QQ
    qq = config.channels.qq
    qq_config = f"app_id: {qq.app_id[:10]}..." if qq.app_id else "[dim]not configured[/dim]"
    table.add_row(
        "QQ",
        "✓" if qq.enabled else "✗",
        qq_config
    )

    # Email
    em = config.channels.email
    em_config = em.imap_host if em.imap_host else "[dim]not configured[/dim]"
    table.add_row(
        "Email",
        "✓" if em.enabled else "✗",
        em_config
    )

    console.print(table)


def _get_bridge_dir() -> Path:
    """Get the bridge directory, setting it up if needed."""
    import shutil
    import subprocess

    # User's bridge location
    user_bridge = Path.home() / ".nanobot" / "bridge"

    # Check if already built
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge

    # Check for npm
    if not shutil.which("npm"):
        console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
        raise typer.Exit(1)

    # Find source bridge: first check package data, then source dir
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # nanobot/bridge (installed)
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge (dev)

    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge

    if not source:
        console.print("[red]Bridge source not found.[/red]")
        console.print("Try reinstalling: pip install --force-reinstall nanobot")
        raise typer.Exit(1)

    console.print(f"{__logo__} Setting up bridge...")

    # Copy to user directory
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))

    # Install and build
    try:
        console.print("  Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)

        console.print("  Building...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)

        console.print("[green]✓[/green] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)

    return user_bridge


@channels_app.command("login")
def channels_login():
    """Link device via QR code."""
    import subprocess
    from nanobot.config.loader import load_config

    config = load_config()
    bridge_dir = _get_bridge_dir()

    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")

    env = {**os.environ}
    if config.channels.whatsapp.bridge_token:
        env["BRIDGE_TOKEN"] = config.channels.whatsapp.bridge_token

    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True, env=env)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge failed: {e}[/red]")
    except FileNotFoundError:
        console.print("[red]npm not found. Please install Node.js.[/red]")


# ============================================================================
# Cron Commands
# ============================================================================

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="Include disabled jobs"),
):
    """List scheduled jobs."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    jobs = service.list_jobs(include_disabled=all)

    if not jobs:
        console.print("No scheduled jobs.")
        return

    table = Table(title="Scheduled Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Source", style="magenta")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("Next Run")

    import time
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    for job in jobs:
        # Format schedule
        if job.schedule.kind == "every":
            sched = f"every {(job.schedule.every_ms or 0) // 1000}s"
        elif job.schedule.kind == "cron":
            sched = f"{job.schedule.expr or ''} ({job.schedule.tz})" if job.schedule.tz else (job.schedule.expr or "")
        else:
            sched = "one-time"

        # Format next run
        next_run = ""
        if job.state.next_run_at_ms:
            ts = job.state.next_run_at_ms / 1000
            try:
                tz = ZoneInfo(job.schedule.tz) if job.schedule.tz else None
                next_run = _dt.fromtimestamp(ts, tz).strftime("%Y-%m-%d %H:%M")
            except Exception:
                next_run = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))

        status = "[green]enabled[/green]" if job.enabled else "[dim]disabled[/dim]"
        source_label = "[blue]schedule[/blue]" if job.source == "schedule" else "cli"

        table.add_row(job.id, job.name, source_label, sched, status, next_run)

    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),
    message: str = typer.Option(..., "--message", "-m", help="Message for agent"),
    every: int = typer.Option(None, "--every", "-e", help="Run every N seconds"),
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron expression (e.g. '0 9 * * *')"),
    tz: str | None = typer.Option(None, "--tz", help="IANA timezone for cron (e.g. 'America/Vancouver')"),
    at: str = typer.Option(None, "--at", help="Run once at time (ISO format)"),
    deliver: bool = typer.Option(False, "--deliver", "-d", help="Deliver response to channel"),
    to: str = typer.Option(None, "--to", help="Recipient for delivery"),
    channel: str = typer.Option(None, "--channel", help="Channel for delivery (e.g. 'telegram', 'whatsapp')"),
):
    """Add a scheduled job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronSchedule

    if tz and not cron_expr:
        console.print("[red]Error: --tz can only be used with --cron[/red]")
        raise typer.Exit(1)

    # Determine schedule type
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr, tz=tz)
    elif at:
        import datetime
        dt = datetime.datetime.fromisoformat(at)
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        console.print("[red]Error: Must specify --every, --cron, or --at[/red]")
        raise typer.Exit(1)

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    try:
        job = service.add_job(
            name=name,
            schedule=schedule,
            message=message,
            deliver=deliver,
            to=to,
            channel=channel,
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e

    console.print(f"[green]✓[/green] Added job '{job.name}' ({job.id})")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="Job ID to remove"),
):
    """Remove a scheduled job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    if service.remove_job(job_id):
        console.print(f"[green]✓[/green] Removed job {job_id}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("enable")
def cron_enable(
    job_id: str = typer.Argument(..., help="Job ID"),
    disable: bool = typer.Option(False, "--disable", help="Disable instead of enable"),
):
    """Enable or disable a job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    job = service.enable_job(job_id, enabled=not disable)
    if job:
        status = "disabled" if disable else "enabled"
        console.print(f"[green]✓[/green] Job '{job.name}' {status}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="Job ID to run"),
    force: bool = typer.Option(False, "--force", "-f", help="Run even if disabled"),
):
    """Manually run a job."""
    from loguru import logger
    from nanobot.config.loader import load_config, get_data_dir
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop
    logger.disable("nanobot")

    config = load_config()
    provider = _make_provider(config)
    bus = MessageBus()
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        vision_model=config.agents.defaults.vision_model,
        mini_model=config.agents.defaults.mini_model,
        voice_model=config.agents.defaults.voice_model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        reasoning_effort=config.agents.defaults.reasoning_effort,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        mcp_servers=config.tools.mcp_servers,
        channels_config=config.channels,
        context_compression=config.agents.defaults.context_compression,
        memory_tier=config.agents.defaults.memory_tier,
        in_loop_truncation=config.agents.defaults.in_loop_truncation,
    )

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    result_holder = []

    async def on_job(job: CronJob) -> str | None:
        model_override = agent_loop.get_model_for_tier(job.payload.model_tier)
        response = await agent_loop.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}",
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
            model_override=model_override,
        )
        result_holder.append(response)
        return response

    service.on_job = on_job

    async def run():
        return await service.run_job(job_id, force=force)

    if asyncio.run(run()):
        console.print("[green]✓[/green] Job executed")
        if result_holder:
            _print_agent_response(result_holder[0], render_markdown=True)
    else:
        console.print(f"[red]Failed to run job {job_id}[/red]")

# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show nanobot status."""
    from nanobot.config.loader import load_config, get_config_path

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} Nanobot Status\n")

    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        from nanobot.providers.registry import PROVIDERS

        console.print(f"Model: {config.agents.defaults.model}")

        # Check API keys from registry
        for spec in PROVIDERS:
            p = getattr(config.providers, spec.name, None)
            if p is None:
                continue
            if spec.is_oauth:
                console.print(f"{spec.label}: [green]✓ (OAuth)[/green]")
            elif spec.is_local:
                # Local deployments show api_base instead of api_key
                if p.api_base:
                    console.print(f"{spec.label}: [green]✓ {p.api_base}[/green]")
                else:
                    console.print(f"{spec.label}: [dim]not set[/dim]")
            else:
                has_key = bool(p.api_key)
                console.print(f"{spec.label}: {'[green]✓[/green]' if has_key else '[dim]not set[/dim]'}")


# ============================================================================
# OAuth Login
# ============================================================================

provider_app = typer.Typer(help="Manage providers")
app.add_typer(provider_app, name="provider")


_LOGIN_HANDLERS: dict[str, callable] = {}


def _register_login(name: str):
    def decorator(fn):
        _LOGIN_HANDLERS[name] = fn
        return fn
    return decorator


@provider_app.command("login")
def provider_login(
    provider: str = typer.Argument(..., help="OAuth provider (e.g. 'openai-codex', 'github-copilot')"),
):
    """Authenticate with an OAuth provider."""
    from nanobot.providers.registry import PROVIDERS

    key = provider.replace("-", "_")
    spec = next((s for s in PROVIDERS if s.name == key and s.is_oauth), None)
    if not spec:
        names = ", ".join(s.name.replace("_", "-") for s in PROVIDERS if s.is_oauth)
        console.print(f"[red]Unknown OAuth provider: {provider}[/red]  Supported: {names}")
        raise typer.Exit(1)

    handler = _LOGIN_HANDLERS.get(spec.name)
    if not handler:
        console.print(f"[red]Login not implemented for {spec.label}[/red]")
        raise typer.Exit(1)

    console.print(f"{__logo__} OAuth Login - {spec.label}\n")
    handler()


@_register_login("openai_codex")
def _login_openai_codex() -> None:
    try:
        from oauth_cli_kit import get_token, login_oauth_interactive
        token = None
        try:
            token = get_token()
        except Exception:
            pass
        if not (token and token.access):
            console.print("[cyan]Starting interactive OAuth login...[/cyan]\n")
            token = login_oauth_interactive(
                print_fn=lambda s: console.print(s),
                prompt_fn=lambda s: typer.prompt(s),
            )
        if not (token and token.access):
            console.print("[red]✗ Authentication failed[/red]")
            raise typer.Exit(1)
        console.print(f"[green]✓ Authenticated with OpenAI Codex[/green]  [dim]{token.account_id}[/dim]")
    except ImportError:
        console.print("[red]oauth_cli_kit not installed. Run: pip install oauth-cli-kit[/red]")
        raise typer.Exit(1)


@_register_login("github_copilot")
def _login_github_copilot() -> None:
    import asyncio

    console.print("[cyan]Starting GitHub Copilot device flow...[/cyan]\n")

    async def _trigger():
        from litellm import acompletion
        await acompletion(model="github_copilot/gpt-4o", messages=[{"role": "user", "content": "hi"}], max_tokens=1)

    try:
        asyncio.run(_trigger())
        console.print("[green]✓ Authenticated with GitHub Copilot[/green]")
    except Exception as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
