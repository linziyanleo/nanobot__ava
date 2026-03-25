#!/usr/bin/env python3
"""
独立测试脚本：诊断 transcription API 的 404 问题。
用法：python test_transcription.py [音频文件路径]

会读取 ~/.nanobot/config.json 中的 voiceModel 配置，
解析出 provider、api_base、api_key、model，
然后直接用 httpx 调用 /audio/transcriptions 接口，
打印完整的请求/响应细节。
"""

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. 读取 config.json
# ---------------------------------------------------------------------------
CONFIG_PATH = Path.home() / ".nanobot" / "config.json"

if not CONFIG_PATH.exists():
    print(f"[ERROR] 找不到配置文件: {CONFIG_PATH}")
    sys.exit(1)

config = json.loads(CONFIG_PATH.read_text())

voice_model_raw = config.get("agents", {}).get("defaults", {}).get("voiceModel")
if not voice_model_raw:
    print("[ERROR] config.json 中未设置 voiceModel")
    sys.exit(1)

print(f"[CONFIG] voiceModel = {voice_model_raw}")

# ---------------------------------------------------------------------------
# 2. 解析 provider 前缀 → 查找对应的 api_key / api_base
# ---------------------------------------------------------------------------
providers_cfg = config.get("providers", {})

# 提取 "google/gemini-xxx" → prefix="google", model_name="gemini-xxx"
if "/" in voice_model_raw:
    prefix, model_name = voice_model_raw.split("/", 1)
else:
    prefix, model_name = None, voice_model_raw

print(f"[PARSE] prefix = {prefix!r}, model_name = {model_name!r}")

# 模拟 nanobot 的 provider 匹配逻辑
# 1) 先按前缀精确匹配 provider name
# 2) 再按关键词匹配 (gemini → gemini provider)
KEYWORD_MAP = {
    "gemini": "gemini",
    "groq": "groq",
    "whisper": "groq",
    "dashscope": "dashscope",
    "openai": "openai",
    "deepseek": "deepseek",
}

matched_provider_name = None

# 精确前缀匹配
if prefix and prefix in providers_cfg:
    matched_provider_name = prefix

# 关键词匹配
if not matched_provider_name:
    model_lower = voice_model_raw.lower()
    for kw, pname in KEYWORD_MAP.items():
        if kw in model_lower and pname in providers_cfg:
            matched_provider_name = pname
            break

# Fallback: 第一个有 apiKey 的 provider
if not matched_provider_name:
    for pname, pcfg in providers_cfg.items():
        if pcfg.get("apiKey"):
            matched_provider_name = pname
            break

if not matched_provider_name:
    print("[ERROR] 无法匹配到任何 provider")
    sys.exit(1)

provider_cfg = providers_cfg[matched_provider_name]
api_key = provider_cfg.get("apiKey", "")
api_base = provider_cfg.get("apiBase")

print(f"[MATCH] provider = {matched_provider_name!r}")
print(f"[MATCH] apiBase  = {api_base!r}")
print(f"[MATCH] apiKey   = {api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else f"[MATCH] apiKey   = (too short or empty)")

# ---------------------------------------------------------------------------
# 3. 构建最终 URL（与 TranscriptionProvider 一致）
# ---------------------------------------------------------------------------
if api_base:
    transcription_url = api_base.rstrip("/") + "/audio/transcriptions"
else:
    transcription_url = "https://api.groq.com/openai/v1/audio/transcriptions"

print(f"\n[URL] 最终请求地址: {transcription_url}")
print(f"[URL] 模型参数:     {model_name}")

# ---------------------------------------------------------------------------
# 4. 准备测试音频
# ---------------------------------------------------------------------------
audio_path = None
if len(sys.argv) > 1:
    audio_path = Path(sys.argv[1])
else:
    # 尝试常见位置
    candidates = [
        Path("/tmp/test_audio.ogg"),
        Path("/tmp/test_audio.mp3"),
        Path("/tmp/test_audio.wav"),
        Path("/tmp/test.ogg"),
        Path("/tmp/test.mp3"),
    ]
    for c in candidates:
        if c.exists():
            audio_path = c
            break

if not audio_path or not audio_path.exists():
    print("\n[WARN] 没有找到测试音频文件，将生成一段静音 WAV 用于测试...")
    import struct
    import wave

    audio_path = Path("/tmp/test_silence.wav")
    with wave.open(str(audio_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # 1 秒静音
        wf.writeframes(struct.pack("<" + "h" * 16000, *([0] * 16000)))
    print(f"[AUDIO] 已生成静音 WAV: {audio_path}")
else:
    print(f"[AUDIO] 使用音频文件: {audio_path}")

# ---------------------------------------------------------------------------
# 5. 发送请求
# ---------------------------------------------------------------------------
import httpx

print("\n" + "=" * 60)
print("发送 POST 请求...")
print("=" * 60)

headers = {"Authorization": f"Bearer {api_key}"}
print(f"[REQ] URL:     {transcription_url}")
print(f"[REQ] Headers: Authorization: Bearer {api_key[:8]}...")
print(f"[REQ] Files:   file={audio_path.name}, model={model_name}")

try:
    with httpx.Client(timeout=30.0) as client:
        with open(audio_path, "rb") as f:
            response = client.post(
                transcription_url,
                headers=headers,
                files={
                    "file": (audio_path.name, f),
                    "model": (None, model_name),
                },
            )

    print(f"\n[RESP] Status: {response.status_code}")
    print(f"[RESP] Headers:")
    for k, v in response.headers.items():
        print(f"         {k}: {v}")

    body = response.text
    if len(body) > 2000:
        body = body[:2000] + "... (truncated)"
    print(f"[RESP] Body:\n{body}")

    if response.status_code == 404:
        print("\n" + "=" * 60)
        print("[诊断] 404 Not Found — 可能的原因：")
        print(f"  1. API 网关 ({api_base}) 不支持 /audio/transcriptions 路由")
        print(f"  2. 当前 voiceModel ({voice_model_raw}) 对应的 provider")
        print(f"     ({matched_provider_name}) 不提供 Whisper 兼容的转录接口")
        print(f"  3. 需要将 voiceModel 改为支持转录的 provider，例如:")
        print(f"     - groq/whisper-large-v3  (需要 groq apiKey)")
        print(f"     - dashscope/paraformer-v2 (需要 dashscope apiKey)")
        print("=" * 60)

    elif response.status_code == 200:
        print("\n[SUCCESS] 转录成功！")

except httpx.ConnectError as e:
    print(f"\n[ERROR] 连接失败: {e}")
except Exception as e:
    print(f"\n[ERROR] 请求异常: {type(e).__name__}: {e}")
