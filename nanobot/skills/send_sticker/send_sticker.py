#!/usr/bin/env python3
"""
send_sticker - 发送 Telegram 表情包

用法:
    python send_sticker.py <sticker_id> <chat_id>
    
环境变量:
    TELEGRAM_BOT_TOKEN: Telegram Bot Token
    TELEGRAM_PROXY: SOCKS5 代理地址 (默认：socks5://127.0.0.1:13659)
"""

import os
import sys
import json
import subprocess

# Sticker pack 名称
STICKER_PACK_NAME = "ava_01"

# 表情编号到 emoji 的映射（用于获取 sticker）
STICKER_EMOJIS = {
    1: "😌", 2: "😲", 3: "😴", 4: "😊", 5: "🤕", 6: "💃",
    7: "😤", 8: "🤪", 9: "🎸", 10: "🎮", 11: "😎", 12: "🤩",
    13: "😑", 14: "❤️", 15: "🤔", 16: "🎧", 17: "🙂", 18: "😱",
    19: "🫨", 20: "😳", 21: "✨", 22: "😪", 23: "👊", 24: "🪼",
}

# Telegram 代理配置
TELEGRAM_PROXY = os.environ.get("TELEGRAM_PROXY", "socks5://127.0.0.1:13659")


def get_sticker_set(token: str, pack_name: str) -> dict:
    """获取 sticker set 信息"""
    cmd = [
        "curl",
        "--socks5-hostname", TELEGRAM_PROXY.replace("socks5://", ""),
        "-s",
        f"https://api.telegram.org/bot{token}/getStickerSet?name={pack_name}"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data.get("ok"):
                return data.get("result", {})
            else:
                print(f"Error: {data.get('description', 'Unknown error')}")
        else:
            print(f"curl error: {result.stderr}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def get_sticker_file_id(sticker_set: dict, emoji: str) -> str:
    """通过 emoji 获取 sticker 的 file_id"""
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
    cmd = [
        "curl",
        "--socks5-hostname", TELEGRAM_PROXY.replace("socks5://", ""),
        "-s",
        "-X", "POST",
        f"https://api.telegram.org/bot{token}/sendSticker",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"chat_id": chat_id, "sticker": file_id})
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data.get("ok"):
                print(f"✓ Sticker sent successfully to {chat_id}")
                return True
            else:
                print(f"Error: {data.get('description', 'Unknown error')}")
                return False
        else:
            print(f"curl error: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python send_sticker.py <sticker_id> <chat_id>")
        print("       python send_sticker.py list  # List all stickers")
        sys.exit(1)
    
    # 列出所有表情（不需要 token）
    if sys.argv[1] == "list":
        print(f"Sticker Pack: {STICKER_PACK_NAME}")
        print(f"Total: {len(STICKER_EMOJIS)} stickers\n")
        for sticker_id, emoji in sorted(STICKER_EMOJIS.items()):
            print(f"{sticker_id:2d}. {emoji}")
        sys.exit(0)
    
    # 发送表情
    try:
        sticker_id = int(sys.argv[1])
    except ValueError:
        print(f"Error: Invalid sticker_id '{sys.argv[1]}'")
        sys.exit(1)
    
    if sticker_id < 1 or sticker_id > 24:
        print(f"Error: sticker_id must be between 1 and 24")
        sys.exit(1)
    
    chat_id = sys.argv[2]
    emoji = STICKER_EMOJIS.get(sticker_id)
    
    if not emoji:
        print(f"Error: No emoji mapped for sticker_id {sticker_id}")
        sys.exit(1)
    
    # 获取 token
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set")
        sys.exit(1)
    
    print(f"Sending sticker {sticker_id} ({emoji}) to {chat_id}...")
    
    # 获取 sticker set
    sticker_set = get_sticker_set(token, STICKER_PACK_NAME)
    if not sticker_set:
        print(f"Error: Could not get sticker set '{STICKER_PACK_NAME}'")
        sys.exit(1)
    
    # 获取 sticker file_id
    file_id = get_sticker_file_id(sticker_set, emoji)
    if not file_id:
        print(f"Error: Could not find sticker with emoji {emoji}")
        sys.exit(1)
    
    # 发送 sticker
    success = send_sticker(token, chat_id, file_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
