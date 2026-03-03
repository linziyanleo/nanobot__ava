"""Sticker tool for sending Telegram stickers."""

import json
import urllib.request
import urllib.error
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.config.loader import load_config


# Sticker pack 名称
STICKER_PACK_NAME = "ava_01"

# 表情编号到 emoji 的映射
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

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current chat context."""
        self._default_chat_id = chat_id

    @property
    def name(self) -> str:
        return "send_sticker"

    @property
    def description(self) -> str:
        return "Send a Telegram sticker from the ava sticker pack. Use this to express emotions visually. Sticker IDs: 1-24"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sticker_id": {
                    "type": "integer",
                    "description": "Sticker ID (1-24). 1=😌, 2=😲, 3=😴, 4=😊, 5=🤕, 6=💃, 7=😤, 8=🤪, 9=🎸, 10=🎮, 11=😎, 12=🤩, 13=😑, 14=❤️, 15=🤔, 16=🎧, 17=🙂, 18=😱, 19=🫨, 20=😳, 21=✨, 22=😪, 23=👊, 24=🪼"
                },
                "chat_id": {
                    "type": "string",
                    "description": "Optional: Telegram chat ID. If not provided, uses the current chat context."
                }
            },
            "required": ["sticker_id"]
        }

    def _get_config(self):
        """Load config if not already loaded."""
        if self._config is None:
            self._config = load_config()
        return self._config

    def _get_sticker_file_id(self, token: str, emoji: str) -> str | None:
        """Get sticker file_id by emoji."""
        url = f"https://api.telegram.org/bot{token}/getStickerSet?name={STICKER_PACK_NAME}"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
                if data.get("ok"):
                    sticker_set = data.get("result", {})
                    stickers = sticker_set.get("stickers", [])
                    
                    # 查找匹配的 emoji
                    for sticker in stickers:
                        if sticker.get("emoji") == emoji:
                            return sticker.get("file_id")
                    
                    # 如果没有精确匹配，返回第一个
                    if stickers:
                        return stickers[0].get("file_id")
        except (urllib.error.URLError, json.JSONDecodeError, KeyError):
            pass
        
        return None

    def _send_sticker(self, token: str, chat_id: str, file_id: str, proxy: str | None = None) -> tuple[bool, str]:
        """Send sticker to chat."""
        url = f"https://api.telegram.org/bot{token}/sendSticker"
        data = {
            "chat_id": chat_id,
            "sticker": file_id
        }
        
        # 设置代理
        handlers = []
        if proxy:
            proxy_handler = urllib.request.ProxyHandler({
                'http': proxy,
                'https': proxy
            })
            handlers.append(proxy_handler)
        
        opener = urllib.request.build_opener(*handlers) if handlers else urllib.request.urlopen
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            with opener(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                if result.get("ok"):
                    return True, "Sticker sent successfully"
                else:
                    return False, result.get('description', 'Unknown error')
        except urllib.error.URLError as e:
            return False, f"Network error: {str(e)}"
        except json.JSONDecodeError as e:
            return False, f"Response parse error: {str(e)}"

    async def execute(
        self,
        sticker_id: int,
        chat_id: str | None = None,
        **kwargs: Any
    ) -> str:
        # 验证 sticker_id
        if not 1 <= sticker_id <= 24:
            return f"Error: Sticker ID must be between 1-24, got {sticker_id}"
        
        # 获取配置
        config = self._get_config()
        tg = config.channels.telegram
        
        if not tg.token:
            return "Error: Telegram token not configured"
        
        # 使用提供的 chat_id 或回退到默认值
        target_chat_id = chat_id or self._default_chat_id
        if not target_chat_id:
            return "Error: No chat_id provided and no default chat context"
        
        # 获取 emoji
        emoji = STICKER_EMOJIS.get(sticker_id)
        if not emoji:
            return f"Error: No emoji mapped for sticker_id {sticker_id}"
        
        # 获取 sticker file_id
        file_id = self._get_sticker_file_id(tg.token, emoji)
        if not file_id:
            return f"Error: Could not find sticker with emoji {emoji}"
        
        # 发送 sticker
        success, message = self._send_sticker(
            tg.token,
            target_chat_id,
            file_id,
            proxy=tg.proxy
        )
        
        if success:
            return f"✓ Sticker {sticker_id} ({emoji}) sent to {target_chat_id}"
        else:
            return f"Error: {message}"
