"""Tests for transcription_patch — Groq transcription proxy injection."""

import json
from pathlib import Path

import pytest


class TestTranscriptionPatch:
    def test_skip_when_no_proxy_configured(self, monkeypatch, tmp_path):
        """T11.1: patch skips when config contains no proxy."""
        fake_home = tmp_path / "home"
        nanobot_dir = fake_home / ".nanobot"
        nanobot_dir.mkdir(parents=True)
        (nanobot_dir / "config.json").write_text(json.dumps({"tools": {"web": {}}}), encoding="utf-8")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

        from ava.patches.transcription_patch import apply_transcription_patch

        result = apply_transcription_patch()
        assert "skipping" in result.lower()

    def test_patch_applies_with_proxy(self, monkeypatch, tmp_path):
        """T11.2: patch applies when proxy config exists."""
        fake_home = tmp_path / "home"
        nanobot_dir = fake_home / ".nanobot"
        nanobot_dir.mkdir(parents=True)
        (nanobot_dir / "config.json").write_text(
            json.dumps({"tools": {"web": {"proxy": "socks5://127.0.0.1:1080"}}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

        from nanobot.providers.transcription import GroqTranscriptionProvider
        from ava.patches.transcription_patch import apply_transcription_patch

        result = apply_transcription_patch()
        assert "proxy=socks5://127.0.0.1:1080" in result
        assert getattr(GroqTranscriptionProvider.transcribe, "_ava_transcription_patched", False) is True

    def test_idempotent(self, monkeypatch, tmp_path):
        """T11.3: repeated apply returns skipped once patched."""
        fake_home = tmp_path / "home"
        nanobot_dir = fake_home / ".nanobot"
        nanobot_dir.mkdir(parents=True)
        (nanobot_dir / "config.json").write_text(
            json.dumps({"tools": {"web": {"proxy": "socks5://127.0.0.1:1080"}}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

        from ava.patches.transcription_patch import apply_transcription_patch

        apply_transcription_patch()
        result = apply_transcription_patch()
        assert "skipped" in result.lower()
