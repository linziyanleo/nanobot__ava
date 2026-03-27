"""Patch ContextBuilder.build_messages to apply history processing and memory injection.

Intercept: ContextBuilder.build_messages
Behavior:
  1. Apply HistorySummarizer to compress old turns into condensed pairs
  2. Apply HistoryCompressor to trim history within character budget
  3. Call original build_messages
  4. Inject CategorizedMemoryStore context into system prompt

Depends on loop_patch having set self.context._agent_loop on the ContextBuilder.
"""

from __future__ import annotations

from loguru import logger

from ava.launcher import register_patch


def apply_context_patch() -> str:
    from nanobot.agent.context import ContextBuilder

    if getattr(ContextBuilder.build_messages, "_ava_patched", False):
        return "context_patch already applied (skipped)"

    original_build = ContextBuilder.build_messages

    def patched_build_messages(self, history, current_message, **kwargs):
        """Wrap build_messages: summarize → compress → build → inject memory."""
        channel = kwargs.get("channel")
        chat_id = kwargs.get("chat_id")

        loop = getattr(self, "_agent_loop", None)

        # 1. 历史摘要（旧轮次压缩为精简 user/assistant 对）
        summarizer = getattr(loop, "history_summarizer", None) if loop else None
        if summarizer:
            try:
                history = summarizer.summarize(history)
            except Exception as exc:
                logger.warning("HistorySummarizer failed, using raw history: {}", exc)

        # 2. 历史压缩（基于字符预算 + 相关性裁剪）
        compressor = getattr(loop, "history_compressor", None) if loop else None
        if compressor:
            try:
                history = compressor.compress(history, current_message)
            except Exception as exc:
                logger.warning("HistoryCompressor failed, using summarized history: {}", exc)

        # 3. 调用原始 build_messages
        messages = original_build(self, history, current_message, **kwargs)

        # 4. 注入分类记忆到系统提示词
        cat_mem = getattr(loop, "categorized_memory", None) if loop else None
        if cat_mem and channel and chat_id:
            try:
                memory_ctx = cat_mem.get_combined_context(channel, chat_id)
                if memory_ctx and messages and messages[0]["role"] == "system":
                    messages[0]["content"] += f"\n\n# Personal Memory\n\n{memory_ctx}"
            except Exception as exc:
                logger.warning("CategorizedMemory injection failed: {}", exc)

        # 5. 保存 system prompt 到 loop，供 token_stats 记录
        if loop and messages and messages[0].get("role") == "system":
            try:
                loop._last_system_prompt = (messages[0]["content"] or "")[:500]
            except Exception:
                pass

        return messages

    patched_build_messages._ava_patched = True
    ContextBuilder.build_messages = patched_build_messages

    return "ContextBuilder.build_messages patched: history summarize+compress, categorized memory injection"


register_patch("context_builder", apply_context_patch)
