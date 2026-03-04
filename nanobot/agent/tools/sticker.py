"""Sticker tool for sending Telegram stickers."""

import json
import urllib.request
import urllib.error
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.config.loader import load_config

# Sticker pack name
STICKER_PACK_NAME = "ava_01"

# Sticker ID to emoji mapping
STICKER_EMOJIS = {
    1: "😌",
    2: "😲",
    3: "😴",
    4: "😊",
    5: "🤕",
    6: "💃",
    7: "😤",
    8: "🤪",
    9: "🎸",
    10: "🎮",
    11: "😎",
    12: "🤩",
    13: "😑",
    14: "❤️",
    15: "🤔",
    16: "🎧",
    17: "🙂",
    18: "😱",
    19: "🫨",
    20: "😳",
    21: "✨",
    22: "😪",
    23: "👊",
    24: "🪼",
}


class StickerTool(Tool):
    """Tool to send Telegram stickers."""

    def __init__(self):
        self._config = None
        self._default_chat_id = None
        self._sticker_cache: dict[str, str] | None = None
        self._sent_in_turn: bool = False

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current chat context."""
        self._default_chat_id = chat_id

    @property
    def name(self) -> str:
        return "send_sticker"

    @property
    def description(self) -> str:
        return (
            "Send a Telegram sticker from the ava sticker pack. "
            "Use this to express emotions visually. Sticker IDs: 1-24"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sticker_id": {
                    "type": "integer",
                    "description": (
                        "Sticker ID (1-24). "
                        "1=😌, 2=😲, 3=😴, 4=😊, 5=🤕, 6=💃, 7=😤, 8=🤪, "
                        "9=🎸, 10=🎮, 11=😎, 12=🤩, 13=😑, 14=❤️, 15=🤔, "
                        "16=🎧, 17=🙂, 18=😱, 19=🫨, 20=😳, 21=✨, 22=😪, "
                        "23=👊, 24=🪼"
                    ),
                },
                "chat_id": {
                    "type": "string",
                    "description": (
                        "Optional: Telegram chat ID. "
                        "If not provided, uses the current chat context."
                    ),
                },
            },
            "required": ["sticker_id"],
        }

    def _get_config(self) -> dict:
        """Load config and extract telegram settings."""
        if not self._config:
            config = load_config()
            tg = config.channels.telegram
            self._config = {
                "token": tg.token,
                "proxy": tg.proxy,
            }
        return self._config

    def _build_opener(self, proxy: str | None):
        """Build a urllib opener with optional proxy support."""
        handlers = []
        if proxy:
            proxy_handler = urllib.request.ProxyHandler({
                "http": proxy,
                "https": proxy,
            })
            handlers.append(proxy_handler)

        if handlers:
            return urllib.request.build_opener(*handlers)
        return None

    def _get_sticker_file_ids(self, token: str, proxy: str | None) -> dict[str, str]:
        """Fetch all sticker file_ids from the pack and cache them. Returns emoji->file_id map."""
        if self._sticker_cache is not None:
            return self._sticker_cache

        url = f"https://api.telegram.org/bot{token}/getStickerSet?name={STICKER_PACK_NAME}"
        try:
            opener = self._build_opener(proxy)
            if opener:
                response = opener.open(url, timeout=10)
            else:
                response = urllib.request.urlopen(url, timeout=10)

            data = json.loads(response.read().decode())
            if data.get("ok"):
                sticker_set = data.get("result", {})
                stickers = sticker_set.get("stickers", [])
                # Build emoji -> file_id cache
                cache = {}
                for sticker in stickers:
                    emoji = sticker.get("emoji")
                    file_id = sticker.get("file_id")
                    if emoji and file_id and emoji not in cache:
                        cache[emoji] = file_id
                self._sticker_cache = cache
                return cache
        except (urllib.error.URLError, json.JSONDecodeError):
            pass

        return {}

    def _send_sticker(self, token: str, chat_id: str, file_id: str, proxy: str | None) -> tuple[bool, str]:
        """Send sticker to chat."""
        url = f"https://api.telegram.org/bot{token}/sendSticker"
        data = {
            "chat_id": chat_id,
            "sticker": file_id,
        }

        try:
            opener = self._build_opener(proxy)

            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )

            if opener:
                response = opener.open(req, timeout=10)
            else:
                response = urllib.request.urlopen(req, timeout=10)

            result = json.loads(response.read().decode())
            if result.get("ok"):
                return True, "Sticker sent successfully"
            return False, result.get("description", "Unknown error")
        except urllib.error.URLError as e:
            return False, f"Network error: {e}"
        except json.JSONDecodeError as e:
            return False, f"Response parse error: {e}"

    async def execute(self, sticker_id: int, chat_id: str | None = None, **kwargs) -> str:
        """Execute the sticker send."""
        # Validate sticker_id
        if not 1 <= sticker_id <= 24:
            return f"Error: Sticker ID must be between 1-24, got {sticker_id}"

        # Get config
        cfg = self._get_config()
        token = cfg.get("token")
        proxy = cfg.get("proxy")

        if not token:
            return "Error: Telegram token not configured in ~/.nanobot/config.json"

        # Resolve chat_id
        target_chat_id = chat_id or self._default_chat_id
        if not target_chat_id:
            return "Error: No chat_id provided and no default chat context"

        # Get emoji for this sticker_id
        emoji = STICKER_EMOJIS.get(sticker_id)
        if not emoji:
            return f"Error: No emoji mapped for sticker_id {sticker_id}"

        # Get file_id from cache or API
        file_id_map = self._get_sticker_file_ids(token, proxy)
        file_id = file_id_map.get(emoji)
        if not file_id:
            return f"Error: Could not find sticker with emoji {emoji} in pack {STICKER_PACK_NAME}"

        # Send it
        success, msg = self._send_sticker(token, target_chat_id, file_id, proxy)
        if success:
            self._sent_in_turn = True
            return f"✓ Sticker {sticker_id} ({emoji}) sent to {target_chat_id}"
        return f"Error: {msg}"
