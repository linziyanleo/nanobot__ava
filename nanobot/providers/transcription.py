"""Voice transcription provider — supports any OpenAI-compatible transcription API."""

import os
from pathlib import Path

import httpx
from loguru import logger

_DEFAULT_MODEL = "whisper-large-v3"
_DEFAULT_API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class TranscriptionProvider:
    """
    Voice transcription provider using OpenAI-compatible /audio/transcriptions API.

    Supports Groq, DashScope, OpenAI, and any other provider with a compatible endpoint.
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        api_key: str | None = None,
        api_base: str | None = None,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if api_base:
            self.api_url = api_base.rstrip("/") + "/audio/transcriptions"
        else:
            self.api_url = _DEFAULT_API_URL

    async def transcribe(self, file_path: str | Path) -> str:
        """
        Transcribe an audio file.

        Args:
            file_path: Path to the audio file.

        Returns:
            Transcribed text, or empty string on failure.
        """
        if not self.api_key:
            logger.warning("Transcription API key not configured")
            return ""

        path = Path(file_path)
        if not path.exists():
            logger.error("Audio file not found: {}", file_path)
            return ""

        try:
            async with httpx.AsyncClient() as client:
                with open(path, "rb") as f:
                    files = {
                        "file": (path.name, f),
                        "model": (None, self.model),
                    }
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                    }

                    response = await client.post(
                        self.api_url,
                        headers=headers,
                        files=files,
                        timeout=60.0
                    )

                    response.raise_for_status()
                    data = response.json()
                    return data.get("text", "")

        except Exception as e:
            logger.error("Transcription error: {}", e)
            return ""


# Backward compatibility alias
GroqTranscriptionProvider = TranscriptionProvider
