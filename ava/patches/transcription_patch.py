"""Monkey patch to add proxy support to GroqTranscriptionProvider.

Problem: api.groq.com is blocked by GFW; direct httpx requests fail with 403/timeout.
Fix: Inject socks5 proxy (from config.tools.web.proxy) into the httpx.AsyncClient
     used in GroqTranscriptionProvider.transcribe.

Requires: httpx[socks] / socksio (already installed as nanobot-ai dependency).
"""

from __future__ import annotations

from loguru import logger

from ava.launcher import register_patch


def apply_transcription_patch() -> str:
    """Patch GroqTranscriptionProvider.transcribe to use proxy from config."""
    from nanobot.providers.transcription import GroqTranscriptionProvider
    from pathlib import Path
    import json

    if not hasattr(GroqTranscriptionProvider, "transcribe"):
        logger.warning("transcription_patch skipped: transcribe not found")
        return "transcription_patch skipped (transcribe not found)"

    if getattr(GroqTranscriptionProvider.transcribe, "_ava_transcription_patched", False):
        return "transcription_patch already applied (skipped)"

    # Read proxy from config
    _proxy: str | None = None
    try:
        config_path = Path.home() / ".nanobot" / "config.json"
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            _proxy = data.get("tools", {}).get("web", {}).get("proxy") or None
        # Also check extra_config.json
        extra_path = Path.home() / ".nanobot" / "extra_config.json"
        if extra_path.exists():
            extra = json.loads(extra_path.read_text(encoding="utf-8"))
            _proxy = extra.get("tools", {}).get("web", {}).get("proxy") or _proxy
    except Exception as e:
        logger.warning("transcription_patch: failed to read proxy config: {}", e)

    if not _proxy:
        return "transcription_patch: no proxy configured, skipping"

    proxy = _proxy  # capture for closure

    import httpx
    from pathlib import Path as _Path

    original_transcribe = GroqTranscriptionProvider.transcribe

    async def patched_transcribe(self: GroqTranscriptionProvider, file_path: str | _Path) -> str:
        if not self.api_key:
            logger.warning("Groq API key not configured for transcription")
            return ""

        path = _Path(file_path)
        if not path.exists():
            logger.error("Audio file not found: {}", file_path)
            return ""

        try:
            async with httpx.AsyncClient(proxy=proxy) as client:
                with open(path, "rb") as f:
                    files = {
                        "file": (path.name, f),
                        "model": (None, "whisper-large-v3"),
                    }
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                    }
                    response = await client.post(
                        self.api_url,
                        headers=headers,
                        files=files,
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data.get("text", "")
        except Exception as e:
            logger.error("Groq transcription error (proxy={}): {}", proxy, e)
            return ""

    patched_transcribe._ava_transcription_patched = True
    GroqTranscriptionProvider.transcribe = patched_transcribe
    return f"GroqTranscriptionProvider.transcribe patched with proxy={proxy}"


register_patch("transcription_proxy", apply_transcription_patch)
