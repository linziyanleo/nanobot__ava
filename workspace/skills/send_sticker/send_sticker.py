#!/usr/bin/env python3
"""
send_sticker - 发送 Telegram 表情包

用法:
    python send_sticker.py <sticker_id> <chat_id>
    
环境变量:
    TELEGRAM_BOT_TOKEN: Telegram Bot Token
    STICKER_CONFIG_PATH: 配置文件路径 (可选，默认：~/.nanobot/sticker.json)
    STICKER_PACK: 使用的表情包 pack 名称 (可选，默认：从配置读取)
"""

import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any

# 默认配置
DEFAULT_STICKER_PACK_NAME = "ava_01"


class StickerConfig:
    """表情包配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()
        
    def _get_default_config_path(self) -> str:
        """获取默认配置文件路径"""
        return str(Path.home() / ".nanobot" / "sticker.json")
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件，如果不存在则返回空配置"""
        if not os.path.exists(self.config_path):
            print(f"Config file not found: {self.config_path}, using defaults")
            return {}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config: {e}, using defaults")
            return {}
    
    def get_pack(self, pack_name: Optional[str] = None) -> Dict[str, Any]:
        """获取指定表情包配置"""
        packs = self.config.get('packs', {})
        
        # 如果指定了 pack 名称，优先使用
        if pack_name and pack_name in packs:
            return packs[pack_name]
        
        # 否则使用第一个 pack 或默认 pack
        if packs:
            first_pack = list(packs.keys())[0]
            return packs[first_pack]
        
        return {}
    
    def list_packs(self) -> list:
        """列出所有可用的表情包"""
        packs = self.config.get('packs', {})
        result = []
        
        for name, pack in packs.items():
            result.append({
                'name': name,
                'description': pack.get('description', ''),
                'link': pack.get('link', ''),
                'count': len(pack.get('stickers', {}))
            })
        
        return result


def get_sticker_set(token: str, pack_name: str) -> dict:
    """获取 sticker set 信息"""
    url = f"https://api.telegram.org/bot{token}/getStickerSet?name={pack_name}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            if data.get("ok"):
                return data.get("result", {})
            else:
                print(f"Error: {data.get('description', 'Unknown error')}")
                return None
    except urllib.error.URLError as e:
        print(f"Network error: {e}")
        return None


def get_sticker_file_id(token: str, pack_name: str, emoji: str) -> str:
    """通过 emoji 获取 sticker 的 file_id"""
    # 先获取 sticker set
    sticker_set = get_sticker_set(token, pack_name)
    if not sticker_set:
        return None
    
    stickers = sticker_set.get("stickers", [])
    
    # 查找匹配的 emoji
    for sticker in stickers:
        if sticker.get("emoji") == emoji:
            return sticker.get("file_id")
    
    # 如果没有精确匹配，返回第一个
    if stickers:
        return stickers[0].get("file_id")
    
    return None


def send_sticker(token: str, chat_id: str, file_id: str) -> bool:
    """发送 sticker"""
    url = f"https://api.telegram.org/bot{token}/sendSticker"
    data = {
        "chat_id": chat_id,
        "sticker": file_id
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            if result.get("ok"):
                print(f"✓ Sticker sent successfully to {chat_id}")
                return True
            else:
                print(f"Error: {result.get('description', 'Unknown error')}")
                return False
    except urllib.error.URLError as e:
        print(f"Network error: {e}")
        return False


def main():
    # 加载配置
    config_path = os.environ.get('STICKER_CONFIG_PATH')
    config = StickerConfig(config_path)
    
    # 确定使用哪个 pack
    pack_name = os.environ.get('STICKER_PACK')
    sticker_pack = config.get_pack(pack_name)
    
    STICKER_PACK_NAME = sticker_pack.get('name', DEFAULT_STICKER_PACK_NAME)
    STICKER_LINK = sticker_pack.get('link', f'https://t.me/addstickers/{STICKER_PACK_NAME}')
    
    # 解析 stickers 字典（支持新格式和旧格式）
    raw_stickers = sticker_pack.get('stickers', sticker_pack.get('emojis', {}))
    STICKER_DATA = {}  # {id: {"emoji": ..., "meaning": ..., "aliases": [...]}}
    for key, value in raw_stickers.items():
        try:
            sticker_id = int(key)
            # 支持新格式（对象）和旧格式（简单字符串）
            if isinstance(value, dict):
                STICKER_DATA[sticker_id] = value
            else:
                STICKER_DATA[sticker_id] = {"emoji": value, "meaning": "", "aliases": []}
        except (ValueError, TypeError):
            print(f"Warning: Invalid sticker_id '{key}', skipping")
    
    if len(sys.argv) < 2:
        print("Usage: python send_sticker.py <sticker_id> <chat_id>")
        print("       python send_sticker.py list  # List all stickers")
        print("       python send_sticker.py packs # List all sticker packs")
        print("")
        print(f"Current pack: {STICKER_PACK_NAME}")
        print(f"Pack link: {STICKER_LINK}")
        print(f"Total stickers: {len(STICKER_DATA)}")
        sys.exit(1)
    
    # 列出所有表情包（不需要 token）
    if sys.argv[1] == "list":
        print(f"Sticker Pack: {STICKER_PACK_NAME}")
        print(f"Link: {STICKER_LINK}")
        print(f"Total: {len(STICKER_DATA)} stickers\n")
        print(f"{'ID':>3} | {'Emoji':^6} | {'Meaning':<16} | Aliases")
        print("-" * 50)
        for sticker_id, data in sorted(STICKER_DATA.items()):
            emoji = data.get('emoji', '')
            meaning = data.get('meaning', '')
            aliases = ' '.join(data.get('aliases', []))
            print(f"{sticker_id:>3} | {emoji:^6} | {meaning:<16} | {aliases}")
        sys.exit(0)
    
    # 列出所有可用表情包集合（不需要 token）
    if sys.argv[1] == "packs":
        packs = config.list_packs()
        if not packs:
            print("No sticker packs configured")
        else:
            print("Available Sticker Packs:")
            print("=" * 50)
            for pack in packs:
                print(f"Name: {pack['name']}")
                print(f"Description: {pack['description']}")
                print(f"Link: {pack['link']}")
                print(f"Stickers: {pack['count']}")
                print("-" * 50)
        sys.exit(0)
    
    # 以下操作需要 token
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set")
        sys.exit(1)
    
    # 发送表情
    try:
        sticker_id = int(sys.argv[1])
    except ValueError:
        print(f"Error: Invalid sticker_id '{sys.argv[1]}'")
        sys.exit(1)
    
    min_id = min(STICKER_DATA.keys()) if STICKER_DATA else 1
    max_id = max(STICKER_DATA.keys()) if STICKER_DATA else 24
    
    if sticker_id < min_id or sticker_id > max_id:
        print(f"Error: sticker_id must be between {min_id} and {max_id}")
        sys.exit(1)
    
    chat_id = sys.argv[2] if len(sys.argv) > 2 else None
    if not chat_id:
        print("Error: chat_id is required")
        print("Usage: python send_sticker.py <sticker_id> <chat_id>")
        sys.exit(1)
    
    sticker_info = STICKER_DATA.get(sticker_id)
    
    if not sticker_info:
        print(f"Error: No sticker mapped for sticker_id {sticker_id}")
        sys.exit(1)
    
    emoji = sticker_info.get('emoji', '')
    meaning = sticker_info.get('meaning', '')
    
    print(f"Sending sticker {sticker_id} ({emoji} - {meaning}) to {chat_id}...")
    print(f"Using pack: {STICKER_PACK_NAME}")
    
    # 获取 sticker file_id
    file_id = get_sticker_file_id(token, STICKER_PACK_NAME, emoji)
    if not file_id:
        print(f"Error: Could not find sticker with emoji {emoji}")
        sys.exit(1)
    
    # 发送 sticker
    success = send_sticker(token, chat_id, file_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
